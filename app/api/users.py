# app/api/users.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import User
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Profile Page ----------
@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("profile.html", {"request": request, "user": None})

    db_user = db.query(User).filter(User.email == user["email"]).first()
    if not db_user or not db_user.interests:
        return templates.TemplateResponse("profile.html", {"request": request, "user": db_user, "new_user": True})

    return templates.TemplateResponse("profile.html", {"request": request, "user": db_user, "new_user": False})


# ---------- Save Interests + Generate Recommendations ----------
@router.post("/profile/save")
async def save_profile(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    interests = form.getlist("interests")

    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)

    db_user = db.query(User).filter(User.email == user["email"]).first()
    if db_user:
        db_user.interests = ", ".join(interests)
        db.commit()

    user_id = user.get("google_id") or user.get("id")
    if user_id:
        print(f"🔁 Generating recommendations for user_id: {user_id}")
        # generate_recommendations_sql(user_id, top_k=15)
    else:
        print("⚠️ No valid user_id found, skipping recommendation generation.")

    return RedirectResponse("/profile", status_code=303)


@router.get("/profile/edit_interests", response_class=HTMLResponse)
async def edit_interests(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)

    db_user = db.query(User).filter(User.email == user["email"]).first()
    if not db_user:
        return RedirectResponse("/profile", status_code=303)

    # Convert "ML, DL, Cybersecurity" → ["ml", "dl", "cybersecurity"]
    current_interests = []
    if db_user.interests:
        current_interests = [i.strip() for i in db_user.interests.split(",")]

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": db_user,
            "edit_mode": True,
            "selected_interests": current_interests,
        }
    )

@router.post("/profile/save/ajax")
async def save_profile_ajax(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    interests = data.get("interests", [])

    user = request.session.get("user")
    if not user:
        return JSONResponse({"status": "error", "message": "Not logged in"}, status_code=401)

    db_user = db.query(User).filter(User.email == user["email"]).first()
    if not db_user:
        return JSONResponse({"status": "error", "message": "User not found"}, status_code=404)

    # Save interests
    db_user.interests = ", ".join(interests)
    db.commit()

    # OPTIONAL: regenerate recommendations
    user_id = user.get("google_id") or user.get("id")
    if user_id:
        from app.utils.recommend import generate_recommendations_sql
        generate_recommendations_sql(user_id, top_k=15)

    return JSONResponse({
        "status": "success",
        "saved_interests": interests
    })


