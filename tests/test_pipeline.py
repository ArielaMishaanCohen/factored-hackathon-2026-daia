"""Offline integration tests: generated CSV -> actual pipeline -> backend contract."""
import csv
from datetime import date
import json
from pathlib import Path

import duckdb
import pytest
from pandera.errors import SchemaErrors

from data_pipeline.build_gold import GOLD_TABLES, backend_schema
from data_pipeline.lineage import sha256
from data_pipeline.run_pipeline import run
from data_pipeline.source import LocalSource, ROOT
from data_pipeline.quality import QualityError

FIXTURE = json.loads((Path(__file__).parent/'fixtures/incremental/scenario.json').read_text())
TX_COLS = ['transaction_id','customer_id','product_id','amount','currency','amount_usd',
           'transaction_status','fraud_score','merchant_name']


def write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def tx_file(root, day, values, extra=False):
    d=date.fromisoformat(day)
    records=[]
    for values_row in values:
        row=dict(zip(TX_COLS,values_row))
        row.update(process_date=day,transaction_date=day+'T23:30:00',transaction_type='Purchase',
                   channel='POS',transaction_country='Mexico',is_fraud=row['fraud_score']==45)
        if extra:
            row[FIXTURE['new_column']]='v2'
        records.append(row)
    write_csv(root/f'transactions/year={d.year}/month={d.month:02d}/day={d.day:02d}/tx.csv',records)


@pytest.fixture
def source(tmp_path):
    root=tmp_path/'source'
    customers=[dict(customer_id=f'C-{n:02d}',segment='Basic',country='Mexico',last_updated='2026-06-17T00:00:00') for n in range(1,10)]
    products=[dict(product_id=f'P-{n:02d}',customer_id=f'C-{n:02d}',product_type='Tarjeta Débito',
                   product_number=f'1234567890{n:04d}',currency='COP' if n==9 else 'USD',
                   product_status='Active',last_updated='2026-06-17T00:00:00') for n in range(1,10)]
    write_csv(root/'customers.csv',customers)
    write_csv(root/'products.csv',products)
    write_csv(root/'daily_exchange_rates.csv',[dict(date='2026-06-16',source_currency='COP',target_currency='USD',exchange_rate=.00025)])
    write_csv(root/'service_agents.csv',[dict(agent_id='A-01',languages='es,pt',agent_status='Active')])
    write_csv(root/'complaints/year=2026/month=06/day=16/c.csv',[
        dict(complaint_id='Q-1',customer_id='C-09',process_date='2026-06-16',creation_date='2026-06-16T01:00:00',
             subcategory='Cargo no reconocido',status='Open',sla_breached=False,resolution_days='')])
    write_csv(root/'call_center_interactions/year=2026/month=06/day=16/i.csv',[
        dict(interaction_id='I-1',customer_id='C-09',process_date='2026-06-16',interaction_date='2026-06-16T01:00:00',
             reason_category='Queja',was_resolved=False,duration_seconds=100)])
    write_csv(root/'satisfaction_surveys/year=2026/month=06/day=16/s.csv',[
        dict(survey_id='S-1',customer_id='C-09',interaction_id='I-1',process_date='2026-06-16',
             survey_date='2026-06-16T02:00:00',survey_type='CSAT',main_score=2)])
    tx_file(root,FIXTURE['day_n'],FIXTURE['base_transactions'])
    return root


def execute(root,tmp_path,**kwargs):
    return run(source=LocalSource(root),data_dir=tmp_path/'data',reports_dir=tmp_path/'reports',
               policy_path=ROOT/'config/policy.yaml',workers=1,**kwargs)


def logical_gold(path):
    with duckdb.connect(str(path),read_only=True) as con:
        return {table:con.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall() for table in GOLD_TABLES}


def test_incremental_late_duplicate_new_column_and_idempotency(source,tmp_path):
    execute(source,tmp_path)
    tx_file(source,FIXTURE['day_n_plus_1'],[FIXTURE['duplicate_update']]*2,extra=True)
    tx_file(source,FIXTURE['late_partition'],[FIXTURE['late_arrival']],extra=True)
    manifest=execute(source,tmp_path,since=date(2026,6,17))
    checks=json.loads((tmp_path/'reports/quality_report.json').read_text())['checks']
    assert next(c for c in checks if c['check']=='bronze.late_arrivals_in_window')['failures']==1
    assert next(c for c in checks if c['check']=='bronze.transactions.schema_evolution')['details']['added']==['provider_revision']
    path=tmp_path/'data/gold/gold_full.duckdb'
    first=logical_gold(path)
    with duckdb.connect(str(path),read_only=True) as con:
        assert con.execute('SELECT count(*) FROM dispute_transactions').fetchone()[0]==11
        assert con.execute("SELECT amount FROM dispute_transactions WHERE transaction_id='TX-01'").fetchone()[0]==120
        assert con.execute("SELECT amount_usd FROM dispute_transactions WHERE transaction_id='TX-FX'").fetchone()[0]==100
        assert con.execute("SELECT count(*) FROM dispute_transactions WHERE transaction_id='TX-LATE'").fetchone()[0]==1
    silver=tmp_path/'data/runs'/manifest['run_id']/'silver/transactions.parquet'
    with duckdb.connect() as con:
        assert 'provider_revision' in con.read_parquet(str(silver)).columns
    execute(source,tmp_path,since=date(2026,6,17))
    assert logical_gold(path)==first
    execute(source,tmp_path)
    assert logical_gold(path)==first


def test_exact_backend_schema_minimization_and_real_rules(source,tmp_path):
    execute(source,tmp_path)
    path=tmp_path/'data/gold/gold.duckdb'
    expected=duckdb.connect()
    expected.execute(backend_schema())
    with duckdb.connect(str(path),read_only=True) as con:
        for table in GOLD_TABLES:
            assert con.execute(f"PRAGMA table_info('{table}')").fetchall()==expected.execute(f"PRAGMA table_info('{table}')").fetchall()
        assert con.execute('SELECT count(*) FROM demo_customers').fetchone()[0]==8
        for table in GOLD_TABLES:
            assert not {'is_fraud','product_number','email','document_number'} & set(con.table(table).columns)
        assert con.execute("SELECT count(*) FROM cards WHERE card_mask NOT LIKE '•••• ____'").fetchone()[0]==0
    expected.close()


@pytest.mark.parametrize('damage',['missing_column','bad_status','missing_fx'])
def test_failed_quality_preserves_published_gold(source,tmp_path,damage):
    execute(source,tmp_path)
    path=tmp_path/'data/gold/gold.duckdb'
    old=sha256(path)
    if damage=='missing_fx':
        write_csv(source/'daily_exchange_rates.csv',[dict(date='2026-06-15',source_currency='COP',target_currency='USD',exchange_rate=.00025)])
    else:
        tx=next((source/'transactions').rglob('*.csv'))
        with tx.open(encoding='utf-8') as f:
            records=list(csv.DictReader(f))
        if damage=='missing_column':
            for record in records:
                del record['currency']
        else:
            records[0]['transaction_status']='INVALID'
        write_csv(tx,records)
    with pytest.raises(SchemaErrors if damage=='bad_status' else QualityError):
        execute(source,tmp_path)
    assert sha256(path)==old
    report=json.loads((tmp_path/'reports/quality_report.json').read_text())
    assert report['status']=='failed'
    assert json.loads((tmp_path/'data/manifest.json').read_text())['status']=='success'


def test_incremental_requires_previous_success(source,tmp_path):
    with pytest.raises(ValueError,match='full exitoso'):
        execute(source,tmp_path,since=date(2026,6,17))


def test_timezone_preserves_business_date_and_offset(source,tmp_path):
    tx=next((source/'transactions').rglob('*.csv'))
    with tx.open(encoding='utf-8') as f:
        records=list(csv.DictReader(f))
    records[0]['transaction_date']='2026-06-17T01:30:00Z'
    write_csv(tx,records)
    manifest=execute(source,tmp_path,source_timezone='America/Guatemala')
    silver=tmp_path/'data/runs'/manifest['run_id']/'silver/transactions.parquet'
    with duckdb.connect() as con:
        con.read_parquet(str(silver)).create_view('t')
        row=con.execute("SELECT business_date, transaction_ts_utc AT TIME ZONE 'UTC' FROM t WHERE transaction_id='TX-01'").fetchone()
        assert row[0]==date(2026,6,16)
        assert row[1].hour==1  # explicit UTC offset must not be interpreted as Guatemala local time
        naive=con.execute("SELECT transaction_ts_utc AT TIME ZONE 'UTC' FROM t WHERE transaction_id='TX-02'").fetchone()[0]
        assert naive.day==17 and naive.hour==5


def test_older_arrival_is_warned_until_full(source,tmp_path):
    execute(source,tmp_path)
    tx_file(source,'2026-06-10',[FIXTURE['late_arrival']])
    execute(source,tmp_path,since=date(2026,6,17))
    with duckdb.connect(str(tmp_path/'data/gold/gold_full.duckdb'),read_only=True) as con:
        assert con.execute("SELECT count(*) FROM dispute_transactions WHERE transaction_id='TX-LATE'").fetchone()[0]==0
    checks=json.loads((tmp_path/'reports/quality_report.json').read_text())['checks']
    assert next(c for c in checks if c['check']=='bronze.changes_outside_reprocess_window')['failures']==1
    execute(source,tmp_path)
    with duckdb.connect(str(tmp_path/'data/gold/gold_full.duckdb'),read_only=True) as con:
        assert con.execute("SELECT count(*) FROM dispute_transactions WHERE transaction_id='TX-LATE'").fetchone()[0]==1
