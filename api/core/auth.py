"""
ESGPilot — Authentication & authorisation utilities.
JWT tokens, API key verification, role-based access control.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from api.core.config import get_settings
from api.models.schemas import TokenPayload

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


# ──────────────────────────────────────────────
# Password hashing
# ──────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ──────────────────────────────────────────────
# API key hashing
# ──────────────────────────────────────────────

def hash_api_key(key: str) -> str:
    """Hash a tenant API key for storage."""
    return pwd_context.hash(key + settings.api_key_salt)


def verify_api_key(key: str, hashed: str) -> bool:
    return pwd_context.verify(key + settings.api_key_salt, hashed)


def generate_api_key() -> str:
    """Generate a new tenant API key."""
    return f"pk_live_{uuid.uuid4().hex}"


# ──────────────────────────────────────────────
# JWT tokens
# ──────────────────────────────────────────────

def create_session_token(
    tenant_id: str,
    user_id: str,
    role: str,
    entity_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> tuple[str, datetime]:
    """Create a short-lived JWT session token (15-min default)."""
    expires = datetime.utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "entity_id": entity_id,
        "project_id": project_id,
        "exp": expires,
        "iat": datetime.utcnow(),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return TokenPayload(
            tenant_id=payload["tenant_id"],
            user_id=payload["sub"],
            role=payload["role"],
            entity_id=payload.get("entity_id"),
            project_id=payload.get("project_id"),
            exp=datetime.fromtimestamp(payload["exp"]),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────────
# FastAPI dependencies
# ──────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> TokenPayload:
    """Extract and validate the current user from JWT."""
    token = credentials.credentials

    # Dev/demo mode — accept the demo token without DB validation
    if token in ("demo_token_offline", "demo_key"):
        return TokenPayload(
            tenant_id="demo_tenant",
            user_id="demo_user",
            role="project_user",
            entity_id=None,
            project_id=None,
            exp=datetime(2099, 1, 1),
        )

    token_data = decode_token(token)
    if token_data.exp < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    return token_data


def require_role(*roles: str):
    """Factory for role-based access control dependency."""
    async def _check(user: TokenPayload = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorised. Required: {roles}",
            )
        return user
    return _check


def scope_to_tenant(user: TokenPayload):
    """Return tenant-scoping filters based on user role."""
    filters = {"tenant_id": user.tenant_id}
    if user.role == "project_user" and user.project_id:
        filters["project_id"] = user.project_id
    elif user.role == "entity_admin" and user.entity_id:
        filters["entity_id"] = user.entity_id
    return filters
