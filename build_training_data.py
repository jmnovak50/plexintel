from dotenv import load_dotenv
from collections import Counter
from datetime import datetime
import numpy as np
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from pgvector import Vector
import ast

from api.db.connection import connect_db
from api.db.schema import ensure_app_schema
from api.services.app_settings import get_setting_value
from user_profile_embeddings import (
    TrainingProfileResult,
    build_user_profiles,
    fetch_profile_title_rows,
    fuse_media_and_user_embedding,
    leave_one_title_out,
)

# ✅ Load environment variables
load_dotenv()

ENGAGEMENT_THRESHOLD = get_setting_value("training.engagement_threshold", default=0.7)
FEEDBACK_BONUS = get_setting_value("training.feedback_bonus", default=0.1)
ENABLE_FEEDBACK = get_setting_value("training.enable_feedback", default=True)
USE_SAMPLE_WEIGHT = get_setting_value("training.use_sample_weight", default=True)
WATCH_EMBED_MIN_ENGAGEMENT = get_setting_value("training.watch_embed_min_engagement", default=0.5)
INTERESTED_SAMPLE_WEIGHT = get_setting_value("training.interested_sample_weight", default=0.75)
WATCHED_LIKE_SAMPLE_WEIGHT = get_setting_value("training.watched_like_sample_weight", default=3.0)
NEGATIVE_SAMPLE_WEIGHT = get_setting_value("training.negative_sample_weight", default=5.0)
USER_PROFILE_ENGAGEMENT_THRESHOLD = get_setting_value(
    "user_embeddings.engagement_threshold",
    default=0.5,
)

REQUIRED_TRAINING_COLUMNS = [
    "username",
    "rating_key",
    "label",
    "embedding",
    "genre_tags",
    "actor_tags",
    "director_tags",
    "release_year",
    "season_number",
    "episode_number",
    "played_duration",
    "media_duration",
    "engagement_ratio",
]

OPTIONAL_TRAINING_COLUMNS = [
    "watch_sim",
    "sample_weight",
    "label_source",
    "feedback_value",
    "engagement_type",
    "watch_count",
    "max_single_session_seconds",
    "total_played_seconds",
]

WATCH_ENGAGED_THRESHOLD = 0.60
WATCH_ABANDONED_MAX_RATIO = 0.35
WATCH_MIN_SECONDS = 120
WATCH_ABANDONED_MIN_SECONDS = 600
WATCH_ABANDONED_MIN_RATIO = 0.05
MOVIE_REVISIT_PENDING_DAYS = get_setting_value("training.movie_revisit_pending_days", default=21)
TV_REVISIT_PENDING_DAYS = get_setting_value("training.tv_revisit_pending_days", default=14)


def connect():
    conn = connect_db()
    register_vector(conn)
    return conn


def parse_embedding(x):
    if isinstance(x, Vector):
        x = x.to_numpy()
    if isinstance(x, str):
        x = ast.literal_eval(x)
    return np.asarray(x, dtype=np.float32)

def cosine_similarity(a, b):
    if a is None or b is None:
        return 0.0
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def feedback_only_config(feedback: str):
    if feedback == "interested":
        return 1, INTERESTED_SAMPLE_WEIGHT, FEEDBACK_BONUS, "explicit_interest"
    if feedback == "never_watch":
        return 0, NEGATIVE_SAMPLE_WEIGHT, 0.0, "explicit_reject"
    if feedback == "watched_like":
        return 1, WATCHED_LIKE_SAMPLE_WEIGHT, FEEDBACK_BONUS, "explicit_watched_like"
    if feedback == "watched_dislike":
        return 0, NEGATIVE_SAMPLE_WEIGHT, 0.0, "explicit_watched_dislike"
    return None


def get_training_data_columns(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'training_data'
        """)
        return {row[0] for row in cur.fetchall()}


def build_insert_sql(existing_columns):
    insert_columns = [col for col in REQUIRED_TRAINING_COLUMNS if col in existing_columns]
    missing_required = [col for col in REQUIRED_TRAINING_COLUMNS if col not in existing_columns]
    if missing_required:
        raise RuntimeError(
            "training_data is missing required columns: "
            + ", ".join(missing_required)
        )

    insert_columns.extend(
        col for col in OPTIONAL_TRAINING_COLUMNS if col in existing_columns
    )
    placeholders = ["%s::vector" if col == "embedding" else "%s" for col in insert_columns]
    insert_sql = f"""
        INSERT INTO training_data ({", ".join(insert_columns)})
        VALUES ({", ".join(placeholders)})
    """
    return insert_sql, insert_columns


def skipped_watch_row(engagement_type):
    return {
        "include_training": False,
        "engagement_type": engagement_type,
    }


def past_revisit_pending_window(last_watched_at, pending_days):
    if pending_days <= 0:
        return True
    if not last_watched_at:
        return False

    now = datetime.now(last_watched_at.tzinfo) if getattr(last_watched_at, "tzinfo", None) else datetime.now()
    return (now - last_watched_at).days >= pending_days


def build_user_watch_vectors(conn):
    """
    Build a per-user average watch-embedding vector (from watch_history + watch_embeddings).
    Only includes watch events above WATCH_EMBED_MIN_ENGAGEMENT.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                wh.username,
                wh.played_duration,
                l.duration AS media_duration,
                we.embedding AS watch_embedding
            FROM watch_history wh
            JOIN library l ON wh.rating_key = l.rating_key
            JOIN watch_embeddings we ON wh.watch_id::text = we.watch_id::text
            WHERE wh.played_duration IS NOT NULL
              AND l.duration IS NOT NULL
        """)
        rows = cur.fetchall()

    user_sums = {}
    user_counts = {}
    for row in rows:
        media_duration = row.get("media_duration")
        if not media_duration:
            continue
        played = row.get("played_duration")
        ratio = played / (media_duration / 1000.0) if media_duration else 0.0
        if ratio < WATCH_EMBED_MIN_ENGAGEMENT:
            continue

        vec = parse_embedding(row.get("watch_embedding"))
        username = row.get("username")
        if username not in user_sums:
            user_sums[username] = vec.copy()
            user_counts[username] = 1
        else:
            user_sums[username] += vec
            user_counts[username] += 1

    user_vectors = {u: user_sums[u] / user_counts[u] for u in user_sums}
    print(f"🧠 Built watch-embedding profiles for {len(user_vectors)} users (min engagement {WATCH_EMBED_MIN_ENGAGEMENT})")
    return user_vectors


def process_row(row, user_watch_vectors=None, from_feedback_only=False):
    username = row["username"]
    rewatch_count = int(row.get("rewatch_count", 0))
    rating_key = row["rating_key"]
    feedback = row.get("feedback")
    genres = row.get("genre_tags") or ''
    actors = row.get("actor_tags") or ''
    directors = row.get("director_tags") or ''
    media_embedding = parse_embedding(row["media_embedding"])
    user_embedding = parse_embedding(row["user_embedding"])
    combined_emb = Vector(
        fuse_media_and_user_embedding(media_embedding, user_embedding).tolist()
    )
    user_watch_vec = user_watch_vectors.get(username) if user_watch_vectors else None
    watch_sim = cosine_similarity(user_watch_vec, media_embedding) if user_watch_vec is not None else 0.0

    if from_feedback_only:
        feedback_config = feedback_only_config(feedback)
        if not feedback_config:
            return None
        label, sample_weight, engagement_ratio, label_source = feedback_config

        return {
            "include_training": True,
            "username": username,
            "rating_key": rating_key,
            "label": label,
            "embedding": combined_emb,
            "genre_tags": genres,
            "actor_tags": actors,
            "director_tags": directors,
            "release_year": row.get("release_year"),
            "season_number": None,
            "episode_number": None,
            "played_duration": 0,
            "media_duration": 0,
            "engagement_ratio": engagement_ratio,
            "watch_sim": watch_sim,
            "sample_weight": sample_weight,
            "label_source": label_source,
            "feedback_value": feedback,
            "engagement_type": label_source,
            "watch_count": 0,
            "max_single_session_seconds": 0,
            "total_played_seconds": 0,
        }

    media_duration_seconds = row.get("media_duration_seconds")
    if not media_duration_seconds or float(media_duration_seconds) <= 0:
        return skipped_watch_row("invalid_duration")

    media_type = row.get("media_type")
    played_duration = int(row.get("total_played_seconds") or 0)
    engagement_ratio = float(row["total_engagement_ratio"])
    max_session_engagement_ratio = float(row.get("max_session_engagement_ratio") or 0.0)
    max_single_session_seconds = int(row.get("max_single_session_seconds") or 0)
    watch_count = int(row.get("watch_count") or 0)
    last_watched_at = row.get("last_watched_at")
    revisit_pending_days = TV_REVISIT_PENDING_DAYS if media_type == "episode" else MOVIE_REVISIT_PENDING_DAYS

    label_source = "watch_history"
    feedback_value = feedback

    feedback_config = feedback_only_config(feedback)
    if feedback_config:
        label, sample_weight, _feedback_engagement_ratio, label_source = feedback_config
        return {
            "include_training": True,
            "username": username,
            "rating_key": rating_key,
            "label": label,
            "embedding": combined_emb,
            "genre_tags": genres,
            "actor_tags": actors,
            "director_tags": directors,
            "release_year": row.get("release_year"),
            "season_number": row.get("season_number"),
            "episode_number": row.get("episode_number"),
            "played_duration": int(played_duration),
            "media_duration": int(round(float(media_duration_seconds))),
            "engagement_ratio": engagement_ratio,
            "watch_sim": watch_sim,
            "sample_weight": sample_weight,
            "label_source": label_source,
            "feedback_value": feedback_value,
            "engagement_type": label_source,
            "watch_count": watch_count,
            "max_single_session_seconds": max_single_session_seconds,
            "total_played_seconds": int(played_duration),
        }

    # Label the user's aggregate behavior for this item. Completed-over-time
    # viewing is positive; abandonment is negative only after a real start.
    # Middle cases are too noisy for now and are counted, not trained.
    meaningful_partial = (
        max_single_session_seconds >= WATCH_MIN_SECONDS
        and engagement_ratio <= WATCH_ABANDONED_MAX_RATIO
        and (
            max_single_session_seconds >= WATCH_ABANDONED_MIN_SECONDS
            or max_session_engagement_ratio >= WATCH_ABANDONED_MIN_RATIO
        )
    )
    if engagement_ratio >= WATCH_ENGAGED_THRESHOLD:
        label = 1
        engagement_type = "engaged"
        sample_weight = min(1.0 + 0.5 * rewatch_count, 5.0)
    elif meaningful_partial and not past_revisit_pending_window(last_watched_at, revisit_pending_days):
        return skipped_watch_row("revisit_pending")
    elif meaningful_partial:
        label = 0
        engagement_type = "abandoned"
        sample_weight = min(1.0 + 0.5 * rewatch_count, 5.0)
    elif played_duration < WATCH_MIN_SECONDS:
        return skipped_watch_row("too_short")
    else:
        return skipped_watch_row("sample_or_uncertain")

    return {
        "include_training": True,
        "username": username,
        "rating_key": rating_key,
        "label": label,
        "embedding": combined_emb,
        "genre_tags": genres,
        "actor_tags": actors,
        "director_tags": directors,
        "release_year": row.get("release_year"),
        "season_number": row.get("season_number"),
        "episode_number": row.get("episode_number"),
        "played_duration": int(played_duration),
        "media_duration": int(round(float(media_duration_seconds))),
        "engagement_ratio": engagement_ratio,
        "watch_sim": watch_sim,
        "sample_weight": sample_weight,
        "label_source": label_source,
        "feedback_value": feedback_value,
        "engagement_type": engagement_type,
        "watch_count": watch_count,
        "max_single_session_seconds": max_single_session_seconds,
        "total_played_seconds": int(played_duration),
    }


def add_leave_one_out_user_embedding(row, user_profiles):
    """Attach the only user embedding permitted for a training example."""
    profile = user_profiles.get(row["username"])
    if profile is None:
        result = TrainingProfileResult(
            embedding=None,
            qualifying_count=0,
            training_count=0,
            current_title_in_profile=False,
            current_title_excluded=False,
        )
        return None, result

    result = leave_one_title_out(profile, row["rating_key"])
    if result.current_title_in_profile:
        assert result.current_title_excluded, (
            "LEAKAGE VIOLATION: qualifying current title was not excluded for "
            f"{row['username']}/{row['rating_key']}"
        )
        assert result.training_count == result.qualifying_count - 1
    else:
        assert result.training_count == result.qualifying_count

    if result.embedding is None:
        return None, result

    training_row = dict(row)
    training_row["user_embedding"] = result.embedding
    return training_row, result


def build_training_data(diagnostic_samples=0, dry_run=False):
    if not dry_run:
        ensure_app_schema()
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    existing_columns = get_training_data_columns(conn)
    insert_sql, insert_columns = build_insert_sql(existing_columns)

    print("📦 Fetching aggregated watch-based rows...")
    cur.execute("""
        WITH latest_feedback AS (
            SELECT DISTINCT ON (username, rating_key)
                username,
                rating_key,
                feedback
            FROM user_feedback
            ORDER BY username, rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
        ),
        watch_agg AS (
            SELECT
                t.username,
                t.rating_key,
                COUNT(*) AS watch_count,
                SUM(t.played_duration)::integer AS total_played_seconds,
                MAX(t.played_duration)::integer AS max_single_session_seconds,
                l.duration AS media_duration,
                l.media_type,
                MAX(t.watched_at) AS last_watched_at,
                CASE
                    WHEN l.duration IS NOT NULL AND l.duration > 0
                        THEN l.duration / 1000.0
                    ELSE NULL
                END AS media_duration_seconds,
                CASE
                    WHEN l.duration IS NOT NULL AND l.duration > 0
                        THEN SUM(t.played_duration)::float / (l.duration / 1000.0)
                    ELSE NULL
                END AS total_engagement_ratio,
                CASE
                    WHEN l.duration IS NOT NULL AND l.duration > 0
                        THEN MAX(t.played_duration)::float / (l.duration / 1000.0)
                    ELSE NULL
                END AS max_session_engagement_ratio,
                l.year AS release_year,
                COALESCE(l.season_number, MAX(t.season_number)) AS season_number,
                COALESCE(l.episode_number, MAX(t.episode_number)) AS episode_number
            FROM watch_history t
            LEFT JOIN library l ON t.rating_key = l.rating_key
            WHERE t.played_duration IS NOT NULL
            GROUP BY t.username, t.rating_key, l.duration, l.media_type, l.year,
                     l.season_number, l.episode_number
        )
        SELECT
    t.username,
    t.rating_key,
    t.watch_count,
    t.watch_count AS rewatch_count,
    t.total_played_seconds,
    t.max_single_session_seconds,
    t.media_duration,
    t.media_type,
    t.last_watched_at,
    t.media_duration_seconds,
    t.total_engagement_ratio,
    t.max_session_engagement_ratio,
    t.release_year,
    t.season_number,
    t.episode_number,
    genre_tags.genre_tags,
    actor_tags.actor_tags,
    director_tags.director_tags,
    me.embedding AS media_embedding,
    f.feedback
FROM watch_agg t
JOIN media_embeddings me ON t.rating_key = me.rating_key
LEFT JOIN latest_feedback f ON f.username = t.username AND f.rating_key = t.rating_key

-- ✅ Subquery joins to fetch tags per media item
LEFT JOIN LATERAL (
    SELECT string_agg(g.name, ', ') AS genre_tags
    FROM media_genres mg
    JOIN genres g ON mg.genre_id = g.id
    WHERE mg.media_id = t.rating_key
) genre_tags ON true

LEFT JOIN LATERAL (
    SELECT string_agg(a.name, ', ' ORDER BY ma.cast_order NULLS LAST, a.name) AS actor_tags
    FROM media_actors ma
    JOIN actors a ON ma.actor_id = a.id
    WHERE ma.media_id = t.rating_key
) actor_tags ON true

LEFT JOIN LATERAL (
    SELECT string_agg(d.name, ', ') AS director_tags
    FROM media_directors md
    JOIN directors d ON md.director_id = d.id
    WHERE md.media_id = t.rating_key
) director_tags ON true

    """)
    watched_rows = cur.fetchall()

    print("📅 Fetching feedback-only rows (no watch history)...")
    cur.execute("""
        WITH latest_feedback AS (
            SELECT DISTINCT ON (username, rating_key)
                username,
                rating_key,
                feedback
            FROM user_feedback
            ORDER BY username, rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
        )
        SELECT
            f.username,
            f.rating_key,
            f.feedback,
            l.year AS release_year,
            (
                SELECT string_agg(g.name, ', ')
                FROM media_genres mg
                JOIN genres g ON mg.genre_id = g.id
                WHERE mg.media_id = l.rating_key
            ) AS genre_tags,
            (
                SELECT string_agg(a.name, ', ' ORDER BY ma.cast_order NULLS LAST, a.name)
                FROM media_actors ma
                JOIN actors a ON ma.actor_id = a.id
                WHERE ma.media_id = l.rating_key
            ) AS actor_tags,
            (
                SELECT string_agg(d.name, ', ')
                FROM media_directors md
                JOIN directors d ON md.director_id = d.id
                WHERE md.media_id = l.rating_key
            ) AS director_tags,
            me.embedding AS media_embedding
        FROM latest_feedback f
        JOIN library l ON f.rating_key = l.rating_key
        JOIN media_embeddings me ON f.rating_key = me.rating_key
        LEFT JOIN watch_history w ON w.username = f.username AND w.rating_key = f.rating_key
        WHERE w.rating_key IS NULL
    """)
    feedback_only_rows = cur.fetchall()

    if watched_rows:
        sample_embedding = parse_embedding(watched_rows[0]["media_embedding"])
    elif feedback_only_rows:
        sample_embedding = parse_embedding(feedback_only_rows[0]["media_embedding"])
    else:
        sample_embedding = None

    if sample_embedding is not None:
        embedding_dim = len(sample_embedding)
        print("🔍 Detected embedding dimension:", embedding_dim)
    else:
        cur.close()
        conn.close()
        raise RuntimeError(
            "No media embeddings found for candidate training data. "
            "Leaving existing training_data unchanged."
        )

    print(f"✅ Retrieved {len(watched_rows)} aggregated watched + {len(feedback_only_rows)} feedback-only rows")

    print("👤 Fetching title-level user preference profiles...")
    profile_title_rows = fetch_profile_title_rows(conn)
    user_profiles = build_user_profiles(
        profile_title_rows,
        engagement_threshold=USER_PROFILE_ENGAGEMENT_THRESHOLD,
        expected_dimension=embedding_dim,
    )
    qualifying_profile_titles = sum(profile.count for profile in user_profiles.values())

    print("🧮 Building per-user watch-embedding profiles...")
    user_watch_vectors = build_user_watch_vectors(conn)

    inserts = []
    watched_insert_count = 0
    watched_skip_counts = Counter()
    watch_engagement_counts = Counter()
    loo_excluded_count = 0
    loo_not_in_profile_count = 0
    loo_empty_skip_count = 0
    loo_empty_users = set()
    diagnostic_candidates = {0: [], 1: []}

    def process_training_candidate(row, *, from_feedback_only=False):
        nonlocal loo_excluded_count, loo_not_in_profile_count
        nonlocal loo_empty_skip_count

        training_row, profile_result = add_leave_one_out_user_embedding(
            row,
            user_profiles,
        )
        if training_row is None:
            loo_empty_skip_count += 1
            loo_empty_users.add(row["username"])
            print(
                f"[LEAKAGE-GUARD] Skipping {row['username']} / rating_key "
                f"{row['rating_key']}: no qualifying user-history vectors remain "
                "after leave-one-out exclusion"
            )
            return None, profile_result

        result = process_row(
            training_row,
            user_watch_vectors,
            from_feedback_only=from_feedback_only,
        )
        if result and result.get("include_training"):
            if profile_result.current_title_in_profile:
                assert profile_result.current_title_excluded
                loo_excluded_count += 1
            else:
                loo_not_in_profile_count += 1

            label_diagnostics = diagnostic_candidates.setdefault(result["label"], [])
            if len(label_diagnostics) < diagnostic_samples:
                excluded_display = (
                    "True" if profile_result.current_title_in_profile else "N/A"
                )
                label_diagnostics.append(
                    "[LOO-DIAGNOSTIC] "
                    f"username={row['username']} "
                    f"rating_key={row['rating_key']} "
                    f"label={result['label']} "
                    f"qualifying_profile_titles={profile_result.qualifying_count} "
                    f"current_title_in_profile={profile_result.current_title_in_profile} "
                    f"training_profile_titles={profile_result.training_count} "
                    f"current_title_excluded={excluded_display}"
                )
        return result, profile_result

    for row in watched_rows:
        result, _profile_result = process_training_candidate(row)
        if not result:
            continue
        watch_engagement_counts[result["engagement_type"]] += 1
        if result.get("include_training"):
            inserts.append(result)
            watched_insert_count += 1
        else:
            watched_skip_counts[result["engagement_type"]] += 1

    for row in feedback_only_rows:
        result, _profile_result = process_training_candidate(
            row,
            from_feedback_only=True,
        )
        if result and result.get("include_training"):
            inserts.append(result)

    label_counts = Counter(r["label"] for r in inserts)

    diagnostics_to_print = []
    if diagnostic_samples:
        # Show both classes when available, then fill remaining slots without
        # exceeding the caller's requested total.
        for label in (1, 0):
            if diagnostic_candidates.get(label):
                diagnostics_to_print.append(diagnostic_candidates[label].pop(0))
        for label in (1, 0):
            while (
                diagnostic_candidates.get(label)
                and len(diagnostics_to_print) < diagnostic_samples
            ):
                diagnostics_to_print.append(diagnostic_candidates[label].pop(0))
        for diagnostic in diagnostics_to_print[:diagnostic_samples]:
            print(diagnostic)

    users_processed = {
        row["username"] for row in watched_rows + feedback_only_rows
    }
    print(f"👥 Users processed: {len(users_processed)}")
    print(f"🎞️ Unique watched titles evaluated: {len(profile_title_rows)}")
    print(f"✅ Qualifying user-profile titles: {qualifying_profile_titles}")
    print(f"📊 Aggregated user/media pairs: {len(watched_rows)}")
    print(f"🧠 Prepared training_data records: {len(inserts)}")
    print(f"🧠 Training rows created: {len(inserts)}")
    print(f"➕ Positive training rows: {label_counts.get(1, 0)}")
    print(f"➖ Negative training rows: {label_counts.get(0, 0)}")
    print(f"🚪 Rows where current title was excluded from user embedding: {loo_excluded_count}")
    print(f"➡️ Rows where current title was not part of user profile: {loo_not_in_profile_count}")
    print(f"🛡️ Rows skipped because leave-one-out history was empty: {loo_empty_skip_count}")
    print(f"🛡️ Users affected: {len(loo_empty_users)}")
    print(f"🎬 Inserted watched aggregates: {watched_insert_count}")
    print(f"🚫 Skipped invalid_duration: {watched_skip_counts.get('invalid_duration', 0)}")
    print(f"⏱️ Skipped too_short: {watched_skip_counts.get('too_short', 0)}")
    print(f"⚪ Skipped partial_or_uncertain: {watched_skip_counts.get('partial_or_uncertain', 0)}")
    print(f"✅ Labeled engaged: {watch_engagement_counts.get('engaged', 0)}")
    print(f"🛑 Labeled abandoned: {watch_engagement_counts.get('abandoned', 0)}")
    print(f"📈 Label distribution: {dict(sorted(label_counts.items()))}")
    print(f"🧾 Watch engagement type counts: {dict(sorted(watch_engagement_counts.items()))}")

    negative_feedback_count = sum(
        1 for r in inserts
        if r.get("label_source") in ["explicit_reject", "explicit_watched_dislike"]
    )
    interested_count = sum(1 for r in inserts if r.get("label_source") == "explicit_interest")
    watched_like_count = sum(1 for r in inserts if r.get("label_source") == "explicit_watched_like")
    print(f"👎 Explicit negative feedback rows: {negative_feedback_count}")
    print(f"🔖 Interested intent rows: {interested_count}")
    print(f"👍 Explicit watched-like rows: {watched_like_count}")

    rewatch_boosted = sum(
        1 for r in inserts
        if r.get("label_source") == "watch_history"
        and r.get("sample_weight", 1.0) > 1.0
        and r["label"] == 1
    )
    print(f"🔁 Rewatch-boosted positive labels: {rewatch_boosted}")

    if not inserts:
        cur.close()
        conn.close()
        raise RuntimeError(
            "No valid training records were generated after engagement filtering. "
            "Leaving existing training_data unchanged."
        )

    summary = {
        "users_processed": len(users_processed),
        "unique_watched_titles_evaluated": len(profile_title_rows),
        "qualifying_user_profile_titles": qualifying_profile_titles,
        "training_rows_created": len(inserts),
        "positive_training_rows": label_counts.get(1, 0),
        "negative_training_rows": label_counts.get(0, 0),
        "current_title_excluded_rows": loo_excluded_count,
        "current_title_not_in_profile_rows": loo_not_in_profile_count,
        "zero_leave_one_out_history_rows": loo_empty_skip_count,
        "zero_leave_one_out_history_users": len(loo_empty_users),
    }

    if dry_run:
        cur.close()
        conn.close()
        print("🧪 Dry run complete; training_data was not modified.")
        return summary

    print(f"🧠 Inserting {len(inserts)} training records...")

    with conn.cursor() as insert_cur:
        print("🚧 Replacing existing training data...")
        insert_cur.execute("DELETE FROM training_data;")
        for row in inserts:
            insert_cur.execute(insert_sql, [row.get(col) for col in insert_columns])

    conn.commit()

    cur.execute("""
        SELECT COUNT(*) AS duplicate_pairs
        FROM (
            SELECT username, rating_key
            FROM training_data
            GROUP BY username, rating_key
            HAVING COUNT(*) > 1
        ) duplicates
    """)
    duplicate_pairs = cur.fetchone()["duplicate_pairs"]
    print(f"🔎 Duplicate username/rating_key pairs after insert: {duplicate_pairs}")

    cur.close()
    conn.close()
    print("✅ Training data build complete.")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build leakage-safe PlexIntel training data."
    )
    parser.add_argument(
        "--diagnostic-samples",
        type=int,
        default=0,
        help="Print bounded leave-one-title-out details for this many created rows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and report all rows without modifying schema or training_data.",
    )
    args = parser.parse_args()
    if args.diagnostic_samples < 0:
        parser.error("--diagnostic-samples must be zero or greater")
    build_training_data(
        diagnostic_samples=args.diagnostic_samples,
        dry_run=args.dry_run,
    )
