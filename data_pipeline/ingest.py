"""CSV -> immutable Parquet objects, SHA-256 of original bytes, resumable inventory."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path

import pandas as pd

from .lineage import sha256, write_json
from .source import TABLES

BRONZE_FORMAT_VERSION = 2


def ingest(source, data_dir: Path, reference: date, start: date, since, reprocess_days,
           quality, workers=4):
    index_path = data_dir / 'bronze_index.json'
    old = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    if since and not old:
        raise ValueError('El incremental requiere una carga full previa.')
    if old and old.get('source') != source.name:
        raise ValueError('Usa otro data-dir para cambiar de fuente.')
    previous = {f['key']: f for f in old.get('files', [])}
    cutoff = since - timedelta(days=reprocess_days) if since else None
    files = [f for f in source.inventory()
             if (not f.partition or f.partition <= reference.isoformat())
             and (f.table != 'transactions' or not f.partition or f.partition >= start.isoformat())]
    for table in TABLES:
        quality.check(f'bronze.{table}.source_present', not any(f.table == table for f in files))
    now = datetime.now(timezone.utc).isoformat()
    cache = data_dir / 'bronze'
    cache.mkdir(parents=True, exist_ok=True)

    def one(item):
        prior = previous.get(item.key)
        outside = cutoff and item.partition and item.partition < cutoff.isoformat()
        if outside:
            if prior:
                cached = Path(prior['parquet'])
                if not cached.exists() or sha256(cached) != prior['parquet_sha256']:
                    raise ValueError('Bronze previo fuera de ventana no íntegro; ejecutar --full.')
            return prior, 'outside_changed' if not prior or prior['identity'] != item.identity else 'outside'
        if prior and prior.get('format_version') == BRONZE_FORMAT_VERSION and prior['identity'] == item.identity:
            path = Path(prior['parquet'])
            if path.exists() and sha256(path) == prior['parquet_sha256']:
                return prior, 'reused'
        raw = source.read(item)
        digest = hashlib.sha256(raw).hexdigest()
        # dtype=str preserves identifiers and lexical values; empty CSV fields are null.
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, na_values=[''])
        if any(c.startswith('_') for c in df.columns):
            raise ValueError('El origen usa columnas reservadas con prefijo _.')
        columns = list(df.columns)
        df['_source_file'] = source.name + '/' + item.key
        df['_ingested_at'] = now
        df['_file_hash'] = digest
        df['_partition_date'] = item.partition
        df['_source_row'] = range(1,len(df)+1)
        name = hashlib.sha256((str(BRONZE_FORMAT_VERSION) + item.key + digest).encode()).hexdigest()
        path = cache / item.table / (name + '.parquet')
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_suffix('.tmp')
            df.to_parquet(temp, index=False)
            os.replace(temp, path)
        return {'key': item.key, 'table': item.table, 'partition': item.partition,
                'identity': item.identity, 'source_file': source.name + '/' + item.key,
                'format_version':BRONZE_FORMAT_VERSION,
                'sha256': digest, 'bytes': len(raw), 'rows': len(df), 'columns': columns,
                'parquet': str(path.resolve()), 'parquet_sha256': sha256(path)}, 'read'

    records, actions = [], {}
    late_files = sum(1 for f in files if since and f.partition and cutoff.isoformat() <= f.partition < since.isoformat()
                     and (f.key not in previous or previous[f.key]['identity'] != f.identity))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for count, (record, action) in enumerate(pool.map(one, files), 1):
            if record:
                records.append(record)
            actions[action] = actions.get(action, 0) + 1
            if count % 250 == 0:
                print(f'Bronze: {count}/{len(files)} archivos', flush=True)
    # A missing source object is not silently interpreted as a record deletion.
    missing = set(previous) - {f.key for f in files}
    if since:
        for key in sorted(missing):
            prior = previous[key]
            cached = Path(prior['parquet'])
            quality.check('bronze.retained_deleted_object_integrity',
                          not cached.exists() or sha256(cached) != prior['parquet_sha256'])
            records.append(prior)
    quality.check('bronze.deleted_source_files', len(missing), severity='warning',
                  details='Incremental retains prior objects; full rebuild reconciles source deletions.')
    quality.check('bronze.changes_outside_reprocess_window', actions.get('outside_changed', 0),
                  severity='warning', details='Run --full or use an earlier --since to include these changes.')
    quality.check('bronze.late_arrivals_in_window', late_files, severity='warning',
                  details='New/changed objects with a partition before --since, included by the reprocess window.')
    for table in TABLES:
        old_columns = set(c for f in previous.values() if f['table']==table for c in f['columns'])
        new_columns = set(c for f in records if f['table']==table for c in f['columns'])
        added = sorted(new_columns-old_columns) if old_columns else []
        removed = sorted(old_columns-new_columns) if old_columns else []
        quality.check(f'bronze.{table}.schema_evolution',len(added)+len(removed),severity='warning',
                      details={'added':added,'removed':removed})
    index = {'source': source.name, 'files': records, 'actions': actions}
    write_json(index_path, index)
    return index
