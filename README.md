<div align="center">

# 🔬 ScholarLens AI

**AI-Powered Research Paper Discovery & Chat System**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Llama 3.1](https://img.shields.io/badge/Llama_3.1-Groq-FF6B35?style=for-the-badge&logo=meta&logoColor=white)](https://groq.com)
[![FAISS](https://img.shields.io/badge/FAISS-Vector_DB-4285F4?style=for-the-badge&logo=meta&logoColor=white)](https://faiss.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

*Discover papers semantically. Chat with them intelligently. Bookmark what matters.*

[Features](#-features) • [Architecture](#-architecture) • [Setup](#-setup) • [Usage](#-usage) • [Docker](#-run-with-docker) • [Challenges](#-challenges)

</div>

---

## 🧠 What is ScholarLens AI?

ScholarLens AI is an intelligent research assistant that bridges the gap between **finding** academic papers and **understanding** them.

https://github.com/user-attachments/assets/bbd6862d-0f27-4a99-82aa-29050f407581

It combines:
- 📡 **Semantic paper recommendation** via SPECTER2 embeddings
- 💬 **RAG-based paper chat** — ask questions, get answers from the actual paper
- 🔖 **User personalization** — interests, bookmarks, filtered dashboards
- 🔐 **Google OAuth** authentication

> Instead of skimming 20-page PDFs, just ask: *"What is the main contribution of this paper?"*

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Semantic Search** | Find papers by topic using SPECTER2 embeddings |
| 💬 **Chat with Paper** | RAG pipeline lets you ask questions about any paper |
| 🏷️ **Category Filters** | Filter papers by research domain |
| 🔖 **Bookmarks** | Save papers to revisit later |
| 👤 **Personalization** | Dashboard tailored to your research interests |
| 🔐 **Google Login** | OAuth2-based secure authentication |

---

## 🏗️ Architecture
<div align="center">
     <img src="scholarlensai arch.gif" alt="Architecture" width="1000"/>
  </div>

The system runs as **two independent microservices** that communicate over HTTP.

---

## 🗂️ Project Structure

```
ScholarLensAI/
│
├── app/                          # Main FastAPI application
│   ├── api/
│   │   ├── pages.py              # Page routes
│   │   ├── auth.py               # Google OAuth2
│   │   └── users.py              # User endpoints
│   ├── db/                       # SQLAlchemy models & DB setup
│   ├── utils/
│   │   └── recommend.py          # SPECTER2 recommendation engine
│   ├── templates/                # Jinja2 HTML templates
│   ├── static/                   # CSS, JS, assets
│   └── main.py                   # App entrypoint
│
├── rag_service/                  # Standalone RAG microservice
│   ├── api.py                    # FastAPI RAG endpoints
│   ├── rag_engine.py             # Core RAG pipeline
│   ├── rag_store/                # Per-paper FAISS indexes
│   │   └── <paper_id>/
│   │       ├── paper.pdf
│   │       ├── chunks.parquet
│   │       └── faiss.index
│   └── requirements.txt
│
└── requirements.txt
```

---

## ⚙️ How the RAG Pipeline Works

For each paper, the pipeline runs once and caches the result:

```
1. Download PDF  →  2. Extract Text (PyMuPDF)  →  3. Split into Chunks
        ↓
4. Generate Embeddings (SentenceTransformers)
        ↓
5. Store in FAISS Index  →  Cached at rag_store/<paper_id>/
        ↓
6. User asks a question
        ↓
7. Retrieve top-k relevant chunks
        ↓
8. Build prompt: [context chunks + question]
        ↓
9. Send to Groq (Llama 3.1)  →  Return answer
```

**Caching:** If `faiss.index` already exists for a paper, it is reused — no re-embedding needed.

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com) — async web framework
- [SQLAlchemy](https://sqlalchemy.org) + SQLite — ORM & database
- [httpx](https://www.python-httpx.org) — async HTTP between services

**ML / Embeddings**
- [SPECTER2](https://huggingface.co/allenai/specter2) — scientific paper embeddings
- [SentenceTransformers](https://sbert.net) — embedding library
- [FAISS](https://faiss.ai) — vector similarity search

**LLM / RAG**
- [Groq API](https://groq.com) — ultra-fast LLM inference
- [Llama 3.1](https://llama.meta.com) — underlying language model

**Data Preprocessing**
- [PyMuPDF](https://pymupdf.readthedocs.io) — PDF text extraction
- Pandas + NumPy — data processing

**Frontend**
- Jinja2 templates, HTML, CSS

**Auth**
- Google OAuth2

---

## 🚀 Setup

### Prerequisites
- Python 3.10+
- A [Groq API key](https://console.groq.com) (free tier)
- Google OAuth credentials (for login)

---

### 1. Clone the Repository

```bash
git clone https://github.com/arpitpatelsitapur/ScholarLensAI.git
cd ScholarLensAI
```

### 2. Set Up the Main App

```bash
cd app
python -m venv recom_env
source recom_env/bin/activate        # Windows: recom_env\Scripts\activate
pip install -r requirements.txt
```

### 3. Set Up the RAG Service

```bash
# Open a new terminal
cd rag_service
python -m venv rag_env
source rag_env/bin/activate          # Windows: rag_env\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
SECRET_KEY=your_session_secret_key
```

### 5. Run Both Services

**Terminal 1 — Main app:**
```bash
cd app
uvicorn main:app --reload
# Runs at http://127.0.0.1:8000
```

**Terminal 2 — RAG service:**
```bash
cd rag_service
uvicorn api:app --port 8001 --reload
# Runs at http://127.0.0.1:8001
```

---

## 🐳 Run with Docker

ScholarLensAI is fully containerized. You can run the complete system using prebuilt Docker images — no Python setup or virtual environments needed.

### 📦 Docker Images


| Service      | Image                                      |
|-------------|--------------------------------------------|
| App Service | `datadreamer7/scholarlens-app:latest`       |
| RAG Service | `datadreamer7/scholarlens-rag:latest`       |

### 1. Create `docker-compose.yml`

```yaml
services:
  app:
    image: datadreamer7/scholarlens-app:latest
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - rag_service
    volumes:
      - app_data:/app

  rag_service:
    image: datadreamer7/scholarlens-rag:latest
    ports:
      - "8001:8001"
    env_file:
      - .env
    volumes:
      - rag_data:/rag_service/rag_store

volumes:
  app_data:
  rag_data:

```

### 2. Configure Environment Variables

Create a `.env` file in the same directory:

```env
GROQ_API_KEY=your_api_key
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
SECRET_KEY=your_secret
HF_TOKEN=your_token
```

### 3. Run

```bash
docker compose up

```

Then open: 👉 http://localhost:8000

### ⚠️ Notes

-   First run may take some time due to model loading
-   Ensure ports `8000` and `8001` are free on your machine
-   Both services communicate internally over the Docker network — no manual wiring needed

----------

## 🧪 Usage

1. Open `http://127.0.0.1:8000` in your browser
2. Log in with Google
3. Set your research interests in your profile
4. Browse recommended papers on the dashboard
5. Click any paper → open **"Chat with Paper"**
6. Ask questions like:

```
What is the main contribution of this paper?
What datasets were used for evaluation?
Explain the proposed methodology in simple terms.
What are the limitations mentioned by the authors?
```

**Example:**

> **Q:** What is MAXQ decomposition?
>
> **A:** MAXQ decomposition breaks a Markov Decision Process into a hierarchy of smaller subproblems. Each subproblem has its own value function which contributes to the overall value of the parent task, enabling hierarchical reinforcement learning.

---

## Some Screenshots
<p align="center">
  <img src="screenshots/home1.png" width="400"/>
  <img src="screenshots/about1.png" width="400"/>
  <img src="screenshots/about1.png" width="400"/>
  <img src="screenshots/profile.png" width="400"/>
  <img src="screenshots/dashboard1.png" width="400"/>
  <img src="screenshots/bookmark1.png" width="400"/>
  <img src="screenshots/chat1.png" width="400"/>
</p>


## Challenges

| Challenge | Solution |
|---|---|
| **Dependency conflicts** between `transformers`, `sentence-transformers`, `huggingface_hub` | Isolated each service into separate Docker containers with independent requirements |
| **Microservice communication** between main app and RAG service | HTTP calls via `httpx` using Docker service name (`http://rag_service:8001`) |
| **Single-paper RAG** — original pipeline only handled one PDF | Per-paper FAISS index stored at `rag_store/<paper_id>/` |
| **Noisy PDF extraction** — hyphenation, broken formatting | PyMuPDF + post-extraction text cleaning |
| **LLM token limits** — large prompts exceeded context window | Chunk truncation, token counting, prompt length control |
| **Slow re-embedding** on repeated paper visits | Index caching — rebuild only if `faiss.index` doesn't exist |
| **Large Docker image size** due to ML libraries (`torch`, `transformers`) | Used slim base image + `.dockerignore` to reduce build context |
| **Docker build failures due to strict versioning** | Relaxed version constraints and resolved incompatible dependencies |
| **Multi-container orchestration complexity** | Used Docker Compose to manage app + RAG services together |
| **Environment variable management across services** | Centralized config using `.env` file and `env_file` in Compose |
| **Database not persisting across container restarts** | Added Docker volumes (`app_data`) for persistent SQLite storage |
| **RAG index loss after container restart** | Mounted volume (`rag_data`) for persistent FAISS storage |
| **Broken pipe / timeout while pushing images to Docker Hub** | Switched to local build + `docker push` (chunked upload) instead of `buildx --push` |
| **Multi-architecture build issues on M1 (ARM)** | Used `buildx` builder setup; simplified to single-arch for reliability |
| **Module import errors inside container (`ModuleNotFoundError`)** | Fixed working directory and Python import paths in Dockerfile |
| **SQLite path issues inside container** | Switched to absolute container paths (e.g., `/app/scholarlens.db`) |
| **Service startup dependency issues (App before RAG)** | Used `depends_on` in Docker Compose |
| **Initial model loading delay (cold start)** | Documented behavior; accepted as expected for ML models |
| **Reproducibility across environments** | Provided Docker Compose setup for one-command execution |

---

## Limitations that I know this has

- Only works for papers with publicly accessible PDF URLs
- Index building takes 15–30s for the first load of a large paper
- No distributed vector store (single-node FAISS only)
- UI is functional but minimal

---
## Any Improvements/Suggestions are welcomed, just Fork the repo and play with it. Remember I used Microservices system so there are 2 virtual environments here.

[![GitHub](https://img.shields.io/badge/GitHub-arpitpatelsitapur-181717?style=flat&logo=github)](https://github.com/arpitpatelsitapur)

---

<div align="center">

*If this project helped you, consider giving it a ⭐*

</div>
