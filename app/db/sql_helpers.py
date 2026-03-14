# app/db/sql_helpers.py
import sqlite3

DB_PATH = "scholarlens.db"  # update if your main DB file name differs

def get_user_recommendations_sql(user_id, limit=20):
    """
    Fetch top recommended papers for a given user using SQL JOIN.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
        SELECT p.paper_id, p.title, p.authors, p.abstract, p.subcategory, 
               p.url, p.popularity_score, r.score, r.created_at
        FROM recommendations r
        JOIN papers p ON r.paper_id = p.paper_id
        WHERE r.user_id = ?
        ORDER BY r.score DESC
        LIMIT ?
    """
    cursor.execute(query, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    # Convert to a list of dicts for easy use in templates
    recommendations = [
        {
            "paper_id": row[0],
            "title": row[1],
            "authors": row[2],
            "abstract": row[3],
            "subcategory": row[4],
            "url": row[5],
            "popularity_score": row[6],
            "score": row[7],
            "created_at": row[8]
        }
        for row in rows
    ]
    return recommendations