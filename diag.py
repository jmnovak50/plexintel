import os
import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Connect to the database
db_url = os.getenv("DATABASE_URL")
if db_url:
    conn = psycopg2.connect(db_url)
else:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", 5432)
    )
register_vector(conn)
cursor = conn.cursor(cursor_factory=RealDictCursor)

# Show column names from key tables
tables = ["media_embeddings", "user_embeddings", "watch_history"]
for table in tables:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    print(f"\n🧱 Columns in '{table}':")
    for row in cursor.fetchall():
        print(f" - {row['column_name']}")

cursor.close()
conn.close()
