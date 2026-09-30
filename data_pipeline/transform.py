"""DuckDB transforms; bounded Pandera validation plus global uniqueness checks."""
from pathlib import Path
import duckdb
import pandas as pd

from .contracts import PRIMARY_KEYS, REQUIRED, schema_for
from .source import FACTS, TABLES


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def ident(value):
    return '"' + value.replace('"', '""') + '"'


CASTS = {
    'transactions': {'amount': 'DOUBLE', 'amount_usd': 'DOUBLE', 'fraud_score': 'DOUBLE', 'is_fraud': 'BOOLEAN'},
    'daily_exchange_rates': {'date': 'DATE', 'exchange_rate': 'DOUBLE'},
    'complaints': {'sla_breached': 'BOOLEAN', 'resolution_days': 'DOUBLE'},
    'call_center_interactions': {'was_resolved': 'BOOLEAN', 'duration_seconds': 'DOUBLE'},
    'satisfaction_surveys': {'main_score': 'DOUBLE'},
}
EVENT = {'transactions': 'transaction_date', 'complaints': 'creation_date',
         'call_center_interactions': 'interaction_date', 'satisfaction_surveys': 'survey_date'}


def transform(index, run_dir: Path, quality, reference, timezone='UTC', memory_limit='1GB'):
    silver = run_dir / 'silver'
    silver.mkdir(parents=True)
    con = duckdb.connect(str(run_dir / 'work.duckdb'))
    try:
        return _transform(con, index, silver, quality, reference, timezone, memory_limit)
    except Exception:
        con.close()
        raise


def _transform(con, index, silver, quality, reference, timezone, memory_limit):
    con.execute(f'SET memory_limit={literal(memory_limit)}')
    con.execute("SET threads=2; SET TimeZone='UTC'; SET preserve_insertion_order=false")
    counts = {}
    order = ['daily_exchange_rates', 'customers', 'products', 'complaints',
             'call_center_interactions', 'satisfaction_surveys', 'service_agents', 'transactions']
    for table in order:
        entries = [f for f in index['files'] if f['table'] == table]
        for entry in entries:
            missing = set(REQUIRED[table]) - set(entry['columns'])
            quality.check(f'{table}.required_columns', len(missing), details=sorted(missing))
        con.read_parquet([e['parquet'] for e in entries], union_by_name=True,
                         hive_partitioning=False).create_view('raw')
        cols = [r[0] for r in con.execute('DESCRIBE raw').fetchall()]
        replacements = [f'CAST({ident(col)} AS {typ}) AS {ident(col)}'
                        for col, typ in CASTS.get(table, {}).items()]
        if 'country' in cols:
            replacements.append("CASE WHEN country='Mexico' THEN 'México' ELSE country END AS country")
        if 'transaction_country' in cols:
            replacements.append("CASE WHEN transaction_country='Mexico' THEN 'México' ELSE transaction_country END AS transaction_country")
        star = '* REPLACE (' + ', '.join(replacements) + ')' if replacements else '*'
        additions = []
        if table in FACTS:
            mismatch = con.execute('SELECT count(*) FROM raw WHERE _partition_date IS NOT NULL '
                                   'AND CAST(_partition_date AS DATE) <> CAST(process_date AS DATE)').fetchone()[0]
            quality.check(f'{table}.partition_matches_process_date', mismatch)
            additions.append('CAST(coalesce(_partition_date, process_date) AS DATE) AS business_date')
            event = EVENT[table]
            timestamp_name = 'transaction_ts_utc' if table == 'transactions' else 'event_ts_utc'
            additions.append(f"CASE WHEN regexp_matches({event}, '(Z|[+-][0-9]{{2}}:[0-9]{{2}})$') "
                             f'THEN CAST({event} AS TIMESTAMPTZ) ELSE CAST({event} AS TIMESTAMP) '
                             f'AT TIME ZONE {literal(timezone)} END AS {timestamp_name}')
        con.execute('CREATE OR REPLACE TABLE typed AS SELECT ' + star +
                    (', ' + ', '.join(additions) if additions else '') + ' FROM raw')
        input_rows = con.execute('SELECT count(*) FROM typed').fetchone()[0]
        pk = ', '.join(ident(k) for k in PRIMARY_KEYS[table])
        ranking = []
        if 'last_updated' in cols:
            ranking.append('CAST(last_updated AS TIMESTAMPTZ) DESC NULLS LAST')
        if table in FACTS:
            ranking.append('business_date DESC')
            ranking.append(f'CAST({EVENT[table]} AS TIMESTAMPTZ) DESC')
        ranking.extend(['_ingested_at DESC', '_source_file DESC', '_file_hash DESC', '_source_row DESC'])
        con.execute(f'CREATE TABLE {table} AS SELECT * FROM typed QUALIFY '
                    f'row_number() OVER (PARTITION BY {pk} ORDER BY {", ".join(ranking)}) = 1')
        if table == 'transactions':
            repaired = con.execute("SELECT currency, count(*) FROM transactions WHERE amount_usd IS NULL OR currency='USD' GROUP BY currency").fetchall()
            # Source->USD rates are direct multipliers; no inverse/nearest-date imputation.
            con.execute("""CREATE OR REPLACE TABLE transactions AS
                SELECT t.* REPLACE (CASE WHEN t.currency='USD' THEN t.amount
                    ELSE coalesce(t.amount_usd, round(t.amount*r.exchange_rate, 2)) END AS amount_usd)
                FROM transactions t LEFT JOIN daily_exchange_rates r
                  ON r.date=t.business_date AND r.source_currency=t.currency AND r.target_currency='USD'""")
            quality.check('transactions.fx_repairs', 0, details=dict(repaired))
            quality.check('transactions.amount_usd_missing', con.execute('SELECT count(*) FROM transactions WHERE amount_usd IS NULL').fetchone()[0])
        if table in FACTS:
            quality.check(f'{table}.future_business_date', con.execute(
                f'SELECT count(*) FROM {table} WHERE business_date > ?', [reference]).fetchone()[0])
            stamp = 'transaction_ts_utc' if table == 'transactions' else 'event_ts_utc'
            late = con.execute(f'SELECT count(*) FROM {table} WHERE CAST({stamp} AS DATE) < business_date').fetchone()[0]
            quality.check(f'{table}.late_events', late, severity='warning')
        rows = con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        for col, dtype in CASTS.get(table, {}).items():
            if dtype == 'DOUBLE':
                nonfinite = con.execute(f'SELECT count(*) FROM {table} WHERE {ident(col)} IS NOT NULL AND NOT isfinite({ident(col)})').fetchone()[0]
                quality.check(f'{table}.finite.{col}', nonfinite, total=rows)
        # Same content with distinct primary keys is evidence, not permission to erase events.
        content_cols = [ident(c) for c in REQUIRED[table] if c not in PRIMARY_KEYS[table]]
        content_duplicates = 0
        if table in ('transactions', 'complaints', 'call_center_interactions'):
            # Include all original business columns, not merely the serving projection.
            content_cols = [ident(c) for c in cols if not c.startswith('_') and c not in PRIMARY_KEYS[table]]
            content_duplicates = rows-con.execute(f'SELECT count(*) FROM (SELECT DISTINCT {", ".join(content_cols)} FROM {table})').fetchone()[0]
            quality.check(f'{table}.duplicate_content_different_pk', content_duplicates, severity='warning', total=rows)
        duplicates = con.execute(f'SELECT count(*) FROM (SELECT {pk} FROM {table} GROUP BY {pk} HAVING count(*) > 1)').fetchone()[0]
        quality.check(f'{table}.unique_pk', duplicates, total=rows)
        schema = schema_for(table)
        # Pandera checks run on bounded batches; uniqueness is also checked globally above.
        reader = con.execute(f'SELECT * FROM {table}').to_arrow_reader(batch_size=50000)
        for batch in reader:
            df = batch.to_pandas()
            for c in schema.columns:
                dtype = str(schema.columns[c].dtype)
                if dtype.startswith('datetime64'):
                    df[c] = pd.to_datetime(df[c], utc='UTC' in dtype).astype(dtype)
            try:
                schema.validate(df, lazy=True)
            except Exception as exc:
                failures = getattr(exc, 'failure_cases', None)
                if failures is not None:
                    summary = failures.groupby(['column','check'], dropna=False).size()
                    quality.checks.append({'check':f'{table}.pandera','severity':'error','status':'fail',
                                           'details':{str(k):int(v) for k,v in summary.items()}})
                raise
        quality.check(f'{table}.pandera', 0, total=rows)
        for c in REQUIRED[table]:
            nulls = con.execute(f'SELECT count(*) FROM {table} WHERE {ident(c)} IS NULL').fetchone()[0]
            expected = .25 if c == 'fraud_score' else .85 if c == 'merchant_name' else .10
            quality.check(f'{table}.nulls.{c}', nulls if rows and nulls / rows > expected else 0,
                          severity='warning', total=rows, details={'null_count': nulls, 'warn_above_fraction': expected})
        output = silver / (table + '.parquet')
        con.execute(f'COPY {table} TO {literal(output)} (FORMAT PARQUET, COMPRESSION ZSTD)')
        counts[table] = {'bronze_rows': input_rows, 'silver_rows': rows,
                         'discarded_duplicate_pk': input_rows - rows,
                         'duplicate_content_different_pk_retained':content_duplicates}
        print(f'Silver {table}: {rows} filas', flush=True)
    for table, fk, parent, parent_pk in [('products','customer_id','customers','customer_id'),
            ('transactions','customer_id','customers','customer_id'), ('transactions','product_id','products','product_id'),
            ('complaints','customer_id','customers','customer_id'),
            ('satisfaction_surveys','interaction_id','call_center_interactions','interaction_id')]:
        n = con.execute(f'SELECT count(*) FROM {table} c LEFT JOIN {parent} p ON c.{fk}=p.{parent_pk} '
                        f'WHERE c.{fk} IS NOT NULL AND p.{parent_pk} IS NULL').fetchone()[0]
        quality.check(f'{table}.orphan.{fk}', n, severity='warning')
    return con, counts
