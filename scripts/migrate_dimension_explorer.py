"""Apply only the additive Dimension Explorer migrations, without running jobs."""
from contextlib import closing
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from api.db.connection import connect_db
from api.db.schema import apply_dimension_schema

if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    with closing(connect_db()) as conn, conn:
        apply_dimension_schema(conn)
    print('Dimension Explorer migrations applied. No labeling, training, or scoring was run.')
