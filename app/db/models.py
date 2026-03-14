from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, ForeignKey
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.sqlite import JSON
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    google_id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    picture = Column(String)
    interests = Column(Text)
    created_at = Column(DateTime, default=func.now())


class Paper(Base):
    __tablename__ = "papers"

    paper_id = Column(String, primary_key=True)
    title = Column(Text)
    abstract = Column(Text)
    authors = Column(Text)
    month_year = Column(String)
    category = Column(String)
    subcategory = Column(String)
    year = Column(Integer)
    source = Column(String)
    url = Column(Text)
    pdf_url = Column(Text)
    doi = Column(String)
    journal_ref = Column(Text)
    comment = Column(Text)
    extra_metadata = Column(JSON)   # ✅ renamed to avoid reserved word conflict
    embedding = Column(Text)
    popularity_score = Column(Float)
    created_at = Column(DateTime, default=func.now())


class Bookmark(Base):
    __tablename__ = "bookmarks"

    bookmark_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.google_id"))
    paper_id = Column(String, ForeignKey("papers.paper_id"))
    created_at = Column(DateTime, default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.google_id"))
    paper_id = Column(String, ForeignKey("papers.paper_id"))
    score = Column(Float)
    created_at = Column(DateTime, default=func.now())