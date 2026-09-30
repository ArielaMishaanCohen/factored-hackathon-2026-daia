"""Atomic JSON reports and reproducibility metadata (no environment values)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import importlib.metadata
import platform


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temp, path)


def code_version(root: Path) -> dict:
    def git(*args):
        result = subprocess.run(['git','-c',f'safe.directory={root.as_posix()}', '-C', str(root), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    files = sorted((root / 'data_pipeline').glob('*.py'))
    return {'git_sha': git('rev-parse', 'HEAD'),
            'pipeline_sha256': {p.name: sha256(p) for p in files},
            'python':platform.python_version(),
            'packages':{name:importlib.metadata.version(name) for name in
                        ('duckdb','pandas','pyarrow','pandera','boto3','pyyaml')},
            'note': 'File hashes identify uncommitted code; git_sha may be unavailable under Windows sandbox ownership.'}
