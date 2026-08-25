"""Cookie session authentication and first-admin bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import login_rate_limiter
from app.core.security import hash_password, new_secret_token, password_needs_rehash, secure_equals, token_digest, verify_password
from app.infrastructure.db.models import User, UserSession
from app.infrastructure.db.session import get_db
from app.schemas import AuthRequest, AuthResponse, BootstrapRequest, PasswordChange, UserRead, UserSessionRead
from app.services.audit import record_audit
from app.services.trips import default_settings_for_user


router = APIRouter(prefix="/auth", tags=["auth"])


def _create_session(db: Session, user: User) -> tuple[str, UserSession]:
    settings = get_settings()
    session_value = new_secret_token()
    session = UserSession(
        user_id=user.id,
        token_hash=token_digest(session_value),
        csrf_token=new_secret_token(),
        expires_at=datetime.now(UTC) + timedelta(days=settings.session_days),
    )
    db.add(session)
    return session_value, session


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_days * 86_400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/bootstrap", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(payload: BootstrapRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    if db.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Initial administrator already exists")
    settings = get_settings()
    if settings.is_deployed:
        if not settings.bootstrap_token or not payload.bootstrap_token or not secure_equals(payload.bootstrap_token, settings.bootstrap_token):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap is not available")
    user = User(email=payload.email, password_hash=hash_password(payload.password), is_admin=True)
    db.add(user)
    db.flush()
    default_settings_for_user(db, user.id)
    token, session = _create_session(db, user)
    record_audit(db, actor_id=user.id, action="AUTH_BOOTSTRAP", resource_type="user", resource_id=user.id)
    db.commit()
    _set_cookie(response, token)
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=session.csrf_token)


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    client_host = request.client.host if request.client else "unknown"
    if not login_rate_limiter.allowed(f"{client_host}:{payload.email}"):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_audit(db, actor_id=user.id if user else None, action="AUTH_LOGIN_FAILED", resource_type="auth")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    token, session = _create_session(db, user)
    record_audit(db, actor_id=user.id, action="AUTH_LOGIN", resource_type="user", resource_id=user.id)
    db.commit()
    _set_cookie(response, token)
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=session.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    user_session: UserSession = Depends(get_current_session),
) -> None:
    record_audit(db, actor_id=user.id, action="AUTH_LOGOUT", resource_type="user", resource_id=user.id)
    db.delete(user_session)
    db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")


@router.get("/me", response_model=AuthResponse)
def me(user: User = Depends(get_current_user), user_session: UserSession = Depends(get_current_session)) -> AuthResponse:
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=user_session.csrf_token)


@router.get("/sessions", response_model=list[UserSessionRead])
def sessions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    current: UserSession = Depends(get_current_session),
) -> list[UserSessionRead]:
    raw = request.cookies.get(get_settings().cookie_name, "")
    current_hash = token_digest(raw) if raw else ""
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.created_at.desc())).all()
    return [
        UserSessionRead(
            id=row.id,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            current=row.token_hash == current_hash or row.id == current.id,
        )
        for row in rows
    ]


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def change_password(
    payload: PasswordChange,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    current: UserSession = Depends(get_current_session),
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    # Rotate every other device immediately, retaining the caller's session so
    # the browser can continue after a successful change.
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.id != current.id).delete(synchronize_session=False)
    record_audit(db, actor_id=user.id, action="AUTH_PASSWORD_CHANGE", resource_type="user", resource_id=user.id)
    db.commit()


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def revoke_all_sessions(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    # Synchronize the identity map because get_current_session loaded the
    # caller and updated last_seen_at before this bulk delete.
    db.query(UserSession).filter(UserSession.user_id == user.id).delete(synchronize_session="fetch")
    record_audit(db, actor_id=user.id, action="AUTH_REVOKE_ALL_SESSIONS", resource_type="user", resource_id=user.id)
    db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")
