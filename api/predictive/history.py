"""Bound ordinary execution logs; never prune source, predictions or cloud accounting."""


def prune(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.pipeline_runs')")
        if cur.fetchone()[0] is None:return 0
        # Keep all recent records plus at least 30 terminal records. A current
        # daily/weekly slot cannot be removed by this 30-day age boundary.
        cur.execute('''WITH ranked AS (
                SELECT run_id,started_at,row_number() OVER(ORDER BY started_at DESC,run_id DESC) AS position
                FROM public.pipeline_runs WHERE status IN ('success','failed','cancelled','verification_only'))
            DELETE FROM public.pipeline_runs p USING ranked r WHERE p.run_id=r.run_id AND r.position>30
                AND r.started_at<now()-interval '30 days' ''')
        return cur.rowcount
