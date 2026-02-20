import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("--- Library Stats ---")
cur.execute("SELECT media_type, COUNT(*) FROM library GROUP BY media_type")
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]}")

print("\n--- Episode Parent Linkage ---")
cur.execute("SELECT COUNT(*) FROM library WHERE media_type='episode' AND parent_rating_key IS NOT NULL")
linked_eps = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM library WHERE media_type='episode'")
total_eps = cur.fetchone()[0]
print(f"Episodes with Parent (Season): {linked_eps} / {total_eps}")

print("\n--- Season/Parent IDs ---")
cur.execute("SELECT distinct parent_rating_key from library where media_type='episode' limit 5")
print(f"Sample parent IDs from episodes: {cur.fetchall()}")

cur.execute("SELECT rating_key, title, media_type from library where media_type='season' limit 5")
print(f"Sample Season rows in library: {cur.fetchall()}")

conn.close()
