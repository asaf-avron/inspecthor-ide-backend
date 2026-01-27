"""
Transpiler module for InSpecThor.
Converts Python/TypeScript code to Dafny using LLM.
"""

from .gemini import GeminiTranspiler
from .merger import DafnyMerger

__all__ = ['GeminiTranspiler', 'DafnyMerger']
