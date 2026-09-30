"""Print only schemas and selected non-personal domains; never credentials or client rows."""
import io
import json
import pandas as pd
from .source import S3Source, TABLES


def main():
    try:
        source = S3Source()
        files = source.inventory()
        for table in TABLES:
            group = [f for f in files if f.table == table]
            if not group:
                print(json.dumps({'table': table, 'files': 0}))
                continue
            f = group[-1]
            df = pd.read_csv(io.BytesIO(source.read(f)), low_memory=False)
            domains = {c: df[c].dropna().unique().tolist()[:25] for c in
                       ('product_type', 'currency', 'transaction_status', 'reason_category',
                        'subcategory', 'source_currency', 'target_currency') if c in df}
            print(json.dumps({'table': table, 'files': len(group), 'sample_file': f.key,
                              'columns': list(df.columns), 'domains': domains}, ensure_ascii=True))
            if table == 'daily_exchange_rates':
                print(df[['date', 'source_currency', 'target_currency', 'exchange_rate']].head(8).to_json(orient='records'))
    except Exception as exc:
        print(f'Inspección fallida ({type(exc).__name__}); no se imprimen mensajes externos por seguridad.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
