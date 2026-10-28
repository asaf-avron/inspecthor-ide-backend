"""
Inspecthor Core Package
Contains core verification and analysis modules
"""

from core.workflow import run_triage, run_structuring
from core.auditor import SpecAuditor
from core.gateway import CodeVerifier, verify_code, VerificationResult
from core.parser import DafnyParser, parse_dafny_source, DafnyContract, Method

__all__ = [
    'run_triage',
    'run_structuring',
    'SpecAuditor',
    'CodeVerifier',
    'verify_code',
    'VerificationResult',
    'DafnyParser',
    'parse_dafny_source',
    'DafnyContract',
    'Method',
]

