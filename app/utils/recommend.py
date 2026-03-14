import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import json
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer
from sklearn.metrics.pairwise import cosine_similarity
from adapters import AutoAdapterModel # Uncomment if using adapter-transformers

DB_PATH = "app/scholarlens.db"   

def load_specter2():
    print("Loading SPECTER2 model...")

    tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")

    # Load proximity adapter
    model.load_adapter("allenai/specter2", source="hf", load_as="specter2", set_active=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    print(f"Model loaded on {device}")
    return tokenizer, model, device

def load_papers():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT paper_id, title, abstract, category, url, pdf_url, popularity_score
        FROM unified_papers
        WHERE title IS NOT NULL AND abstract IS NOT NULL
    """, conn) 
    conn.close()
    return df

def align_df_with_embeddings(df, paper_ids):
    # Ensure df is ordered exactly as paper_ids from embeddings table
    df_indexed = df.set_index("paper_id")
    df_aligned = df_indexed.loc[paper_ids].reset_index()
    return df_aligned

def load_embeddings_from_db(model_name="specter2"):
    print("Loading saved embeddings from database...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT paper_id, embedding
        FROM embeddings
        WHERE model_name = ?
        ORDER BY paper_id
    """, (model_name,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("❌ No embeddings found. Run generation first.")
        return None

    # embeddings is stored as JSON string → convert to numpy
    paper_ids = []
    embeddings = []

    for pid, emb_json in rows:
        paper_ids.append(pid)
        emb = np.array(json.loads(emb_json), dtype=np.float32)
        embeddings.append(emb)

    final_embeddings = np.vstack(embeddings)

    print("Loaded embeddings shape:", final_embeddings.shape)

    return paper_ids, final_embeddings

def recommend_by_category(category, df, embeddings, top_k=10):
    mask = df["category"].str.lower() == category.lower()
    subset = df[mask]

    if subset.empty:
        print("No papers in this category.")
        return None

    idx = subset.index
    subset_emb = embeddings[idx]

    centroid = np.mean(subset_emb, axis=0).reshape(1, -1)
    sim = cosine_similarity(centroid, subset_emb).flatten()

    pop = subset["popularity_score"].fillna(0).values

    final_score = 0.8 * sim + 0.2 * pop

    top_idx = np.argsort(final_score)[::-1][:top_k]
    recs = subset.iloc[top_idx].copy()
    recs["semantic_similarity"] = sim[top_idx]
    recs["final_score"] = final_score[top_idx]

    return recs.sort_values("final_score", ascending=False)


def recommend_by_query(query, df, embeddings, tokenizer, model, device, top_k=10):
    encoded = tokenizer(
        [query],
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="pt",
        return_token_type_ids=False
    ).to(device)

    with torch.no_grad():
        out = model(**encoded)

    query_emb = out.last_hidden_state[:, 0, :]
    query_emb = F.normalize(query_emb, p=2, dim=1).cpu().numpy()

    sim_scores = cosine_similarity(query_emb, embeddings).flatten()
    pop = df["popularity_score"].fillna(0).values

    final = 0.8 * sim_scores + 0.2 * pop

    idx = np.argsort(final)[::-1][:top_k]

    recs = df.iloc[idx].copy()
    recs["semantic_similarity"] = sim_scores[idx]
    recs["final_score"] = final[idx]

    return recs.sort_values("final_score", ascending=False)







