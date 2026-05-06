def latest_feedback_cte() -> str:
    return """
        WITH latest_feedback AS (
            SELECT DISTINCT ON (rating_key)
                rating_key,
                feedback,
                suppress
            FROM public.user_feedback
            WHERE username = %s
            ORDER BY rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
        )
    """


def leaf_feedback_join(alias: str = "recs") -> str:
    return f" LEFT JOIN latest_feedback lf ON lf.rating_key = {alias}.rating_key"


def leaf_feedback_visibility_clause() -> str:
    return """
        AND CASE
            WHEN lf.feedback = 'interested' THEN FALSE
            ELSE COALESCE(lf.suppress, FALSE)
        END = FALSE
    """
