"""Shared construction of title-level user preference profiles."""

from dataclasses import dataclass

import numpy as np
from pgvector import Vector
from psycopg2.extras import RealDictCursor


MIN_PROFILE_WATCH_COUNT = 5


def parse_profile_embedding(value):
    if isinstance(value, Vector):
        value = value.to_numpy()
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"Expected a non-empty 1-D embedding, got shape {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError("Embedding contains non-finite values")
    return array


def qualifies_for_user_profile(
    max_engagement_ratio,
    watch_count,
    *,
    engagement_threshold,
):
    """Keep this business rule identical for production and training profiles."""
    ratio = float(max_engagement_ratio or 0.0)
    return ratio > float(engagement_threshold) or int(watch_count or 0) >= MIN_PROFILE_WATCH_COUNT


def fetch_profile_title_rows(conn):
    """Fetch one aggregate row and one media vector per watched user/title pair."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            WITH watch_stats AS (
                SELECT
                    wh.username,
                    wh.rating_key,
                    COUNT(*) AS watch_count,
                    MAX(
                        wh.played_duration::float /
                        NULLIF(l.duration / 1000.0, 0)
                    ) AS max_engagement_ratio
                FROM watch_history wh
                JOIN library l ON l.rating_key = wh.rating_key
                WHERE wh.played_duration IS NOT NULL
                  AND l.duration IS NOT NULL
                  AND l.duration > 0
                GROUP BY wh.username, wh.rating_key
            )
            SELECT
                ws.username,
                ws.rating_key,
                ws.watch_count,
                ws.max_engagement_ratio,
                me.embedding AS media_embedding
            FROM watch_stats ws
            JOIN media_embeddings me ON me.rating_key = ws.rating_key
            ORDER BY ws.username, ws.rating_key
            """
        )
        return cur.fetchall()


@dataclass(frozen=True)
class UserProfile:
    vectors_by_rating_key: dict
    eligible_sum: np.ndarray
    dimension: int

    @property
    def count(self):
        return len(self.vectors_by_rating_key)

    @property
    def mean(self):
        return self.eligible_sum / self.count


@dataclass(frozen=True)
class TrainingProfileResult:
    embedding: np.ndarray | None
    qualifying_count: int
    training_count: int
    current_title_in_profile: bool
    current_title_excluded: bool


def build_user_profiles(rows, *, engagement_threshold, expected_dimension=None):
    """Build complete title-deduplicated profiles from aggregate query rows."""
    vectors_by_user = {}
    detected_dimension = expected_dimension

    for row in rows:
        if not qualifies_for_user_profile(
            row.get("max_engagement_ratio"),
            row.get("watch_count"),
            engagement_threshold=engagement_threshold,
        ):
            continue

        username = row["username"]
        rating_key = row["rating_key"]
        vector = parse_profile_embedding(row["media_embedding"])
        if detected_dimension is None:
            detected_dimension = vector.size
        if vector.size != detected_dimension:
            raise ValueError(
                f"Embedding dimension mismatch for {username}/{rating_key}: "
                f"expected {detected_dimension}, got {vector.size}"
            )

        user_vectors = vectors_by_user.setdefault(username, {})
        if rating_key in user_vectors:
            raise AssertionError(
                f"Duplicate aggregate profile row for {username}/{rating_key}; "
                "each title must contribute exactly once"
            )
        user_vectors[rating_key] = vector

    profiles = {}
    for username, vectors in vectors_by_user.items():
        matrix = np.stack(list(vectors.values()))
        profiles[username] = UserProfile(
            vectors_by_rating_key=vectors,
            eligible_sum=matrix.sum(axis=0, dtype=np.float64),
            dimension=matrix.shape[1],
        )
    return profiles


def leave_one_title_out(profile, current_rating_key):
    """Return an O(1) training profile that cannot contain its current title."""
    in_profile = current_rating_key in profile.vectors_by_rating_key
    if not in_profile:
        return TrainingProfileResult(
            embedding=profile.mean,
            qualifying_count=profile.count,
            training_count=profile.count,
            current_title_in_profile=False,
            current_title_excluded=False,
        )

    # The only permitted path for an eligible current title subtracts its one
    # title-level vector before division. There is deliberately no fallback to
    # the complete profile when no vectors remain.
    remaining_count = profile.count - 1
    if remaining_count == 0:
        return TrainingProfileResult(
            embedding=None,
            qualifying_count=profile.count,
            training_count=0,
            current_title_in_profile=True,
            current_title_excluded=True,
        )

    current_vector = profile.vectors_by_rating_key[current_rating_key]
    remaining_sum = profile.eligible_sum - current_vector
    assert remaining_count == len(profile.vectors_by_rating_key) - 1
    result = remaining_sum / remaining_count
    return TrainingProfileResult(
        embedding=result,
        qualifying_count=profile.count,
        training_count=remaining_count,
        current_title_in_profile=True,
        current_title_excluded=True,
    )


def fuse_media_and_user_embedding(media_embedding, user_embedding):
    """Preserve the model contract: media dimensions, then user dimensions."""
    media = parse_profile_embedding(media_embedding)
    user = parse_profile_embedding(user_embedding)
    if media.size != user.size:
        raise ValueError(
            f"Media/user embedding dimension mismatch: {media.size} != {user.size}"
        )
    fused = np.concatenate([media, user])
    assert fused.size == 2 * media.size
    assert np.array_equal(fused[: media.size], media)
    assert np.array_equal(fused[media.size :], user)
    return fused
