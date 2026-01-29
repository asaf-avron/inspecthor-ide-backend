"""
Dafny Verification Service

A stateless, isolated microservice that performs formal verification
using Dafny and Z3. This service has no external network access,
no database connections, and no credentials.

It receives specification and implementation code, runs verification,
and returns the result.
"""
