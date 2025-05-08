import argparse
import psycopg2
from pgvector.psycopg2 import register_vector
import pandas as pd
import matplotlib.pyplot as plt

def connect_db():
    conn = psycopg2.connect(
        dbname="plexintel",
        user="jmnovak",
        password="brigid",
        host="localhost"
    )
    register_vector(conn)
    return conn

def main():
    parser = argparse.ArgumentParser(description="Explore a specific dimension in combined user-media embeddings.")
    parser.add_argument("--dimension", type=int, required=True, help="Dimension index to explore (e.g. 1345)")
    parser.add_argument("--limit", type=int, default=20, help="How many top rows to return")
    parser.add_argument("--export_csv", action="store_true", help="Export results to CSV")
    args = parser.parse_args()

    conn = connect_db()
    cur = conn.cursor()

    # Load from training_data or scored_data
    cur.execute("SELECT id, rating_key, embedding FROM training_data")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=["id", "rating_key", "embedding"])

    if not rows:
        raise ValueError("No combined embeddings found in training_data")

    vector_dim = len(df["embedding"].iloc[0])
    if args.dimension >= vector_dim:
        raise ValueError(f"⚠️ Dimension {args.dimension} out of bounds (max = {vector_dim - 1})")

    # Add column for selected dimension
    dim_col = f"emb_{args.dimension}"
    df[dim_col] = df["embedding"].apply(lambda v: v[args.dimension])

    # Display top N
    top_df = df.sort_values(dim_col, ascending=False).head(args.limit)
    print("📊 Top rows by embedding dimension:")
    print(top_df[["id", "rating_key", dim_col]])

    # Show stats
    print("\n📈 Dimension statistics:")
    print(df[dim_col].describe())

    # Plot histogram
    plt.hist(df[dim_col], bins=50)
    plt.title(f"Distribution of Combined Dimension {args.dimension}")
    plt.xlabel("Value")
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    if args.export_csv:
        filename = f"combined_emb_{args.dimension}_analysis.csv"
        df.to_csv(filename, index=False)
        print(f"✅ Exported results to {filename}")

if __name__ == "__main__":
    main()
