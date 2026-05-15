-- Read-only validation queries for actor_* feature leakage/show-proxy diagnostics.
-- Change the target_actors VALUES list as needed.

-- 1. Actor media distribution: which media items contain the target actors?
WITH target_actors(actor_name) AS (
    VALUES ('Drew Powell'), ('Michael McKean')
)
SELECT
    a.name AS actor_name,
    l.rating_key,
    l.title,
    l.media_type,
    parent.title AS parent_title,
    COALESCE(NULLIF(l.show_title, ''), show.title) AS grandparent_title,
    l.year
FROM media_actors ma
JOIN actors a ON a.id = ma.actor_id
JOIN target_actors ta ON ta.actor_name = a.name
JOIN library l ON l.rating_key = ma.media_id
LEFT JOIN library parent ON parent.rating_key = l.parent_rating_key
LEFT JOIN library show ON show.rating_key = l.show_rating_key
ORDER BY
    a.name,
    COALESCE(l.show_rating_key, l.rating_key),
    l.media_type,
    l.season_number NULLS LAST,
    l.episode_number NULLS LAST,
    l.rating_key;

-- 2. Actor show/movie concentration for model-relevant rows.
WITH target_actors(actor_name) AS (
    VALUES ('Drew Powell'), ('Michael McKean')
)
SELECT
    a.name AS actor_name,
    COALESCE(NULLIF(l.show_title, ''), show.title, l.title) AS show_or_movie,
    COUNT(*) AS item_count,
    COUNT(*) FILTER (WHERE l.media_type = 'episode') AS episode_count,
    COUNT(*) FILTER (WHERE l.media_type = 'movie') AS movie_count
FROM media_actors ma
JOIN actors a ON a.id = ma.actor_id
JOIN target_actors ta ON ta.actor_name = a.name
JOIN library l ON l.rating_key = ma.media_id
LEFT JOIN library show ON show.rating_key = l.show_rating_key
WHERE l.media_type IN ('movie', 'episode')
GROUP BY a.name, COALESCE(NULLIF(l.show_title, ''), show.title, l.title)
ORDER BY a.name, item_count DESC, show_or_movie;

-- 3. Actor training label distribution.
WITH target_actors(actor_name) AS (
    VALUES ('Drew Powell'), ('Michael McKean')
)
SELECT
    a.name AS actor_name,
    COUNT(*) AS training_rows,
    COUNT(DISTINCT td.username) AS training_user_count,
    COUNT(DISTINCT td.rating_key) AS training_item_count,
    SUM(CASE WHEN td.label = 1 THEN 1 ELSE 0 END) AS positive_training_rows,
    SUM(CASE WHEN td.label = 0 THEN 1 ELSE 0 END) AS negative_training_rows,
    ROUND(AVG(td.label::numeric), 3) AS positive_rate,
    COALESCE(td.engagement_type, td.label_source, 'unknown') AS engagement_type
FROM training_data td
JOIN media_actors ma ON ma.media_id = td.rating_key
JOIN actors a ON a.id = ma.actor_id
JOIN target_actors ta ON ta.actor_name = a.name
GROUP BY a.name, COALESCE(td.engagement_type, td.label_source, 'unknown')
ORDER BY a.name, training_rows DESC;

-- 4. Top suspicious actors by episode concentration and show/movie concentration.
WITH actor_media AS (
    SELECT
        a.id AS actor_id,
        a.name AS actor_name,
        l.rating_key,
        l.media_type,
        COALESCE(l.show_rating_key, l.rating_key) AS show_or_movie_key,
        COALESCE(NULLIF(l.show_title, ''), show.title, l.title) AS show_or_movie
    FROM media_actors ma
    JOIN actors a ON a.id = ma.actor_id
    JOIN library l ON l.rating_key = ma.media_id
    LEFT JOIN library show ON show.rating_key = l.show_rating_key
    WHERE l.media_type IN ('movie', 'episode')
),
media_counts AS (
    SELECT
        actor_id,
        actor_name,
        COUNT(*) AS media_item_count,
        COUNT(*) FILTER (WHERE media_type = 'episode') AS episode_count,
        COUNT(*) FILTER (WHERE media_type = 'movie') AS movie_count,
        COUNT(DISTINCT show_or_movie_key) AS distinct_show_or_movie_count
    FROM actor_media
    GROUP BY actor_id, actor_name
),
show_counts AS (
    SELECT
        actor_id,
        show_or_movie,
        COUNT(*) AS show_item_count,
        ROW_NUMBER() OVER (
            PARTITION BY actor_id
            ORDER BY COUNT(*) DESC, show_or_movie
        ) AS rn
    FROM actor_media
    GROUP BY actor_id, show_or_movie
),
training_counts AS (
    SELECT
        a.id AS actor_id,
        COUNT(*) AS training_rows,
        SUM(CASE WHEN td.label = 1 THEN 1 ELSE 0 END) AS positive_training_rows,
        SUM(CASE WHEN td.label = 0 THEN 1 ELSE 0 END) AS negative_training_rows,
        AVG(td.label::numeric) AS positive_rate
    FROM training_data td
    JOIN media_actors ma ON ma.media_id = td.rating_key
    JOIN actors a ON a.id = ma.actor_id
    GROUP BY a.id
)
SELECT
    mc.actor_name,
    mc.media_item_count,
    mc.episode_count,
    mc.movie_count,
    mc.distinct_show_or_movie_count,
    sc.show_or_movie AS top_show_or_movie,
    sc.show_item_count AS top_show_item_count,
    COALESCE(tc.positive_training_rows, 0) AS positive_training_rows,
    COALESCE(tc.negative_training_rows, 0) AS negative_training_rows,
    ROUND(tc.positive_rate, 3) AS positive_rate,
    CASE
        WHEN mc.media_item_count >= 10
         AND mc.episode_count::numeric / NULLIF(mc.media_item_count, 0) >= 0.80
         AND mc.distinct_show_or_movie_count <= 2
            THEN 'mostly episodes in one or two shows'
        WHEN mc.media_item_count >= 10
         AND sc.show_item_count::numeric / NULLIF(mc.media_item_count, 0) >= 0.75
            THEN 'top show/movie dominates actor rows'
        WHEN tc.positive_rate >= 0.80
            THEN 'positive-label skew'
        WHEN tc.positive_rate <= 0.20
            THEN 'negative-label skew'
        ELSE 'review'
    END AS suspicious_reason
FROM media_counts mc
LEFT JOIN show_counts sc ON sc.actor_id = mc.actor_id AND sc.rn = 1
LEFT JOIN training_counts tc ON tc.actor_id = mc.actor_id
WHERE mc.media_item_count >= 10
ORDER BY
    (mc.episode_count::numeric / NULLIF(mc.media_item_count, 0)) DESC,
    mc.distinct_show_or_movie_count ASC,
    mc.media_item_count DESC
LIMIT 50;

-- 5. Top actor SHAP features, only if shap_impact has feature_name.
-- The current schema stores shap_impact.dimension as an embedding dimension only,
-- so actor_* feature names are not queryable from shap_impact unless scoring is
-- extended to persist non-embedding feature names.
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'shap_impact'
ORDER BY ordinal_position;

-- If a future shap_impact schema includes feature_name, run:
-- SELECT
--     feature_name,
--     COUNT(*) AS top_feature_rows,
--     COUNT(DISTINCT user_id) AS user_count,
--     COUNT(DISTINCT rating_key) AS item_count,
--     AVG(shap_value) AS avg_shap_value,
--     AVG(ABS(shap_value)) AS avg_abs_shap_value
-- FROM shap_impact
-- WHERE feature_name LIKE 'actor_%'
-- GROUP BY feature_name
-- ORDER BY top_feature_rows DESC, avg_abs_shap_value DESC
-- LIMIT 50;
