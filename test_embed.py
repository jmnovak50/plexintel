from sentence_transformers import SentenceTransformer
import time

model = SentenceTransformer("all-mpnet-base-v2")

text = "The Matrix | Action, Sci-Fi | A hacker discovers reality is a simulation."

print("⏱️ Generating embedding...")
start = time.time()
embedding = model.encode(text)
end = time.time()

print(f"✅ Done. Vector length: {len(embedding)}")
print(f"🕒 Time taken: {round(end - start, 2)} seconds")
