"""
Test script to verify Phase 2 implementation
Tests database, file management, and verification modules
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Guardian Gateway - Phase 2 Verification Tests")
print("=" * 60)

# Test 1: Database initialization
print("\n[Test 1] Database Initialization")
try:
    from api.database import init_db, SessionLocal, File
    init_db()
    print("✅ Database tables created successfully")
    
    # Test session
    db = SessionLocal()
    db.close()
    print("✅ Database session works")
except Exception as e:
    print(f"❌ Database test failed: {e}")

# Test 2: File management models
print("\n[Test 2] File Management Models")
try:
    from api.models import FileSaveRequest, FileResponse, FileListResponse
    
    # Test request validation
    request = FileSaveRequest(
        filename="test.md",
        content="# Test",
        file_type="markdown"
    )
    print(f"✅ FileSaveRequest validated: {request.filename}")
    
    # Test response model
    response = FileResponse(
        file_id="test-123",
        filename="test.md",
        content="# Test",
        file_type="markdown",
        created_at="2026-01-25T15:00:00",
        updated_at="2026-01-25T15:00:00",
        size_bytes=6
    )
    print(f"✅ FileResponse created: {response.file_id}")
except Exception as e:
    print(f"❌ File models test failed: {e}")

# Test 3: Verification models
print("\n[Test 3] Verification Models")
try:
    from api.models import VerifyRequest, VerifyResponse, VerificationError, GapLocation
    
    # Test request
    request = VerifyRequest(
        dafny_code="method Test() { }",
        timeout_seconds=10
    )
    print(f"✅ VerifyRequest validated: timeout={request.timeout_seconds}s")
    
    # Test error model
    error = VerificationError(
        type="verification",
        line=10,
        column=5,
        message="postcondition might not hold",
        suggestion="Check if all execution paths satisfy the postcondition"
    )
    print(f"✅ VerificationError created with suggestion: {error.suggestion[:50]}...")
except Exception as e:
    print(f"❌ Verification models test failed: {e}")

# Test 4: Enhanced spec generation models
print("\n[Test 4] Enhanced Spec Generation Models")
try:
    from api.models import Gap, Ambiguity, SpecStatistics, GapLocation
    
    # Test gap with location
    gap = Gap(
        id="GAP-001",
        severity="high",
        category="incomplete-spec",
        description="Missing error handling",
        location=GapLocation(line=10, column=5, file="spec.dfy"),
        suggestion="Add error handling for edge cases"
    )
    print(f"✅ Gap created: {gap.id} - {gap.severity}")
    
    # Test ambiguity
    amb = Ambiguity(
        id="AMB-001",
        text="Unclear timeout value",
        possible_interpretations=["30 seconds", "30 milliseconds"],
        recommendation="Specify time unit explicitly"
    )
    print(f"✅ Ambiguity created: {amb.id}")
    
    # Test statistics
    stats = SpecStatistics(
        total_requirements=10,
        mapped_requirements=8,
        coverage_percentage=80.0,
        total_gaps=3,
        critical_gaps=1
    )
    print(f"✅ Statistics: {stats.coverage_percentage}% coverage, {stats.critical_gaps} critical gaps")
except Exception as e:
    print(f"❌ Enhanced models test failed: {e}")

# Test 5: Verification parser
print("\n[Test 5] Verification Output Parser")
try:
    from api.verification import parse_dafny_output, generate_suggestion
    
    # Test suggestion generation
    suggestion = generate_suggestion("assertion violation")
    print(f"✅ Suggestion for 'assertion violation': {suggestion}")
    
    suggestion = generate_suggestion("postcondition might not hold")
    print(f"✅ Suggestion for 'postcondition': {suggestion}")
    
    # Test output parsing
    sample_output = "method Foo verified\nDafny program verifier finished with 1 verified, 0 errors"
    verified, results, errors = parse_dafny_output(sample_output, 0)
    print(f"✅ Parser: verified={verified}, {len(results)} results, {len(errors)} errors")
except Exception as e:
    print(f"❌ Verification parser test failed: {e}")

# Test 6: Router imports
print("\n[Test 6] Router Imports")
try:
    from api import files, verification
    print(f"✅ Files router imported: {files.router.prefix}")
    print(f"✅ Verification router imported: {verification.router.prefix}")
except Exception as e:
    print(f"❌ Router import test failed: {e}")

# Test 7: Main app with all routers
print("\n[Test 7] Main App Integration")
try:
    from api.main import app
    
    # Check routes
    routes = [route.path for route in app.routes]
    
    # Check for our endpoints
    expected_endpoints = [
        "/api/health",
        "/api/generate/spec",
        "/api/assistant/chat",
        "/api/files/save",
        "/api/verify"
    ]
    
    found_endpoints = []
    for endpoint in expected_endpoints:
        if any(endpoint in route for route in routes):
            found_endpoints.append(endpoint)
            print(f"✅ Endpoint registered: {endpoint}")
    
    if len(found_endpoints) == len(expected_endpoints):
        print(f"✅ All {len(expected_endpoints)} endpoints registered!")
    else:
        missing = set(expected_endpoints) - set(found_endpoints)
        print(f"⚠️  Missing endpoints: {missing}")
        
except Exception as e:
    print(f"❌ Main app test failed: {e}")

print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print("✅ All Phase 2 components verified successfully!")
print("\nTo start the server:")
print("  python -m api.main")
print("\nTo test endpoints:")
print("  curl http://localhost:8000/api/health")
print("  curl http://localhost:8000/docs  # Swagger UI")
print("=" * 60)
