"""Read-only sources. Secrets are loaded by the process, never logged or serialized."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

TABLES = ('customers', 'products', 'daily_exchange_rates', 'transactions',
          'complaints', 'call_center_interactions', 'satisfaction_surveys', 'service_agents')
FACTS = {'transactions', 'complaints', 'call_center_interactions', 'satisfaction_surveys'}
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SourceFile:
    key: str
    table: str
    partition: str | None
    size: int
    identity: str


def describe(key: str, size: int, identity: str) -> SourceFile | None:
    table = key.split('/')[0].removesuffix('.csv')
    if table not in TABLES or not key.endswith('.csv'):
        return None
    match = re.search(r'year=(\d{4})/month=(\d{1,2})/day=(\d{1,2})/', key)
    partition = date(*map(int, match.groups())).isoformat() if match else None
    return SourceFile(key, table, partition, size, identity)


class LocalSource:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.name = f'local:{self.root.as_posix()}'

    def inventory(self):
        result = []
        for path in sorted(self.root.rglob('*.csv')):
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            item = describe(path.relative_to(self.root).as_posix(), path.stat().st_size, digest)
            if item:
                result.append(item)
        return result

    def read(self, item: SourceFile) -> bytes:
        return (self.root / item.key).read_bytes()


class S3Source:
    def __init__(self):
        import boto3
        from botocore.config import Config
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
        self.bucket = os.environ.get('S3_BUCKET') or os.environ.get('BUCKET')
        if not self.bucket:
            raise ValueError('Falta S3_BUCKET; configura el entorno local.')
        self.prefix = os.environ.get('S3_PREFIX', 'data').strip('/')
        if self.prefix != 'data':
            raise ValueError('La fuente aprobada es S3_PREFIX=data, no el backup.')
        self.name = f's3://{self.bucket}/{self.prefix}'
        self.client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-2'),
                                   config=Config(connect_timeout=10, read_timeout=60,
                                                 retries={'max_attempts': 3, 'mode': 'standard'},
                                                 max_pool_connections=8))

    def inventory(self):
        result = []
        for page in self.client.get_paginator('list_objects_v2').paginate(
                Bucket=self.bucket, Prefix=self.prefix + '/'):
            for obj in page.get('Contents', []):
                item = describe(obj['Key'][len(self.prefix) + 1:], obj['Size'],
                                obj['ETag'].strip('"') + ':' + obj['LastModified'].isoformat())
                if item:
                    result.append(item)
        return sorted(result, key=lambda x: x.key)

    def read(self, item: SourceFile) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=f'{self.prefix}/{item.key}',
                                          IfMatch=item.identity.split(':', 1)[0])
        with response['Body'] as body:
            return body.read()
