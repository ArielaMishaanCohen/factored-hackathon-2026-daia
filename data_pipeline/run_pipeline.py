"""Reproducible S3/local -> bronze -> silver -> gold; reports survive failed runs."""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import yaml

from .analytics import analyze
from .build_gold import build_gold
from .ingest import BRONZE_FORMAT_VERSION, ingest
from .lineage import code_version, sha256, write_json
from .quality import Quality
from .source import LocalSource, ROOT, S3Source
from .transform import transform


def publish_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix+'.tmp')
    shutil.copyfile(source,temp)
    os.replace(temp,destination)


def run(*, source, data_dir, reports_dir, policy_path, since=None, reprocess_days=3,
        start=date(2025,7,1), workers=4, source_timezone='UTC', sample_customers=100,
        require_demos=True, memory_limit='1GB', analysis_dir=None):
    data_dir, reports_dir = Path(data_dir).resolve(), Path(reports_dir).resolve()
    policy_path = Path(policy_path)
    policy_text = policy_path.read_text(encoding='utf-8')
    policy = yaml.safe_load(policy_text)
    reference = date.fromisoformat(policy['reference_date'])
    if reprocess_days < 0 or workers < 1 or sample_customers < 0 or start > reference:
        raise ValueError('Parámetros fuera de rango.')
    if since and (since > reference or not (data_dir/'manifest.json').exists()):
        raise ValueError('Incremental requiere full exitoso previo y --since <= reference_date.')
    if since:
        previous = json.loads((data_dir/'manifest.json').read_text(encoding='utf-8'))
        if previous['parameters']['start'] != start.isoformat():
            raise ValueError('Cambiar la ventana histórica requiere --full.')
        if any(f.get('format_version') != BRONZE_FORMAT_VERSION for f in previous['inputs']['files']):
            raise ValueError('Cambió el formato bronze; ejecuta --full antes de otro incremental.')
    data_dir.mkdir(parents=True,exist_ok=True)
    lock = data_dir/'.pipeline.lock'
    with lock.open('x',encoding='utf-8') as f:
        f.write(str(os.getpid()))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run_dir = data_dir/'runs'/run_id
    run_dir.mkdir(parents=True)
    (run_dir/'policy.yaml').write_text(policy_text,encoding='utf-8')
    quality, con = Quality(), None
    stage = 'ingest'
    manifest = {'run_id':run_id,'status':'running','started_at':datetime.now(timezone.utc).isoformat(),
                'source':source.name,'code':code_version(ROOT),'policy_version':policy['policy_version'],
                'policy_sha256':sha256(run_dir/'policy.yaml'),
                'parameters':{'start':start.isoformat(),'reference_date':reference.isoformat(),
                              'since':str(since) if since else None,'reprocess_days':reprocess_days,
                              'source_timezone':source_timezone,'sample_customers':sample_customers},
                'freshness':{'policy':'T+1; static fixture demonstrates late arrivals.',
                             'measured_against':'reference_date, not wall clock'}}
    try:
        index = ingest(source,data_dir,reference,start,since,reprocess_days,quality,workers)
        manifest['inputs'] = index
        stage = 'transform'
        con, counts = transform(index,run_dir,quality,reference,source_timezone,memory_limit)
        manifest['counts'] = counts
        stage = 'analytics'
        analyze(con,run_dir,policy)
        stage = 'gold'
        demos,gold_counts = build_gold(con,run_dir,policy,quality,sample_customers,require_demos)
        manifest['gold'] = gold_counts
        write_json(run_dir/'demo_scenarios.json',demos)
        if require_demos:
            stage = 'backend_acceptance'
            result = subprocess.run([sys.executable,'-m','data_pipeline.verify_backend',
                '--gold',str(run_dir/'gold/gold.duckdb'),'--scenarios',str(run_dir/'demo_scenarios.json'),
                '--policy',str(run_dir/'policy.yaml'),'--report',str(run_dir/'backend_acceptance.json')],
                cwd=ROOT,capture_output=True,text=True,timeout=120)
            quality.check('gold.backend_acceptance',result.returncode != 0,
                          details='See backend_acceptance.json; isolated in-memory operational database.')
        manifest['outputs'] = {p.relative_to(run_dir).as_posix():sha256(p)
                               for folder in ('silver','gold') for p in sorted((run_dir/folder).glob('*'))}
        for table in counts:
            if table in ('transactions','complaints','call_center_interactions','satisfaction_surveys'):
                latest = con.execute(f'SELECT max(business_date) FROM {table}').fetchone()[0]
                lag = (reference-latest).days if latest else None
                quality.check(f'{table}.freshness_T1', lag if lag is not None and lag>1 else 0,
                              severity='warning',details={'max_business_date':latest,'lag_days':lag})
        con.close()
        con = None
        stage = 'publish'
        manifest['status']='success'
        manifest['finished_at']=datetime.now(timezone.utc).isoformat()
        write_json(run_dir/'quality_report.json',quality.report(run_id,'success'))
        write_json(run_dir/'manifest.json',manifest)
        publish_file(run_dir/'gold/gold_full.duckdb',data_dir/'gold/gold_full.duckdb')
        for name in ('quality_report.json','policy_calibration.json','demo_scenarios.json','backend_acceptance.json'):
            if not (run_dir/name).exists():
                continue
            publish_file(run_dir/name,reports_dir/name)
        if analysis_dir:
            publish_file(run_dir/'metricas_problema.json',Path(analysis_dir)/'metricas_problema.json')
        publish_file(run_dir/'gold/gold.duckdb',data_dir/'gold/gold.duckdb')
        write_json(data_dir/'manifest.json',manifest)
        print(f'Pipeline completo: {run_id}; gold publicado en {data_dir / "gold"}',flush=True)
        return manifest
    except Exception as exc:
        manifest.update(status='failed',stage=stage,error_type=type(exc).__name__)
        quality.checks.append({'check':stage,'severity':'error','status':'fail',
                               'error_type':type(exc).__name__})
        write_json(run_dir/'manifest.json',manifest)
        write_json(run_dir/'quality_report.json',quality.report(run_id,'failed'))
        write_json(reports_dir/'quality_report.json',quality.report(run_id,'failed'))
        raise
    finally:
        if con:
            con.close()
        lock.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--full',action='store_true')
    mode.add_argument('--incremental',action='store_true')
    p.add_argument('--since',type=date.fromisoformat)
    p.add_argument('--reprocess-days',type=int,default=3)
    p.add_argument('--start',type=date.fromisoformat,default=date(2025,7,1))
    p.add_argument('--local-source',type=Path,help='CSV mirror for offline development/fixtures; default S3.')
    p.add_argument('--data-dir',type=Path,default=ROOT/'data')
    p.add_argument('--reports-dir',type=Path,default=ROOT/'reports')
    p.add_argument('--policy',type=Path,default=ROOT/'config/policy.yaml')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--source-timezone',default='UTC',help='Explicit assumption for timestamps without offset.')
    p.add_argument('--sample-customers',type=int,default=100)
    p.add_argument('--memory-limit',default='1GB')
    p.add_argument('--allow-incomplete-demo',action='store_true',help='Fixtures/exploration only; not delivery.')
    args=p.parse_args()
    if args.incremental and not args.since:
        p.error('--incremental requiere --since')
    if args.full and args.since:
        p.error('--since solo se usa con --incremental')
    try:
        run(source=LocalSource(args.local_source) if args.local_source else S3Source(),
            data_dir=args.data_dir,reports_dir=args.reports_dir,policy_path=args.policy,
            since=args.since,reprocess_days=args.reprocess_days,start=args.start,
            workers=args.workers,source_timezone=args.source_timezone,sample_customers=args.sample_customers,
            memory_limit=args.memory_limit,require_demos=not args.allow_incomplete_demo,
            analysis_dir=ROOT/'analysis' if args.data_dir.resolve()==(ROOT/'data').resolve() else None)
    except Exception as exc:
        print(f'Pipeline detenido ({type(exc).__name__}). Revisa quality_report.json; no se muestran datos sensibles.')
        raise SystemExit(1) from None


if __name__=='__main__':
    main()
