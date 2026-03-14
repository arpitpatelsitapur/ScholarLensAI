from email import message

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import sqlite3
import httpx
from app.db.session import SessionLocal, SessionPapers
from app.utils.recommend import (
    recommend_by_category,
    recommend_by_query,
    load_papers,
    load_embeddings_from_db,
    load_specter2,
    align_df_with_embeddings,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

DB_PATH = "app/scholarlens.db"

# Load data & model ONCE at startup
df_raw = load_papers()
paper_ids, embeddings = load_embeddings_from_db(model_name="specter2")
df = align_df_with_embeddings(df_raw, paper_ids)

tokenizer, model, device = load_specter2()

# ---------- DB helpers ----------
def get_users_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_papers_db():
    db = SessionPapers()
    try:
        yield db
    finally:
        db.close()


# ---------- Static Pages ----------
@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/home")


@router.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("about.html", {"request": request, "user": user})



# ============================================================
#                   DB HELPERS
# ============================================================

def load_user_interests(google_id: str):
    """Return user's interests as a clean lowercase list."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT interests FROM users WHERE google_id = ?", (google_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return []   # no interests stored

    interests = row[0].split(",")
    return [i.strip().lower() for i in interests if i.strip()]


def execute_query(query: str, params=()):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        return cursor.fetchall()
    except Exception as e:
        print("SQL Error:", e)
        return []
    finally:
        conn.close()


# ============================================================
#                   INTEREST SQL BUILDER
# ============================================================

def build_interest_filter(interest_list: list):
    """
    Convert Python list into SQL IN clause:
    ['machine learning', 'deep learning'] ->
    AND LOWER(category) IN ('machine learning','deep learning')
    """
    if not interest_list:
        return ""

    values = ", ".join([f"'{i}'" for i in interest_list])
    return f" AND LOWER(category) IN ({values}) "


# ============================================================
#                   FETCH DATA
# ============================================================

def format_papers(rows):
    return [
        {
            "paper_id": r[0],
            "title": r[1],
            "authors": r[2],
            "abstract": r[3],
            "category": r[4],
            "url": r[5],
            "pdf_url": r[6],
            "month_year": r[7],
            "source": r[8],
            "tag": r[9],
        }
        for r in rows
    ]

def get_paper_by_id(paper_id: str):
    """
    Fetch a single paper from unified_papers by paper_id.
    Returns a dict compatible with format_papers output.
    """
    sql = """
        SELECT paper_id, title, authors, abstract, category, url, pdf_url,
               month_year, source, tag
        FROM unified_papers
        WHERE paper_id = ?
        LIMIT 1;
    """
    rows = execute_query(sql, (paper_id,))
    if not rows:
        return None

    papers = format_papers(rows)
    return papers[0]


def fetch_papers(extra_filter: str, interests: list, limit=20):
    interest_sql = build_interest_filter(interests)

    sql = f"""
        SELECT paper_id, title, authors, abstract, category, url, pdf_url, month_year, source, tag
        FROM unified_papers
        WHERE 1=1
        {extra_filter}
        {interest_sql}
        ORDER BY DATE(published_at) DESC
        LIMIT ?;
    """

    rows = execute_query(sql, (limit,))
    return format_papers(rows)


# ---- Category Fetchers ---- #

def fetch_new_papers(interests, limit=20):
    return fetch_papers("", interests, limit)


def fetch_must_read_papers(interests, limit=20):
    return fetch_papers("AND is_must_read = 1", interests, limit)


def fetch_arxiv_papers(interests, limit=20):
    return fetch_papers("AND source = 'arxiv'", interests, limit)


def fetch_anthropic_papers(interests, limit=20):
    return fetch_papers("AND source = 'anthropic'", interests, limit)


def fetch_ieee_papers(interests, limit=20):
    return fetch_papers("AND (source = 'ieee' OR url LIKE '%ieee%')", interests, limit)


def fetch_other_sources(interests, limit=20):
    return fetch_papers("AND source = 'others'", interests, limit)


def fetch_free_papers(interests, limit=20):
    return fetch_papers("AND tag = 'free'", interests, limit)


def fetch_not_free_papers(interests, limit=20):
    return fetch_papers("AND tag = 'not free'", interests, limit)


# ============================================================
#                       DASHBOARD ROUTE
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")

    if not user:
        # user not logged in → interests empty list
        interests = []
    else:
        interests = load_user_interests(user["id"])   # returns list

    papers_data = {
        # "recommended": fetch_new_papers(interests),
        "new": fetch_new_papers(interests),
        "must_read": fetch_must_read_papers(interests),
        "arxiv": fetch_arxiv_papers(interests),
        "anthropic": fetch_anthropic_papers(interests),
        "ieee": fetch_ieee_papers(interests),
        "others": fetch_other_sources(interests),
        "free": fetch_free_papers(interests),
        "not_free": fetch_not_free_papers(interests),
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "papers_data": papers_data},
    )

@router.post("/dashboard/filter", response_class=HTMLResponse)
async def filter_dashboard(
    request: Request,
    filter_type: str = Form(...),
    category_value: str = Form(None),
    topic_value: str = Form(None),
    max_limit: int = Form(25)
):
    user = request.session.get("user")
    interests = load_user_interests(user["id"]) if user else []

    # ================================
    # 1. RUN MODEL-BASED FILTER
    # ================================
    if filter_type == "category":
        recs = recommend_by_category(category_value, df, embeddings, top_k=max_limit)

    else:  # topic search
        recs = recommend_by_query(topic_value, df, embeddings, tokenizer, model, device, top_k=max_limit)

    # No results?
    if recs is None or recs.empty:
        filtered_results = []
    else:
        # Extract list of paper_ids
        paper_ids = recs["paper_id"].tolist()

        # ================================
        # 2. GET FULL DETAILS FROM SQL
        # ================================
        placeholders = ",".join("?" * len(paper_ids))

        sql = f"""
            SELECT paper_id, title, authors, abstract, category, url, pdf_url,
                   month_year, source, tag
            FROM unified_papers
            WHERE paper_id IN ({placeholders})
        """

        rows = execute_query(sql, tuple(paper_ids))

        # Convert rows → dict format used by dashboard tables
        filtered_results = format_papers(rows)

    # ================================
    # 3. Load full dashboard sections
    # ================================
    papers_data = {
        "new": fetch_new_papers(interests),
        "must_read": fetch_must_read_papers(interests),
        "arxiv": fetch_arxiv_papers(interests),
        "anthropic": fetch_anthropic_papers(interests),
        "ieee": fetch_ieee_papers(interests),
        "others": fetch_other_sources(interests),
        "free": fetch_free_papers(interests),
        "not_free": fetch_not_free_papers(interests),
    }

    # ================================
    # 4. Render template
    # ================================
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "papers_data": papers_data,
            "filtered_results": filtered_results,
            "filter_info": (
                f"{filter_type.capitalize()}: {category_value or topic_value} "
                f"(Limit: {max_limit})"
            ),
        },
    )


# ============================================================
#                    BOOKMARKS Working
# ============================================================

from datetime import datetime

# ==========================================
#             ADD BOOKMARK
# ==========================================
@router.get("/bookmark/add/{paper_id}")
async def add_bookmark(request: Request, paper_id: str):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    user_id = user.get("google_id") or user.get("id")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # prevent duplicate bookmarks
    cursor.execute(
        "SELECT bookmark_id FROM bookmarks WHERE user_id = ? AND paper_id = ?",
        (user_id, paper_id)
    )
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(
            "INSERT INTO bookmarks (user_id, paper_id, created_at) VALUES (?, ?, ?)",
            (user_id, paper_id, datetime.now().isoformat())
        )
        conn.commit()

    conn.close()
    return RedirectResponse("/bookmarks", status_code=302)

# ==========================================
#          REMOVE BOOKMARK
# ==========================================
@router.get("/bookmark/remove/{paper_id}")
async def remove_bookmark(request: Request, paper_id: str):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    user_id = user.get("google_id") or user.get("id")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM bookmarks WHERE user_id = ? AND paper_id = ?",
        (user_id, paper_id)
    )
    conn.commit()
    conn.close()

    return RedirectResponse("/bookmarks", status_code=302)


# ==========================================
#               VIEW BOOKMARKS
# ==========================================
@router.get("/bookmarks", response_class=HTMLResponse)
async def bookmarks(request: Request):
    user = request.session.get("user")

    if not user:
        return templates.TemplateResponse("bookmarks.html", {"request": request, "user": None})

    user_id = user.get("google_id") or user.get("id")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.paper_id, u.title, u.category, u.source, u.url, b.created_at
        FROM bookmarks b
        JOIN unified_papers u ON u.paper_id = b.paper_id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    bookmarks_list = [
        {
            "paper_id": r[0],
            "title": r[1],
            "category": r[2],
            "source": r[3],
            "url": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]

    return templates.TemplateResponse(
        "bookmarks.html",
        {"request": request, "user": user, "bookmarks": bookmarks_list},
    )


# ==========================================
#          Chat app being implemented
# ==========================================

@router.get("/chat/{paper_id}", response_class=HTMLResponse)
async def chat_paper(request: Request, paper_id: str):
    """
    Show chat UI for a specific paper.
    If pdf_url is missing, the template will show the 'sorry' message and disable chat.
    """

    user = request.session.get("user")

    # Reset chat history when opening a new paper
    request.session["chat_messages"] = []

    paper = get_paper_by_id(paper_id)

    if not paper:
        # Fallback if ID is invalid / not found
        paper = {
            "paper_id": paper_id,
            "title": "Paper not found",
            "authors": "",
            "abstract": "We could not find this paper in the database.",
            "category": "",
            "url": "",
            "pdf_url": None,
            "month_year": "",
            "source": "",
            "tag": "",
        }

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user": user,
            "paper": paper,
            "chat_messages": []   # empty chat at start
        },
    )

@router.post("/chat/{paper_id}/ask", response_class=HTMLResponse)
async def chat_paper_ask(
    request: Request,
    paper_id: str,
    message: str = Form(...),
):
    """
    Handle a chat question for a specific paper.
    RAG logic will be plugged in here later.
    """
    print("\n========== CHAT REQUEST RECEIVED ==========")
    print("Paper ID:", paper_id)
    print("User query:", message)
    print("===========================================\n")
    user = request.session.get("user")
    
    paper = get_paper_by_id(paper_id)
    if not paper:
        paper = {
            "paper_id": paper_id,
            "title": "Paper not found",
            "authors": "",
            "abstract": "We could not find this paper in the database.",
            "category": "",
            "url": "",
            "pdf_url": None,
            "month_year": "",
            "source": "",
            "tag": "",
        }

    # ---------- CALL RAG MICROSERVICE ----------

    pdf_url = paper.get("pdf_url")

    if not pdf_url or pdf_url == "N/A":
        answer = (
            "I’m sorry, but I don’t have access to this paper’s PDF."
        )

    else:
        try:
            print("\n===== CALLING RAG SERVICE =====")
            print("Paper:", paper_id)
            print("Question:", message)

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "http://127.0.0.1:8001/ask",
                    json={
                        "paper_id": paper_id,
                        "pdf_url": paper.get("pdf_url"),
                        "question": message
                    }
                )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "No answer returned.")
            else:
                answer = "RAG service returned an error."

        except Exception as e:
            print("RAG ERROR:", e)
            answer = "Could not connect to the RAG service."

    chat_messages = request.session.get("chat_messages", [])

    chat_messages.append({
        "role": "user",
        "content": message,
        "time": "Now"
    })

    chat_messages.append({
        "role": "bot",
        "content": answer,
        "time": "Now"
    })

    request.session["chat_messages"] = chat_messages

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user": user,
            "paper": paper,
            "chat_messages": chat_messages,
        },
    )
