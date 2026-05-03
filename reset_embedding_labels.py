from dotenv import load_dotenv

load_dotenv()

import argparse
import csv
import os

import psycopg2


DB_URL = os.getenv("DATABASE_URL")
EMBEDDING_SIDE_DIMENSIONS = 768
COMBINED_EMBEDDING_DIMENSIONS = EMBEDDING_SIDE_DIMENSIONS * 2
SCOPE_RANGES = {
    "all": (0, COMBINED_EMBEDDING_DIMENSIONS),
    "media": (0, EMBEDDING_SIDE_DIMENSIONS),
    "user": (EMBEDDING_SIDE_DIMENSIONS, COMBINED_EMBEDDING_DIMENSIONS),
}


def connect_db():
    return psycopg2.connect(DB_URL)


def get_scope_bounds(scope: str) -> tuple[int, int]:
    if scope not in SCOPE_RANGES:
        raise ValueError(f"Unsupported scope: {scope}")
    return SCOPE_RANGES[scope]


def fetch_scope_rows(cur, scope: str) -> list[tuple]:
    dim_min, dim_max = get_scope_bounds(scope)
    cur.execute(
        """
        SELECT dimension, label, created_at
        FROM embedding_labels
        WHERE dimension >= %s AND dimension < %s
        ORDER BY dimension
        """,
        (dim_min, dim_max),
    )
    return cur.fetchall()


def write_backup_csv(path: str, rows: list[tuple]):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["dimension", "label", "created_at"])
        writer.writerows(rows)


def write_backup_sql(path: str, rows: list[tuple], cur):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("-- Restore backup for embedding_labels\n")
        handle.write("BEGIN;\n")
        for row in rows:
            statement = cur.mogrify(
                """
                INSERT INTO embedding_labels (dimension, label, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (dimension)
                DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at;
                """,
                row,
            ).decode("utf-8")
            handle.write(statement)
            handle.write("\n")
        handle.write("COMMIT;\n")


def main():
    parser = argparse.ArgumentParser(description="Backup and optionally clear embedding labels by dimension scope.")
    parser.add_argument("--scope", choices=sorted(SCOPE_RANGES), default="all")
    parser.add_argument("--backup_csv", help="CSV backup path; required with --execute")
    parser.add_argument("--backup_sql", help="SQL restore path; required with --execute")
    parser.add_argument("--execute", action="store_true", help="Actually delete the selected rows after backups succeed")
    args = parser.parse_args()

    conn = connect_db()
    cur = conn.cursor()
    rows = fetch_scope_rows(cur, args.scope)
    dim_min, dim_max = get_scope_bounds(args.scope)

    print(f"Scope: {args.scope} ({dim_min} <= dimension < {dim_max})")
    print(f"Matching rows: {len(rows)}")
    print("Preview:")
    for dimension, label, created_at in rows[:10]:
        print(f"  {dimension}: {label} ({created_at})")
    if len(rows) > 10:
        print(f"  ... {len(rows) - 10} more")

    if not args.execute:
        print("Preview only. Re-run with --execute plus backup paths to delete these rows.")
        cur.close()
        conn.close()
        return

    if not args.backup_csv or not args.backup_sql:
        parser.error("--backup_csv and --backup_sql are required with --execute")

    write_backup_csv(args.backup_csv, rows)
    write_backup_sql(args.backup_sql, rows, cur)
    print(f"✅ Wrote CSV backup: {args.backup_csv}")
    print(f"✅ Wrote SQL backup: {args.backup_sql}")

    cur.execute(
        """
        DELETE FROM embedding_labels
        WHERE dimension >= %s AND dimension < %s
        """,
        (dim_min, dim_max),
    )
    deleted_rows = cur.rowcount
    conn.commit()

    remaining_rows = fetch_scope_rows(cur, args.scope)
    print(f"✅ Deleted rows: {deleted_rows}")
    print(f"Remaining rows in scope: {len(remaining_rows)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
