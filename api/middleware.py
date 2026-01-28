"""
API Security Middleware for Guardian Gateway
Provides authentication, rate limiting, and request logging
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, List
import os
import logging

logger = logging.getLogger(__name__)


class SecurityScannerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to block security scanners and malicious requests early.
    Runs before other middleware to eliminate scanner traffic.
    """
    
    def __init__(self, app):
        super().__init__(app)
        
        # Legitimate API paths - only these should be allowed
        self.allowed_paths = {
            "/api/health",
            "/api/generate/spec",
            "/api/generate/find-gaps",
            "/api/generate/refine-spec",
            "/api/verify/dafny",
            "/api/assistant/chat",
            "/api/files",
            "/api/projects",
            "/api/deconstruct",
            "/api/verification",
            "/api/auth",
            "/api/github/webhooks",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        
        # Suspicious patterns that indicate security scanners
        self.suspicious_patterns = [
            "jndi:",
            "struts2",
            "struts",
            "cgi-bin",
            "wp-admin",
            "wp-content",
            "phpmyadmin",
            ":undefined",
            "webtools",
            "broker/xml",
            "portal/info",
            "analytics/telemetry",
            "token/transfer",
            "index.action",
            ".jsp",
            ".php",
            ".asp",
            ".aspx",
        ]
        
        # Suspicious query parameters
        self.suspicious_query_patterns = [
            "jndi:",
            "${",
            "%24%7B",  # URL-encoded ${ 
        ]
    
    def _is_allowed_path(self, path: str) -> bool:
        """Check if path is a legitimate API endpoint."""
        # ALLOW ALL API ENDPOINTS
        if path.startswith("/api/"):
            return True
        
        # Check exact matches for non-API paths (docs, health, etc.)
        if path in self.allowed_paths:
            return True
        
        # Check if it starts with an allowed non-API prefix
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True
        
        return False
    
    def _is_suspicious(self, request: Request) -> tuple[bool, str]:
        """
        Check if request is suspicious.
        Returns (is_suspicious, reason)
        """
        path = request.url.path.lower()
        query = str(request.url.query).lower()
        
        # Block non-API paths (except public endpoints)
        if not self._is_allowed_path(request.url.path):
            # Allow root path (might be health check or redirect)
            if path == "/":
                return False, ""
            return True, f"Non-API path: {request.url.path}"
        
        # Check for suspicious patterns in path
        for pattern in self.suspicious_patterns:
            if pattern in path:
                return True, f"Suspicious pattern in path: {pattern}"
        
        # Check for suspicious patterns in query string
        for pattern in self.suspicious_query_patterns:
            if pattern in query:
                return True, f"Suspicious pattern in query: {pattern}"
        
        return False, ""
    
    async def dispatch(self, request: Request, call_next):
        # Check if request is suspicious
        is_suspicious, reason = self._is_suspicious(request)
        
        if is_suspicious:
            client_host = request.client.host if request.client else "unknown"
            logger.warning(
                f"[SECURITY] Blocked scanner request: {request.method} {request.url.path} "
                f"from {client_host} - Reason: {reason}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden"}
            )
        
        return await call_next(request)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate API keys OR JWT tokens for protected endpoints.
    Supports both authentication methods for backward compatibility.
    """
    
    def __init__(self, app, allowed_keys: Optional[list[str]] = None):
        super().__init__(app)
        # Get allowed API keys from environment variable
        env_keys = os.getenv("ALLOWED_API_KEYS", "")
        self.allowed_keys = set(allowed_keys or [])
        
        if env_keys:
            self.allowed_keys.update(key.strip() for key in env_keys.split(",") if key.strip())
        
        # Public endpoints that don't require authentication
        self.public_paths = {
            "/api/health", 
            "/docs", 
            "/redoc", 
            "/openapi.json",
            "/api/auth/github",
            "/api/auth/github/callback",
            "/api/github/webhooks",  # GitHub webhooks use signature verification, not API keys
        }
    
    async def dispatch(self, request: Request, call_next):
        # Allow OPTIONS requests (CORS preflight) without authentication
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Allow public endpoints
        if request.url.path in self.public_paths:
            return await call_next(request)
        
        # Allow auth endpoints
        if request.url.path.startswith("/api/auth/"):
            return await call_next(request)
        
        # Check for JWT token in cookie (user logged in)
        access_token = request.cookies.get("access_token")
        if access_token:
            # JWT authentication - let the endpoint handler validate
            return await call_next(request)
        
        # Check for API key in header (for CI/CD or programmatic access)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            if api_key not in self.allowed_keys:
                client_host = request.client.host if request.client else "unknown"
                logger.warning(f"Invalid API key attempt from {client_host}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Invalid API key"}
                )
            # Valid API key, proceed
            return await call_next(request)
        
        # ANONYMOUS ACCESS: Allow local-first usage without authentication
        # GitHub operations will be blocked at the endpoint level if not authenticated
        # This enables the "lazy authentication" pattern
        client_host = request.client.host if request.client else "unknown"
        logger.debug(f"Anonymous request from {client_host} to {request.url.path}")
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware based on IP address.
    Limits requests per minute per IP.
    Excludes health checks, public endpoints, and localhost from rate limiting.
    """
    
    def __init__(self, app, requests_per_minute: int = 300):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, List[datetime]] = defaultdict(list)
        
        # Endpoints excluded from rate limiting
        self.excluded_paths = {
            "/api/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        
        # IPs excluded from rate limiting (localhost for development)
        self.excluded_ips = {
            "127.0.0.1",
            "localhost",
            "::1",
        }
    
    def _is_localhost(self, client_ip: str) -> bool:
        """Check if client IP is localhost."""
        return client_ip in self.excluded_ips or client_ip.startswith("127.") or client_ip.startswith("::1")
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        # Skip rate limiting for excluded paths
        if path in self.excluded_paths:
            return await call_next(request)
        
        # Skip rate limiting for localhost (development)
        if self._is_localhost(client_ip):
            return await call_next(request)
        
        # Skip rate limiting for authenticated users (they have API keys or JWT tokens)
        # Check for API key or JWT token
        has_api_key = request.headers.get("X-API-Key")
        has_jwt = request.cookies.get("access_token")
        if has_api_key or has_jwt:
            return await call_next(request)
        
        now = datetime.now()
        
        # Clean old requests (older than 1 minute)
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip]
            if now - req_time < timedelta(minutes=1)
        ]
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            logger.warning(
                f"Rate limit exceeded for {client_ip}: {len(self.request_counts[client_ip])} requests in the last minute"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute."
                }
            )
        
        # Add current request
        self.request_counts[client_ip].append(now)
        
        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all incoming requests for monitoring and debugging.
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        path = request.url.path
        
        # Skip logging for health checks (too noisy)
        if path == "/api/health":
            try:
                response = await call_next(request)
                return response
            except Exception as e:
                logger.error(f"Exception in health check: {e}", exc_info=True)
                raise
        
        # Log request
        client_host = request.client.host if request.client else "unknown"
        logger.info(f"Request: {request.method} {path} from {client_host}")
        
        try:
            response = await call_next(request)
            
            # Log response
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Response: {request.method} {path} "
                f"status={response.status_code} duration={duration:.3f}s"
            )
            
            return response
        except Exception as e:
            # Log exception before re-raising (will be caught by global exception handler)
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Exception in {request.method} {path} after {duration:.3f}s: "
                f"{type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise
