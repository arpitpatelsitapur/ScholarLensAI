# ==========================================================
# SCHOLARLENS - PDF RAG CORE (Groq + LLaMA 3.1)
# ==========================================================

import os
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List

import requests
import fitz  # PyMuPDF
import numpy as np
import pandas as pd
import faiss

from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv
load_dotenv()
import warnings
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ==========================================================
# CONFIG
# ==========================================================

PDF_URL = "https://arxiv.org/pdf/cs/9905014v1"
BASE_RAG_DIR = Path("./rag_store")
BASE_RAG_DIR.mkdir(exist_ok=True)

PDF_PATH = None
PAGES_JSON = None
CHUNKS_PARQUET = None
FAISS_INDEX_PATH = None

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_TOKENS = 250
OVERLAP_TOKENS = 50
TOP_K = 4
MAX_PROMPT_TOKENS = 2000 # Added: Limit for the total prompt sent to the LLM

GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # set this before running

# ==========================================================
# INITIALIZE MODELS
# ==========================================================

tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
groq_client = Groq(api_key=GROQ_API_KEY)

# ==========================================================
# UTILS
# ==========================================================

def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8192), b""):
            h.update(b)
    return h.hexdigest()

def count_tokens(text: str, max_len: int = 512) -> int:
    return tokenizer(
        text,
        truncation=True,
        max_length=max_len,
        return_length=True,
    )["length"][0]

# ==========================================================
# STEP 1: DOWNLOAD PDF
# ==========================================================

def download_pdf(pdf_url):

    if not pdf_url or pdf_url == "N/A":
        raise ValueError("Invalid PDF URL")

    if PDF_PATH.exists():
        return

    r = requests.get(pdf_url, stream=True)
    r.raise_for_status()

    with open(PDF_PATH, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

# ==========================================================
# STEP 2: EXTRACT TEXT (PyMuPDF)
# ==========================================================

def extract_pages():
    if PAGES_JSON.exists():
        return
    doc = fitz.open(PDF_PATH)
    pages = []
    for i in range(len(doc)):
        pages.append({
            "page": i + 1,
            "text": doc[i].get_text("text").replace("-\n", "")
        })
    with open(PAGES_JSON, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)

# ==========================================================
# STEP 3: CHUNKING
# ==========================================================

def create_chunks():
    if CHUNKS_PARQUET.exists():
        return

    pages = json.load(open(PAGES_JSON))
    chunks = []

    buffer = []
    token_count = 0
    page_start = None

    for p in pages:
        for para in [x.strip() for x in p["text"].split("\n\n") if x.strip()]:
            para_tokens = count_tokens(para)
            if page_start is None:
                page_start = p["page"]

            if token_count + para_tokens <= MAX_TOKENS:
                buffer.append(para)
                token_count += para_tokens
            else:
                chunks.append({
                    "chunk_id": len(chunks),
                    "text": "\n\n".join(buffer),
                    "page_start": page_start,
                    "page_end": p["page"]
                })
                # Keep an overlap for the next chunk, but ensure it's not too large
                overlap_text = " ".join(buffer[-OVERLAP_TOKENS:]) # Heuristic for word-based overlap
                buffer = [overlap_text] if overlap_text.strip() else []
                token_count = count_tokens(overlap_text) if overlap_text.strip() else 0
                buffer.append(para)
                page_start = p["page"]

    if buffer:
        chunks.append({
            "chunk_id": len(chunks),
            "text": "\n\n".join(buffer),
            "page_start": page_start,
            "page_end": p["page"]
        })

    pd.DataFrame(chunks).to_parquet(CHUNKS_PARQUET, index=False)

# ==========================================================
# STEP 4: BUILD FAISS INDEX
# ==========================================================

def safe_encode(texts, max_tokens=512):
    safe_texts = []

    for t in texts:
        tokens = tokenizer.encode(
            t,
            max_length=max_tokens,
            truncation=True
        )
        safe_texts.append(tokenizer.decode(tokens))

    return embedder.encode(
        safe_texts,
        convert_to_numpy=True,
        show_progress_bar=True
    )


def build_faiss():
    if FAISS_INDEX_PATH.exists():
        return

    df = pd.read_parquet(CHUNKS_PARQUET)
    embeddings = safe_encode(df["text"].tolist())
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, str(FAISS_INDEX_PATH))

# ==========================================================
# RETRIEVAL
# ==========================================================

def retrieve_chunks(query: str, k=TOP_K) -> pd.DataFrame:
    df = pd.read_parquet(CHUNKS_PARQUET)
    index = faiss.read_index(str(FAISS_INDEX_PATH))

    q_emb = safe_encode([query])
    q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)

    scores, idxs = index.search(q_emb.astype(np.float32), k)

    results = df.iloc[idxs[0]].copy()
    results["score"] = scores[0]
    return results

# ==========================================================
# PROMPTING
# ==========================================================

SYSTEM_PROMPT = """
You are an expert research assistant answering questions about a paper.
Explain answers clearly in your own words.
Do NOT use phrases like "According to the excerpts".
Only use information supported by the excerpts.
If information is missing, say:
"The provided excerpts do not contain more details."
"""

def build_prompt(query: str, chunks_df: pd.DataFrame) -> str:
    current_prompt_parts = []

    # Calculate tokens for the fixed parts of the prompt
    system_and_question_prefix = f"{SYSTEM_PROMPT}\n\nQUESTION:\n{query}\n\nANSWER:\n"
    current_token_count = count_tokens(system_and_question_prefix)

    current_prompt_parts.append(system_and_question_prefix)
    current_prompt_parts.append("\nEXCERPTS:\n")
    current_token_count += count_tokens("\nEXCERPTS:\n")

    for _, r in chunks_df.iterrows():
        chunk_header = f"[pages {r.page_start}-{r.page_end}]\n"
        MAX_CHARS_PER_CHUNK = 1000   # critical limit
        chunk_text = str(r.text)[:MAX_CHARS_PER_CHUNK]

        # Estimate tokens for the current chunk including header and separators
        potential_chunk_tokens = count_tokens(chunk_header + chunk_text + "\n\n")

        if current_token_count + potential_chunk_tokens > MAX_PROMPT_TOKENS:
            # If adding the whole chunk exceeds the limit, try to truncate it
            # Reserve some tokens for the truncated indicator
            remaining_space = MAX_PROMPT_TOKENS - current_token_count - count_tokens(chunk_header) - count_tokens("...[truncated]\n\n")
            
            if remaining_space > 0: # Only truncate if there's meaningful space left
                # Truncate chunk_text to fit remaining_space
                truncated_text = tokenizer.decode(tokenizer.encode(chunk_text, max_length=remaining_space, truncation=True))
                context_block = f"{chunk_header}{truncated_text}...[truncated]\n\n"
                current_prompt_parts.append(context_block)
                current_token_count += count_tokens(context_block)
            break # Stop adding chunks after the first truncation or if no space left
        else:
            context_block = f"{chunk_header}{chunk_text}\n\n"
            current_prompt_parts.append(context_block)
            current_token_count += count_tokens(context_block)

    return "".join(current_prompt_parts)

def clean_answer(text: str) -> str:
    patterns = [
        r"^According to .*?,\s*",
        r"^Based on .*?,\s*",
        r"^From the excerpts.*?\s*"
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.I)
    return text.strip()

# ==========================================================
# MAIN RAG FUNCTION (WHAT YOU WILL CALL)
# ==========================================================

def answer_query(query: str) -> str:
    retrieved = retrieve_chunks(query)
    prompt = build_prompt(query, retrieved)
    MAX_PROMPT_CHARS = 12000

    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS]

    completion = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_completion_tokens=600,
        top_p=1
    )

    raw_answer = completion.choices[0].message.content
    return clean_answer(raw_answer)

# ==========================================================
# ONE-TIME SETUP PIPELINE
# ==========================================================

def setup_rag(paper_id: str, pdf_url: str):
    global PDF_PATH, PAGES_JSON, CHUNKS_PARQUET, FAISS_INDEX_PATH

    WORK_DIR = BASE_RAG_DIR / paper_id
    WORK_DIR.mkdir(exist_ok=True)

    PDF_PATH = WORK_DIR / "paper.pdf"
    PAGES_JSON = WORK_DIR / "pages.json"
    CHUNKS_PARQUET = WORK_DIR / "chunks.parquet"
    FAISS_INDEX_PATH = WORK_DIR / "faiss.index"
    if FAISS_INDEX_PATH.exists():
        return

    download_pdf(pdf_url)
    extract_pages()
    create_chunks()
    build_faiss()

# ==========================================================
# RUN ONCE
# ==========================================================
# What is MAXQ decomposition?
# what is hierarchical reinforcement learning?

if __name__ == "__main__":
    setup_rag(PDF_URL)
    print("\nRAG ready. Ask questions (type 'exit' to quit)\n")

    while True:
        q = input(">> ")
        if q.lower() in {"exit", "quit", "bye"}:
            break
        print("\n", answer_query(q), "\n")