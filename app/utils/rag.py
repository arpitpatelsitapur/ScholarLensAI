# ==========================================================
# SCHOLARLENS RAG ENGINE (MULTI PAPER)
# ==========================================================

import os
import json
from pathlib import Path
import requests
import fitz
import numpy as np
import pandas as pd
import faiss

from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------
# CONFIG
# ----------------------------------------------------------

BASE_RAG_DIR = Path("app/rag_store")
BASE_RAG_DIR.mkdir(exist_ok=True)

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 4
MAX_CHARS_PER_CHUNK = 1000

GROQ_MODEL = "llama-3.1-8b-instant"
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

embedder = SentenceTransformer(EMBED_MODEL)

# ----------------------------------------------------------
# HELPERS
# ----------------------------------------------------------

def paper_dir(paper_id: str):
    d = BASE_RAG_DIR / paper_id
    d.mkdir(exist_ok=True)
    return d


def download_pdf(pdf_url: str, path: Path):
    if path.exists():
        return

    r = requests.get(pdf_url, stream=True, timeout=30)
    r.raise_for_status()

    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


# ----------------------------------------------------------
# TEXT EXTRACTION
# ----------------------------------------------------------

def extract_pages(pdf_path: Path, pages_json: Path):
    if pages_json.exists():
        return

    doc = fitz.open(pdf_path)
    pages = []

    for i in range(len(doc)):
        pages.append({
            "page": i + 1,
            "text": doc[i].get_text("text").replace("-\n", "")
        })

    json.dump(pages, open(pages_json, "w"), indent=2)


# ----------------------------------------------------------
# CHUNKING
# ----------------------------------------------------------

def create_chunks(pages_json, chunks_path):
    if chunks_path.exists():
        return

    pages = json.load(open(pages_json))
    chunks = []

    for p in pages:
        text = p["text"]

        for part in text.split("\n\n"):
            part = part.strip()
            if not part:
                continue

            chunks.append({
                "text": part[:MAX_CHARS_PER_CHUNK],
                "page": p["page"]
            })

    pd.DataFrame(chunks).to_parquet(chunks_path, index=False)


# ----------------------------------------------------------
# FAISS BUILD
# ----------------------------------------------------------

def build_index(chunks_path, index_path):
    if index_path.exists():
        return

    df = pd.read_parquet(chunks_path)

    emb = embedder.encode(
        df["text"].tolist(),
        convert_to_numpy=True,
        show_progress_bar=False
    )

    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)

    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(emb.astype(np.float32))

    faiss.write_index(index, str(index_path))


# ----------------------------------------------------------
# SETUP PIPELINE
# ----------------------------------------------------------

def ensure_rag_ready(paper_id: str, pdf_url: str):
    pdir = paper_dir(paper_id)

    pdf_path = pdir / "paper.pdf"
    pages_json = pdir / "pages.json"
    chunks_path = pdir / "chunks.parquet"
    index_path = pdir / "faiss.index"

    download_pdf(pdf_url, pdf_path)
    extract_pages(pdf_path, pages_json)
    create_chunks(pages_json, chunks_path)
    build_index(chunks_path, index_path)


# ----------------------------------------------------------
# RETRIEVE
# ----------------------------------------------------------

def retrieve(paper_id: str, query: str):
    pdir = paper_dir(paper_id)

    df = pd.read_parquet(pdir / "chunks.parquet")
    index = faiss.read_index(str(pdir / "faiss.index"))

    q_emb = embedder.encode([query], convert_to_numpy=True)
    q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)

    scores, idx = index.search(q_emb.astype(np.float32), TOP_K)

    return df.iloc[idx[0]]


# ----------------------------------------------------------
# PROMPT + ANSWER
# ----------------------------------------------------------

SYSTEM_PROMPT = """
You are an expert research assistant.
Answer ONLY using the provided excerpts.
If information is missing, say so clearly.
"""


def build_prompt(query, chunks):
    context = "\n\n".join(
        f"[page {r.page}]\n{r.text}"
        for _, r in chunks.iterrows()
    )

    prompt = f"""
{SYSTEM_PROMPT}

QUESTION:
{query}

EXCERPTS:
{context}

ANSWER:
"""
    return prompt[:12000]  # hard safety


def answer_question(paper_id: str, pdf_url: str, query: str):
    # Ensure index exists
    ensure_rag_ready(paper_id, pdf_url)

    chunks = retrieve(paper_id, query)
    prompt = build_prompt(query, chunks)

    completion = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_completion_tokens=600,
    )

    return completion.choices[0].message.content.strip()