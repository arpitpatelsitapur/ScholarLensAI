import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-for-dev")

    # OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

    # Google endpoints
    GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
    GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v1/userinfo"

    # Databases
    USERS_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./app/users.db")
    PAPERS_DB_URL = os.getenv("PAPERS_DATABASE_URL", "sqlite:///./app/papers.db")

settings = Settings()