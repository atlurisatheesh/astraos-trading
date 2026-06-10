"""AstraOS Router — Authentication (register, login, refresh, me)."""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..core.config import get_settings
from ..models.user import User
from ..schemas import (
    MessageResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive JWT tokens."""
    from ..core.account_lockout import lockout_service

    # Check lockout BEFORE anything else
    if lockout_service.is_locked(data.email):
        remaining = lockout_service.remaining_lockout_seconds(data.email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {remaining} seconds.",
        )

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        # Record failure
        is_locked, remaining_attempts = lockout_service.record_failure(data.email)
        detail = "Invalid email or password"
        if is_locked:
            detail = "Account locked due to too many failed attempts. Try again in 15 minutes."
        elif remaining_attempts > 0:
            detail = f"Invalid email or password. {remaining_attempts} attempt(s) remaining."
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Success — clear lockout counter
    lockout_service.record_success(data.email)

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for new access + refresh tokens."""
    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.post("/forgot-password")
async def forgot_password(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset.

    If SMTP is configured, a reset link is emailed to the user.
    Otherwise (dev mode) the reset token is returned directly so the
    frontend can complete the flow without an email provider.
    Always responds with the same message regardless of whether the
    email exists, to avoid account enumeration.
    """
    from ..services import email_service

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    generic = {"message": "If that email is registered, a reset link has been sent."}
    if not user:
        return generic

    token = create_reset_token(str(user.id))

    if email_service.is_configured():
        import os
        frontend = os.getenv("FRONTEND_URL", "https://web-livid-one-87.vercel.app")
        link = f"{frontend}/reset-password?token={token}"
        html = f"""
        <div style="font-family:'Segoe UI',sans-serif; max-width:480px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
          <div style="background:linear-gradient(135deg,#638cff,#a78bfa); padding:16px 24px;">
            <h2 style="margin:0; color:white;">Reset your Quantus password</h2>
          </div>
          <div style="padding:24px;">
            <p>We received a request to reset your password. This link expires in 15 minutes.</p>
            <p style="margin:20px 0;"><a href="{link}" style="background:#638cff; color:#fff; padding:12px 24px; border-radius:8px; text-decoration:none;">Reset Password</a></p>
            <p style="font-size:12px; color:#888;">If you didn't request this, you can safely ignore this email.</p>
          </div>
        </div>
        """
        await email_service.send_email("Reset your Quantus AI password", html, to=user.email)
        return generic

    # Dev mode — no SMTP configured: return the token so the UI can proceed.
    return {**generic, "dev_mode": True, "reset_token": token}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    token: str = Body(..., embed=True),
    new_password: str = Body(..., embed=True, min_length=8),
    db: AsyncSession = Depends(get_db),
):
    """Set a new password using a valid reset token."""
    payload = decode_token(token)

    if payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(new_password)
    await db.flush()

    from ..core.security import revoke_token
    if payload.get("jti"):
        revoke_token(payload["jti"])  # single-use token

    return MessageResponse(message="Password reset successful. You can now log in.")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return current_user


@router.post("/google", response_model=TokenResponse)
async def google_login(
    id_token: str = Body(..., embed=True),
    notification_preferences: dict | None = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Login or register via Google OAuth.
    
    The frontend sends the Google ID token after the user
    consents with the Google Sign-In button. We verify it with
    Google's API and create/login the user.
    """
    # Verify the Google ID token
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}",
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid Google token",
                    )
                google_data = await resp.json()
    except aiohttp.ClientError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to verify Google token",
        )

    # Validate audience (client ID must match)
    if get_settings().google_client_id and google_data.get("aud") != get_settings().google_client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token audience mismatch",
        )

    google_id = google_data.get("sub")
    email = google_data.get("email")
    full_name = google_data.get("name", email.split("@")[0] if email else "User")
    avatar_url = google_data.get("picture", "")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    # Check if user already exists (by google_id or email)
    result = await db.execute(
        select(User).where((User.google_id == google_id) | (User.email == email))
    )
    user = result.scalar_one_or_none()

    # Default notification preferences (email always ON for Gmail login)
    default_prefs = {
        "email": True,
        "telegram": False,
        "whatsapp": False,
        "telegram_chat_id": "",
        "whatsapp_number": "",
    }
    prefs = {**default_prefs, **(notification_preferences or {})}

    if not user:
        # Auto-register via Google
        import uuid
        user = User(
            email=email,
            password_hash=hash_password(uuid.uuid4().hex + "Aa1!"),  # random placeholder
            full_name=full_name,
            google_id=google_id,
            avatar_url=avatar_url,
            notification_preferences=prefs,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    else:
        # Update Google info + prefs on existing user
        if not user.google_id:
            user.google_id = google_id
        user.avatar_url = avatar_url
        user.notification_preferences = prefs
        await db.flush()

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.put("/notifications")
async def update_notification_preferences(
    preferences: dict = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's notification channel preferences.
    
    Example body:
    {
        "preferences": {
            "email": true,
            "telegram": true,
            "whatsapp": true,
            "telegram_chat_id": "123456789",
            "whatsapp_number": "+919876543210"
        }
    }
    """
    current_prefs = current_user.notification_preferences or {}
    current_prefs.update(preferences)
    current_user.notification_preferences = current_prefs
    await db.flush()
    await db.refresh(current_user)
    return {"message": "Notification preferences updated", "preferences": current_prefs}
