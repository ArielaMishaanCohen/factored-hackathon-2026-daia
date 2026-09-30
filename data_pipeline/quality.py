"""Structured, count-only checks. Failure details never contain source row values."""
from dataclasses import dataclass, field


class QualityError(ValueError):
    pass


@dataclass
class Quality:
    checks: list = field(default_factory=list)

    def check(self, name, failures, *, severity='error', total=None, details=None):
        failures = int(failures or 0)
        self.checks.append({'check': name, 'severity': severity,
                            'status': 'pass' if not failures else ('fail' if severity == 'error' else 'warn'),
                            'failures': failures, 'total': total, 'details': details})
        if failures and severity == 'error':
            raise QualityError(f'{name}: {failures} incumplimientos')

    def report(self, run_id, status):
        return {'run_id': run_id, 'status': status, 'checks': self.checks}
