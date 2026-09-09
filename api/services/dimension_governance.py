"""Shared administrative controls and serialization for every labeling entry point."""
from contextlib import contextmanager, closing
import json
import os

from fastapi import HTTPException
from psycopg2.extras import Json, RealDictCursor

from api.db.connection import connect_db
from api.services.dimension_config import get_active_config, identity

LOCK_NAMESPACE = 184724


def automatic_review_allowed_sql(dimension_expression):
    return f'''NOT EXISTS (SELECT 1 FROM public.embedding_dimension_admin admin_dimension
        JOIN public.embedding_feature_config admin_config USING(config_id)
        WHERE admin_config.active AND admin_dimension.dimension = {dimension_expression}
          AND admin_dimension.paused)'''


@contextmanager
def dimension_review_guard(cur, dimension):
    """Session lock spans LLM I/O and commits. Pause does not cancel in-flight work."""
    cur.execute('SELECT pg_try_advisory_lock(%s, %s)', (LOCK_NAMESPACE, dimension))
    locked = cur.fetchone()[0]
    try:
        if not locked:
            yield False
            return
        cur.execute('SELECT ' + automatic_review_allowed_sql('%s'), (dimension,))
        yield bool(cur.fetchone()[0])
    finally:
        if locked:
            cur.execute('SELECT pg_advisory_unlock(%s, %s)', (LOCK_NAMESPACE, dimension))


def json_safe(value):
    if hasattr(value, 'to_json'):
        return json.loads(value.to_json(orient='records', date_format='iso'))
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def record_assessment(cur, dimension, *, source, provider, model, prompt, result, saved, outcome, before, after):
    cur.execute('SELECT config_id FROM embedding_feature_config WHERE active')
    row = cur.fetchone()
    if not row:  # Registration is explicit; never invent a configuration association.
        return
    config_id = row['config_id'] if isinstance(row, dict) else row[0]
    review_id = None
    requested_id = os.getenv('PLEXINTEL_DIMENSION_REVIEW_ID')
    if requested_id:
        cur.execute("SELECT review_id FROM embedding_dimension_reviews WHERE review_id=%s AND config_id=%s AND dimension=%s AND status='running'",
                    (int(requested_id),config_id,dimension))
        request = cur.fetchone()
        if request:
            review_id = request['review_id'] if isinstance(request,dict) else request[0]
    cur.execute('''INSERT INTO embedding_dimension_assessments
        (config_id, dimension, source, provider, model, prompt, result, saved, outcome, before_state, after_state, review_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (config_id, dimension, source, provider, model, Json(json_safe(prompt)), Json(json_safe(result)),
         saved, outcome, Json(json_safe(before)), Json(json_safe(after)), review_id))


def apply_action(config_id, dimension, actor, action, reason, version):
    if not reason.strip():
        raise HTTPException(422, 'A reason is required for every intervention')
    with closing(connect_db(cursor_factory=RealDictCursor)) as conn, conn:
        with conn.cursor() as cur:
            config = get_active_config(cur)
            if config['config_id'] != config_id:
                raise HTTPException(409, 'Configuration changed; reload the explorer')
            identity(config, dimension)
            if action == 'review' and (config['media_dimensions'],config['user_dimensions']) != (768,768):
                raise HTTPException(409, 'The current labeling implementation supports 768 dimensions per side; review requires a compatible labeling implementation')
            cur.execute('''INSERT INTO embedding_dimension_admin(config_id, dimension) VALUES (%s,%s)
                ON CONFLICT DO NOTHING''', (config_id, dimension))
            cur.execute('SELECT * FROM embedding_dimension_admin WHERE config_id=%s AND dimension=%s FOR UPDATE',
                        (config_id, dimension))
            before = dict(cur.fetchone())
            if action == 'review':
                cur.execute("""SELECT * FROM embedding_dimension_reviews WHERE config_id=%s AND dimension=%s
                    AND status IN ('queued','running')""", (config_id, dimension))
                pending = cur.fetchone()
                if pending:
                    return dict(pending)  # An idempotent repeat is not another observed action.
            if before['version'] != version:
                raise HTTPException(409, 'State changed; reload before applying this action')
            updates = dict(before)
            if action == 'review':
                cur.execute('SELECT COUNT(*) AS count FROM embedding_labels WHERE dimension=%s',(dimension,))
                if cur.fetchone()['count'] > 1:
                    raise HTTPException(409,'Multiple saved rows for this dimension; investigate the existing data conflict before requesting review')
                if before['paused']:
                    raise HTTPException(409, 'Resume automatic review before requesting an assessment')
                cur.execute('''INSERT INTO embedding_dimension_reviews(config_id,dimension,requested_by,reason)
                    VALUES (%s,%s,%s,%s) RETURNING *''', (config_id,dimension,actor,reason.strip()))
                result = dict(cur.fetchone())
            elif action in ('pause', 'resume'):
                updates['paused'] = action == 'pause'
            elif action in ('suppress', 'restore'):
                updates['suppressed'] = action == 'suppress'
            elif action in ('investigate', 'clear'):
                updates['investigation_status'] = 'open' if action == 'investigate' else 'clear'
                updates['investigation_reason'] = reason.strip()
            else:
                raise HTTPException(422, 'Unknown intervention')
            updates['version'] += 1
            cur.execute('''UPDATE embedding_dimension_admin SET paused=%s,suppressed=%s,
                investigation_status=%s,investigation_reason=%s,version=%s WHERE config_id=%s AND dimension=%s''',
                (updates['paused'],updates['suppressed'],updates['investigation_status'],updates['investigation_reason'],
                 updates['version'],config_id,dimension))
            after = dict(updates)
            if action == 'review':
                after['queued_review_id'] = result['review_id']
            cur.execute('''INSERT INTO embedding_dimension_actions
                (config_id,dimension,actor,action,reason,before_state,after_state) VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                (config_id,dimension,actor,action,reason.strip(),Json(before),Json(after)))
            return result if action == 'review' else updates
