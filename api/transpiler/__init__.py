"""
Transpiler module for InSpecThor.
Deterministic AST-to-Dafny (Verification Bridge) and optional LLM-based transpiler.
"""

from .ast_to_dafny import transpile_python_to_dafny, TranspileResult
from .gemini import GeminiTranspiler
from .merger import DafnyMerger

__all__ = [
    'transpile_python_to_dafny',
    'TranspileResult',
    'GeminiTranspiler',
    'DafnyMerger',
]
