import numpy as np

from build_training_data import add_leave_one_out_user_embedding
from user_profile_embeddings import (
    build_user_profiles,
    fuse_media_and_user_embedding,
)


THRESHOLD = 0.5


def profile_row(rating_key, embedding, *, ratio=0.75, watch_count=1):
    return {
        "username": "user",
        "rating_key": rating_key,
        "watch_count": watch_count,
        "max_engagement_ratio": ratio,
        "media_embedding": embedding,
    }


def build_profile(*rows):
    return build_user_profiles(
        rows,
        engagement_threshold=THRESHOLD,
    )


def test_positive_qualifying_title_is_left_out():
    vectors = {
        "A": np.array([1.0, 2.0]),
        "B": np.array([3.0, 4.0]),
        "C": np.array([7.0, 8.0]),
    }
    profiles = build_profile(*(profile_row(key, value) for key, value in vectors.items()))

    training_row, result = add_leave_one_out_user_embedding(
        {"username": "user", "rating_key": "A"},
        profiles,
    )

    np.testing.assert_allclose(training_row["user_embedding"], np.mean([vectors["B"], vectors["C"]], axis=0))
    assert result.current_title_in_profile is True
    assert result.current_title_excluded is True
    assert result.training_count == 2


def test_nonqualifying_title_uses_complete_profile():
    vectors = {
        "A": np.array([1.0, 2.0]),
        "B": np.array([3.0, 4.0]),
        "C": np.array([7.0, 8.0]),
    }
    rows = [profile_row(key, value) for key, value in vectors.items()]
    rows.append(profile_row("D", np.array([100.0, 100.0]), ratio=0.2))
    profiles = build_profile(*rows)

    training_row, result = add_leave_one_out_user_embedding(
        {"username": "user", "rating_key": "D"},
        profiles,
    )

    np.testing.assert_allclose(training_row["user_embedding"], np.mean(list(vectors.values()), axis=0))
    assert result.current_title_in_profile is False
    assert result.current_title_excluded is False
    assert result.training_count == 3


def test_only_qualifying_title_skips_without_self_fallback():
    vector_a = np.array([1.0, 2.0])
    profiles = build_profile(profile_row("A", vector_a))

    training_row, result = add_leave_one_out_user_embedding(
        {"username": "user", "rating_key": "A"},
        profiles,
    )

    assert training_row is None
    assert result.embedding is None
    assert result.current_title_excluded is True
    assert result.training_count == 0


def test_multiple_watch_records_still_contribute_one_title_vector():
    # The bulk SQL aggregates the repeated events into watch_count=5. The
    # profile builder receives one row and therefore stores one vector for A.
    vector_a = np.array([2.0, 4.0])
    vector_b = np.array([6.0, 8.0])
    profiles = build_profile(
        profile_row("A", vector_a, ratio=0.2, watch_count=5),
        profile_row("B", vector_b),
    )

    assert profiles["user"].count == 2
    training_row, result = add_leave_one_out_user_embedding(
        {"username": "user", "rating_key": "A"},
        profiles,
    )
    np.testing.assert_allclose(training_row["user_embedding"], vector_b)
    assert result.training_count == 1


def test_fused_embedding_is_media_then_leave_one_out_user():
    media = np.array([10.0, 20.0, 30.0])
    loo_user = np.array([1.0, 2.0, 3.0])

    fused = fuse_media_and_user_embedding(media, loo_user)

    assert fused.size == 2 * media.size
    np.testing.assert_array_equal(fused[: media.size], media)
    np.testing.assert_array_equal(fused[media.size :], loo_user)

