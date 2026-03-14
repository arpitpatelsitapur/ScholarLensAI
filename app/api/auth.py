from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import User

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/login")
async def login():
    google_auth_url = (
        f"{settings.GOOGLE_AUTH_ENDPOINT}"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
    )
    return RedirectResponse(google_auth_url)


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, db: Session = Depends(get_db)):
    if not code:
        return RedirectResponse("/home")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(settings.GOOGLE_TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        })
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        user_resp = await client.get(
            settings.GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_data = user_resp.json()

    request.session["user"] = user_data

    existing_user = db.query(User).filter(User.email == user_data.get("email")).first()
    if not existing_user and user_data.get("email"):
        new_user = User(
            google_id=user_data.get("id"),
            name=user_data.get("name"),
            email=user_data.get("email"),
            picture=user_data.get("picture")
        )
        db.add(new_user)
        db.commit()

    return RedirectResponse("/profile")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/home")