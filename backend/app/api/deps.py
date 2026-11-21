import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import User

bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"code": "UNAUTHORIZED", "message": "الجلسة غير صالحة"})
    try:
        payload = decode_access_token(creds.credentials)
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, {"code": "UNAUTHORIZED", "message": "الجلسة غير صالحة"})
    return user


def require_roles(*roles: str):
    def _dep(user: User = Depends(current_user)) -> User:
        if not set(roles) & set(user.role_names()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, {"code": "FORBIDDEN", "message": "لا تملك صلاحية لهذا الإجراء"})
        return user

    return _dep
