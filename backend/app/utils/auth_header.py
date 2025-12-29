from __future__ import annotations

from fastapi import HTTPException


def extract_bearer_token(authorization: str | None) -> str:
    """Extract bearer token from Authorization header.

    Behavior (must remain stable):
    - Missing/invalid header => raise 401 UNAUTHENTICATED with message "未登录"
    - Accept case-insensitive "Bearer"
    - Strip whitespace around token
    """

    if not authorization:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "未登录"})
    return parts[1].strip()


