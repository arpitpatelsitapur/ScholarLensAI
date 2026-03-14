from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

DATABASE_URL = "sqlite:///./app/scholarlens.db"

# Single SQLite file for this demo. We expose two engine variables (engine_users,
# engine_papers) to match the usage in `app.main` and allow separate sessionmakers
# (SessionLocal for users, SessionPapers for papers). Both engines point to the
# same DB file by default to keep the setup simple.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Backwards-compatible names expected elsewhere in the codebase
engine_users = engine
engine_papers = engine

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_users)
SessionPapers = sessionmaker(autocommit=False, autoflush=False, bind=engine_papers)