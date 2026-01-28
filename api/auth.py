"""
Authentication endpoints for GitHub OAuth
Handles user login, token refresh, and session management
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Cookie
from fastapi import Request as FastAPIRequest
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import httpx
import os
import logging
from jose import JWTError, jwt
from cryptography.fernet import Fernet

from api.database import get_db, User
from api.models import (
    UserResponse,
    TokenRefreshResponse,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

# Configuration from environment
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Encryption key for storing GitHub tokens
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage"""
    return cipher.encrypt(token.encode()).decode()  # type: ignore[no-any-return]


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher.decrypt(encrypted_token.encode()).decode()  # type: ignore[no-any-return]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)  # type: ignore[no-any-return]


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)  # type: ignore[no-any-return]


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != token_type:
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload  # type: ignore[no-any-return]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from access token cookie"""
    if not access_token:
        return None
    
    try:
        payload = verify_token(access_token, "access")
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = db.query(User).filter(User.user_id == user_id).first()
        return user
    except HTTPException:
        return None


async def require_auth(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
) -> User:
    """Require authentication - raise 401 if not authenticated"""
    user = await get_current_user(access_token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/github")
async def github_oauth_redirect():
    """
    Redirect to GitHub OAuth authorization page.
    This should be opened in a popup or new tab.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID environment variable."
        )
    
    # GitHub OAuth authorization URL
    scopes = "read:user user:email repo workflow"
    # Callback URL should point to frontend API route (which proxies to backend)
    # This allows cookies to be set on the frontend domain
    redirect_uri = f"{FRONTEND_URL}/api/auth/github/callback"
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state=random_state_string"  # TODO: Implement CSRF protection
    )
    
    return {"authorization_url": github_auth_url}


@router.get("/github/callback")
async def github_oauth_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    state: Optional[str] = None,
    response: Response = None,
    request: FastAPIRequest = None,
    db: Session = Depends(get_db)
):
    """
    GitHub OAuth callback handler.
    Exchanges code for access token and creates/updates user.
    """
    # Handle OAuth errors from GitHub
    if error:
        logger.error(f"GitHub OAuth error: {error} - {error_description}")
        redirect_url = f"{FRONTEND_URL}/auth/github/callback?auth=error&error={error}"
        return RedirectResponse(url=redirect_url)
    
    if not code:
        logger.error("GitHub OAuth callback missing code parameter")
        redirect_url = f"{FRONTEND_URL}/auth/github/callback?auth=error&error=missing_code"
        return RedirectResponse(url=redirect_url)
    
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth not configured"
        )
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Failed to exchange code for token"
            )
        
        token_data = token_response.json()
        github_access_token = token_data.get("access_token")
        
        if not github_access_token:
            raise HTTPException(
                status_code=400,
                detail="No access token in GitHub response"
            )
        
        # Get user info from GitHub
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_access_token}",
                "Accept": "application/json"
            }
        )
        
        if user_response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Failed to fetch user info from GitHub"
            )
        
        github_user = user_response.json()
        github_id = github_user.get("id")
        github_login = github_user.get("login")
        email = github_user.get("email")
        avatar_url = github_user.get("avatar_url")
        
        # Create or update user in database
        user = db.query(User).filter(User.github_id == github_id).first()
        
        if user:
            # Update existing user
            user.github_login = github_login
            user.email = email
            user.avatar_url = avatar_url
            user.access_token_encrypted = encrypt_token(github_access_token)  # type: ignore[assignment]
            user.last_login_at = datetime.utcnow()  # type: ignore[assignment]
            user.updated_at = datetime.utcnow()  # type: ignore[assignment]
        else:
            # Create new user
            user = User(
                github_id=github_id,
                github_login=github_login,
                email=email,
                avatar_url=avatar_url,
                access_token_encrypted=encrypt_token(github_access_token),
                tier='free',
                verification_credits=10,
                last_login_at=datetime.utcnow()
            )
            db.add(user)
        
        db.commit()
        db.refresh(user)
        
        # Create JWT tokens
        token_data = {
            "sub": str(user.user_id),
            "github_id": user.github_id,
            "github_login": user.github_login,
            "tier": user.tier,
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Set cookies
        # Note: For cross-origin cookies (localhost:8000 -> localhost:3000),
        # we need samesite="none" and secure=True, but since we're on HTTP in dev,
        # we use samesite="lax" which works for same-site redirects
        # The cookies will be sent with credentials: 'include' from frontend
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # Allow HTTP in development (localhost)
            samesite="lax",  # Allow cross-site cookies for OAuth flow
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",  # Make cookie available for all paths
        )
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,  # Allow HTTP in development (localhost)
            samesite="lax",  # Allow cross-site cookies for OAuth flow
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/",  # Make cookie available for all paths
        )
        
        logger.info(f"Set authentication cookies for user {user.github_login}")
        
        # If request is from Next.js API route proxy, return JSON with tokens
        # Otherwise redirect (for direct access)
        if request and request.headers.get("x-proxy-request") == "true":
            # Return tokens for frontend API route to set cookies
            from fastapi.responses import JSONResponse
            return JSONResponse({
                "status": "success",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {
                    "user_id": str(user.user_id),
                    "github_id": user.github_id,
                    "github_login": user.github_login,
                    "email": user.email,
                    "avatar_url": user.avatar_url,
                    "tier": user.tier,
                }
            })
        
        # Redirect to frontend callback page (which will close popup and notify parent)
        redirect_url = f"{FRONTEND_URL}/auth/github/callback?auth=success"
        return RedirectResponse(url=redirect_url)


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    refresh_token: Optional[str] = Cookie(None),
    response: Response = None,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    Returns new access token.
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    user_id = payload.get("sub")
    
    # Get user from database
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Create new access token
    token_data = {
        "sub": str(user.user_id),
        "github_id": user.github_id,
        "github_login": user.github_login,
        "tier": user.tier,
    }
    
    new_access_token = create_access_token(token_data)
    
    # Set new access token cookie
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=False,  # Allow HTTP in development
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return TokenRefreshResponse(
        access_token=new_access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout user by clearing cookies.
    """
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(require_auth)
):
    """
    Get current authenticated user information.
    """
    return UserResponse(
        user_id=str(current_user.user_id),
        github_id=current_user.github_id,
        github_login=current_user.github_login,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
        tier=current_user.tier,
        verification_credits=current_user.verification_credits,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )
