SELECT
    w.username,
    m.rating_key,
    m.title,
	m.show_title,
	m.rating,
    m.year,
    m.media_type,
	m.summary,
    COALESCE(g.genre_tags, '') AS genre_tags,
    COALESCE(a.actor_tags, '') AS actor_tags,
    COALESCE(d.director_tags, '') AS director_tags,
    w.percent_complete,
    w.watched_at
    --w.completed_at
FROM watch_history w
JOIN library m ON w.rating_key = m.rating_key
LEFT JOIN (
    SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
    FROM media_genres mg
    JOIN genres g ON mg.genre_id = g.id
    GROUP BY mg.media_id
) g ON g.media_id = m.rating_key
LEFT JOIN (
    SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_tags
    FROM media_actors ma
    JOIN actors a ON ma.actor_id = a.id
    GROUP BY ma.media_id
) a ON a.media_id = m.rating_key
LEFT JOIN (
    SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_tags
    FROM media_directors md
    JOIN directors d ON md.director_id = d.id
    GROUP BY md.media_id
) d ON d.media_id = m.rating_key
--WHERE w.username = 'jmnovak'
ORDER BY w.watched_at DESC NULLS LAST, w.watched_at DESC;

SELECT rating_key, title, show_title
FROM library
WHERE rating_key IN (
  -- paste rating_keys from your top items in dim 625
);


SELECT DISTINCT m.media_type, m.title, m.show_title
FROM library m
WHERE m.media_type = 'episode'
ORDER BY m.title
LIMIT 20;

SELECT * FROM training_data WHERE rating_key = 32353;

SELECT * FROM media_embeddings WHERE rating_key = 32353;

SELECT * FROM recommendations WHERE rating_key = 32353;

ALTER TABLE shap_impact
ADD COLUMN modified_at TIMESTAMP DEFAULT NOW();

TRUNCATE TABLE shap_impact;


SELECT 
  r.rating_key,
  r.username,
  uv.friendly_name,
  r.scored_at,
  m.media_type,
  m.show_title,
  m.title,
  m.season_number,
  m.episode_number,
  m.year,
  string_agg(DISTINCT g.name, ', ') AS genres,
  r.predicted_probability,
  string_agg(DISTINCT el.label, ', ') AS top_labels
FROM recommendations r
JOIN library m ON r.rating_key = m.rating_key
JOIN users_v uv ON r.username = uv.username
LEFT JOIN media_genres mg ON mg.media_id = m.rating_key
LEFT JOIN genres g ON mg.genre_id = g.id
LEFT JOIN LATERAL unnest(r.top_shap_dims) AS dim(d) ON TRUE
LEFT JOIN embedding_labels el ON el.dimension = dim.d
GROUP BY 
  r.rating_key, r.username, uv.friendly_name, r.scored_at,
  m.media_type, m.show_title, m.title, m.season_number, 
  m.episode_number, m.year, r.predicted_probability
ORDER BY r.predicted_probability DESC;

SELECT 
  r.rating_key,
  r.username,
  uv.friendly_name,
  r.scored_at,
  m.media_type,
  m.show_title,
  m.title,
  m.season_number,
  m.episode_number,
  m.year,
  string_agg(DISTINCT g.name, ', ') AS genres,
  r.predicted_probability,
  string_agg(DISTINCT el.label, ', ') AS top_labels
FROM recommendations r
JOIN library m ON r.rating_key = m.rating_key
JOIN users_v uv ON r.username = uv.username
LEFT JOIN media_genres mg ON mg.media_id = m.rating_key
LEFT JOIN genres g ON mg.genre_id = g.id

-- 💡 Join to shap_impact to find top impacting dimensions
LEFT JOIN LATERAL (
  SELECT dimension
  FROM shap_impact
  WHERE user_id = r.username AND rating_key = r.rating_key
  ORDER BY ABS(shap_value) DESC
  LIMIT 3
) top_dims ON TRUE
-- 💡 Join to embedding_labels to get human-readable labels
LEFT JOIN embedding_labels el ON el.dimension = top_dims.dimension
GROUP BY 
  r.rating_key, r.username, uv.friendly_name, r.scored_at,
  m.media_type, m.show_title, m.title, m.season_number, 
  m.episode_number, m.year, r.predicted_probability
ORDER BY r.predicted_probability DESC;




SELECT 
  r.rating_key,
  r.username,
  uv.friendly_name,
  r.scored_at,
  m.media_type,
  m.show_title,
  m.title,
  m.season_number,
  m.episode_number,
  m.year,
  string_agg(DISTINCT g.name, ', ') AS genres,
  r.predicted_probability,
  string_agg(DISTINCT el.label, ', ') AS top_labels
FROM recommendations r
JOIN library m ON r.rating_key = m.rating_key
JOIN users_v uv ON r.username = uv.username
LEFT JOIN media_genres mg ON mg.media_id = m.rating_key
LEFT JOIN genres g ON mg.genre_id = g.id
-- ✅ Move LATERAL to after a valid FROM/JOIN clause
LEFT JOIN LATERAL (
  SELECT dimension
  FROM shap_impact
  WHERE user_id = r.username AND rating_key = r.rating_key
  ORDER BY ABS(shap_value) DESC
  LIMIT 3
) top_dims ON TRUE
LEFT JOIN embedding_labels el ON el.dimension = top_dims.dimension
where uv.friendly_name like 'Jason%'
GROUP BY 
  r.rating_key, r.username, uv.friendly_name, r.scored_at,
  m.media_type, m.show_title, m.title, m.season_number, 
  m.episode_number, m.year, r.predicted_probability
ORDER BY r.predicted_probability DESC;

SELECT DATE(modified_at), COUNT(*)
FROM shap_impact
GROUP BY 1
ORDER BY 1 DESC;

SELECT dimension, COUNT(*) AS usage_count
FROM shap_impact
WHERE dimension NOT IN (SELECT dimension FROM embedding_labels)
GROUP BY dimension
ORDER BY usage_count DESC
LIMIT 10;

SELECT COUNT(*) AS unlabeled_dims
FROM (
    SELECT dimension
    FROM shap_impact
    WHERE dimension NOT IN (SELECT dimension FROM embedding_labels)
    GROUP BY dimension
) sub;

SELECT count (*) FROM public.shap_impact

CREATE INDEX idx_shap_dimension ON shap_impact (dimension);

CREATE INDEX ON shap_impact (modified_at);

VACUUM FULL shap_impact;

DELETE FROM shap_impact
WHERE (user_id, rating_key, modified_at) NOT IN (
    SELECT user_id, rating_key, MAX(modified_at)
    FROM shap_impact
    GROUP BY user_id, rating_key
);

select * from shap_impact
WHERE (user_id, rating_key, modified_at) NOT IN (
    SELECT user_id, rating_key, MAX(modified_at)
    FROM shap_impact
    GROUP BY user_id, rating_key

DELETE FROM shap_impact
WHERE ctid NOT IN (
    SELECT MAX(ctid)
    FROM shap_impact
    GROUP BY user_id, rating_key, dimension
);

SELECT MAX(modified_at) FROM shap_impact;

DELETE FROM shap_impact
WHERE modified_at < '2025-04-17 03:00:00';


VACUUM FULL shap_impact;

ANALYZE shap_impact;


SELECT dimension, COUNT(*) AS usage_count
FROM shap_impact
WHERE dimension NOT IN (SELECT dimension FROM embedding_labels)
GROUP BY dimension
ORDER BY usage_count DESC
LIMIT 10;

