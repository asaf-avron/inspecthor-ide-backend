"""
Functional Core module for Inspecthor.
Contains pure Python logic matching Dafny Functional Core specifications.

This module implements the "Functional Core / Imperative Shell" architecture:
- Core: Pure functions with no side effects (matches Dafny specs)
- Shell: I/O operations (database, HTTP) handled in api/*.py routers
"""
