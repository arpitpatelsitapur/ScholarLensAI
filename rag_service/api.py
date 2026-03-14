from fastapi import FastAPI
from pydantic import BaseModel
from rag_engine import answer_query, setup_rag

app = FastAPI()

class AskRequest(BaseModel):
    paper_id: str
    pdf_url: str
    question: str

@app.post("/ask")
def ask(req: AskRequest):

    # Build / load FAISS index for this paper
    setup_rag(req.paper_id, req.pdf_url)

    # Ask question
    ans = answer_query(req.question)

    return {"answer": ans}