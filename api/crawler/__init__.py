"""
Code crawling module for InSpecThor.
Extracts execution slices from anchored functions.
"""

from .python_crawler import PythonCrawler, ExecutionSlice

__all__ = ['PythonCrawler', 'ExecutionSlice']
