"""Server-side register, scoped retained-contribution statistics and traceability."""
import os
from contextlib import contextmanager, nullcontext
from psycopg2.extras import RealDictCursor
from api.db.connection import connect_db
from api.services.dimension_config import get_active_config, identity

REPEATED_ATTEMPTS = max(1, int(os.getenv('DIMENSION_EXPLORER_REPEATED_ATTEMPTS', '3')))
FREQUENT_SELECTIONS = max(1, int(os.getenv('DIMENSION_EXPLORER_FREQUENT_SELECTIONS', '10')))
LIMITATIONS = [
    'Current snapshots only. Older observations are isolated in the unversioned legacy scope; their model identity and pairing with scored_at cannot be verified. New scoring contexts retain model fingerprints and prediction timestamps. Incompatible or stale contexts are excluded, never combined with legacy observations.',
    'Mean absolute magnitude uses finite observed values only; unknown/non-finite contributions are excluded from that mean and counted separately. All contribution signs and zeros describe stored values.',
    'Statistics cover retained embedding contributions on selected SHAP targets, not all model usage. Missing SHAP is unknown, never zero. Signs are retained; non-finite values have unknown sign.',
    'Selected by current explanation rules is a reconstruction using current wording and overrides, not historical display events. It describes selection if rendered, not whether a user saw the card.',
    'Title traits and taste matches each select up to three positive eligible wordings. Legacy semantic themes select up to three across both sides. A wording counts once per prediction/group, with all eligible contributing dimensions attributed.',
    'Show/season API rollups have empty explanation groups. Leaf contributions do not explain an aggregated score.',
    'The verified binary:logistic model uses raw margin (log-odds) contributions, not probability percentage points. Legacy output units lack a per-prediction model association. Non-embedding contributions and compatible prediction base values are not retained; no additive reconstruction is available.',
    'If duplicate label rows exist for a dimension, the register shows the latest timestamped row and flags the conflict; production selection still reflects all saved rows. No label records are deleted or merged.',
    'Older prompt evidence, rejected candidates and displayed wording were not recorded in the database. Existing wording history is partial and has no model/configuration identity.',
]


@contextmanager
def reader():
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '30s'")
            yield cur
    finally:
        conn.rollback()
        conn.close()


def resolve_scope(cur, scope, config):
    cur.execute("""SELECT c.model_version,MAX(c.generated_at) AS generated_at
        FROM shap_prediction_context c JOIN recommendations r
          ON r.username=c.username AND r.rating_key=c.rating_key AND r.scored_at=c.scored_at
        WHERE c.config_id=%s GROUP BY c.model_version ORDER BY generated_at DESC""", (config['config_id'],))
    versions = [dict(row) for row in cur.fetchall()]
    selected = scope.get('model_version') or (versions[0]['model_version'] if versions else 'legacy')
    if selected != 'legacy' and selected not in [v['model_version'] for v in versions]:
        raise ValueError('Selected model snapshot is no longer retained; refresh the register')
    return dict(scope, model_version=selected), versions


def scope_cte(scope, config):
    where, params = ['TRUE'], []
    if scope.get('model_version', 'legacy') == 'legacy':
        where.append('context.username IS NULL')
    else:
        where.append('context.config_id=%s AND context.model_version=%s AND context.scored_at=r.scored_at')
        params += [config['config_id'], scope['model_version']]
    if scope.get('username'):
        where.append('r.username=%s'); params.append(scope['username'])
    if scope.get('media_type'):
        where.append('l.media_type=%s'); params.append(scope['media_type'])
    if scope.get('top_n'):
        where.append('r.rank <= %s'); params.append(scope['top_n'])
    # recommendations is a current snapshot; dedup protects older installations lacking uniqueness.
    sql = '''WITH scoped AS MATERIALIZED (
        SELECT DISTINCT ON (r.username,r.rating_key) r.username,r.rating_key,r.predicted_probability,
            r.rank,r.scored_at,r.model_name,l.title,l.media_type,l.show_rating_key,l.parent_rating_key
        FROM recommendations r JOIN library l USING(rating_key)
        LEFT JOIN shap_prediction_context context ON context.username=r.username AND context.rating_key=r.rating_key
        WHERE ''' + ' AND '.join(where) + '''
        ORDER BY r.username,r.rating_key,r.scored_at DESC NULLS LAST
    ), observations AS MATERIALIZED (
        SELECT DISTINCT ON (s.user_id,s.rating_key,s.dimension) s.user_id,s.rating_key,s.dimension,
            CASE WHEN s.shap_value::text IN ('NaN','Infinity','-Infinity') THEN NULL ELSE s.shap_value END AS shap_value,
            s.modified_at
        FROM shap_impact s JOIN scoped r ON r.username=s.user_id AND r.rating_key=s.rating_key
        ORDER BY s.user_id,s.rating_key,s.dimension,s.modified_at DESC NULLS LAST
    ), selected AS MATERIALIZED (
        SELECT r.username,r.rating_key,g.group_name,labels.*
        FROM scoped r CROSS JOIN (VALUES
            ('title_traits',0,''' + str(config['media_dimensions']) + '''),
            ('taste_match',''' + str(config['media_dimensions']) + ',' + str(config['media_dimensions'] + config['user_dimensions']) + '''),
            ('semantic_themes',0,2147483647)
        ) AS g(group_name,dim_start,dim_end)
        CROSS JOIN LATERAL selected_embedding_labels(r.username,r.rating_key,g.dim_start,g.dim_end,3) labels
        WHERE (g.group_name='semantic_themes' OR r.media_type NOT IN ('show','season','series'))
          AND EXISTS (SELECT 1 FROM observations o WHERE o.user_id=r.username AND o.rating_key=r.rating_key)
    )'''
    return sql, params


def register_cte(scope, config):
    sql, params = scope_cte(scope, config)
    sql += ''', running_dimensions AS MATERIALIZED (
        SELECT objid::integer AS dimension FROM pg_locks
        WHERE locktype='advisory' AND classid=184724 AND objsubid=2 AND granted
          AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
    ), contribution_stats AS (
        SELECT dimension,COUNT(*) AS observed_count,AVG(ABS(shap_value)) AS mean_abs_shap,
            COUNT(*) FILTER(WHERE shap_value>0) AS positive_count,
            COUNT(*) FILTER(WHERE shap_value<0) AS negative_count,
            COUNT(*) FILTER(WHERE shap_value=0) AS zero_count,
            COUNT(*) FILTER(WHERE shap_value IS NULL) AS unknown_count,
            MAX(modified_at) AS shap_timestamp FROM observations GROUP BY dimension
    ), selection_stats AS (
        SELECT dimension,
            COUNT(*) FILTER(WHERE group_name!='semantic_themes') AS selected_count,
            COUNT(*) FILTER(WHERE group_name='semantic_themes') AS semantic_selected_count
        FROM selected CROSS JOIN LATERAL unnest(dimensions) AS dimension GROUP BY dimension
    ), register AS (
        SELECT i.dimension,CASE WHEN i.dimension<%s THEN 'media' ELSE 'user' END AS side,
            CASE WHEN i.dimension<%s THEN i.dimension ELSE i.dimension-%s END AS local_index,
            el.label,el.display_label,el.label_type,el.explainable,el.needs_review,el.label_row_count,
            EXISTS(SELECT 1 FROM running_dimensions rd WHERE rd.dimension=i.dimension) AS in_flight,
            el.updated_at,el.last_reviewed_at,COALESCE(el.review_attempt_count,0) AS review_attempt_count,
            el.next_review_at,COALESCE(a.paused,false) AS paused,COALESCE(a.suppressed,false) AS suppressed,
            COALESCE(a.investigation_status,'clear') AS investigation_status,a.investigation_reason,
            COALESCE(a.version,0) AS version,
            (el.explainable IS TRUE AND NOT COALESCE(el.needs_review,false)
                AND NULLIF(BTRIM(el.display_label),'') IS NOT NULL AND NOT COALESCE(a.suppressed,false)) AS eligible,
            (COALESCE(el.needs_review,false) AND (el.next_review_at IS NULL OR el.next_review_at<=now())) AS due,
            (el.next_review_at>now()) AS cooldown,
            COALESCE(cs.observed_count,0) AS observed_count,cs.mean_abs_shap,
            cs.positive_count,cs.negative_count,cs.zero_count,cs.unknown_count,cs.shap_timestamp,
            COALESCE(ss.selected_count,0) AS selected_count,
            COALESCE(ss.semantic_selected_count,0) AS semantic_selected_count,
            recent.result->>'validation_status' AS validation_status,recent.outcome,
            (recent.outcome IN ('invalid_review_replacement_not_saved','non_semantic_repair_not_saved')
                OR (recent.outcome='repair_cooldown_scheduled' AND jsonb_typeof(recent.before_state)='object'
                    AND recent.result->>'label' NOT IN ('','UNCLEAR / MIXED SIGNAL')
                    AND COALESCE(recent.result->>'processing_error','false')!='true')) AS rejected_replacement,
            job.status AS job_status,COALESCE(job.error, CASE WHEN recent.result->>'processing_error'='true' THEN 'Labeling provider error' END) AS processing_error
        FROM generate_series(0,%s-1) AS i(dimension)
        LEFT JOIN LATERAL (SELECT saved.*,COUNT(*) OVER() AS label_row_count FROM embedding_labels saved
            WHERE saved.dimension=i.dimension ORDER BY saved.updated_at DESC NULLS LAST,
                saved.created_at DESC NULLS LAST,saved.label LIMIT 1) el ON true
        LEFT JOIN embedding_dimension_admin a ON a.dimension=i.dimension AND a.config_id=%s
        LEFT JOIN contribution_stats cs ON cs.dimension=i.dimension
        LEFT JOIN selection_stats ss ON ss.dimension=i.dimension
        LEFT JOIN LATERAL (SELECT result,outcome,before_state FROM embedding_dimension_assessments h
            WHERE h.config_id=%s AND h.dimension=i.dimension ORDER BY assessment_id DESC LIMIT 1) recent ON true
        LEFT JOIN LATERAL (SELECT status,error FROM embedding_dimension_reviews q
            WHERE q.config_id=%s AND q.dimension=i.dimension ORDER BY review_id DESC LIMIT 1) job ON true
    )'''
    media = config['media_dimensions']; cid = config['config_id']
    params += [media,media,media,media+config['user_dimensions'],cid,cid,cid]
    return sql, params


STATUS_FILTERS = {
    'unlabeled': "NULLIF(BTRIM(label),'') IS NULL",
    'unresolved': 'needs_review IS TRUE',
    'due': 'due AND NOT paused',
    'overdue': 'needs_review IS TRUE AND next_review_at < now() AND NOT paused',
    'cooldown': 'cooldown IS TRUE',
    'paused': 'paused', 'suppressed': 'suppressed', 'investigation': "investigation_status='open'",
    'repeated': f'needs_review IS TRUE AND review_attempt_count >= {REPEATED_ATTEMPTS}',
    'rejected': 'rejected_replacement IS TRUE',
    'frequent_review': f'needs_review IS TRUE AND selected_count >= {FREQUENT_SELECTIONS}',
    'errors': "job_status IN ('error','interrupted') OR processing_error IS NOT NULL",
}
SORTS = {'dimension':'dimension ASC','usage':'observed_count DESC,dimension',
         'magnitude':'mean_abs_shap DESC NULLS LAST,dimension','selected':'selected_count DESC,dimension',
         'attempts':'review_attempt_count DESC,dimension','next_review':'next_review_at ASC NULLS LAST,dimension'}


def get_register(scope, search='', side='', status='', sort='dimension', offset=0, limit=50, dimension=None, _cursor=None):
    with (nullcontext(_cursor) if _cursor is not None else reader()) as cur:
        config = get_active_config(cur)
        scope, versions = resolve_scope(cur, scope, config)
        sql, params = register_cte(scope, config)
        summary_sql = ''' SELECT COUNT(*) AS inventory_count,
            COUNT(*) FILTER(WHERE NULLIF(BTRIM(label),'') IS NULL) AS unlabeled,
            COUNT(*) FILTER(WHERE needs_review IS TRUE) AS unresolved,
            COUNT(*) FILTER(WHERE due AND NOT paused) AS due,
            COUNT(*) FILTER(WHERE cooldown) AS cooldown,
            COUNT(*) FILTER(WHERE paused) AS paused,
            COUNT(*) FILTER(WHERE needs_review IS TRUE AND review_attempt_count >= %s) AS repeated,
            (SELECT COUNT(*) FROM scoped) AS scoped_predictions,
            (SELECT COUNT(DISTINCT (user_id,rating_key)) FROM observations) AS observed_predictions,
            (SELECT COUNT(*) FROM selected WHERE group_name!='semantic_themes') AS selected_wordings,
            (SELECT COUNT(*) FROM selected WHERE group_name='semantic_themes') AS semantic_selected_wordings,
            (SELECT MAX(scored_at) FROM scoped) AS scored_at,
            (SELECT MAX(modified_at) FROM observations) AS shap_timestamp
            FROM register'''
        where, extra = ['TRUE'], []
        if search:
            where.append("(label ILIKE %s OR display_label ILIKE %s OR dimension::text=%s OR ('emb_'||dimension)=%s OR (side||':'||local_index)=%s)")
            pattern = '%' + search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
            extra += [pattern,pattern,search,search,search]
        if side:
            where.append('side=%s'); extra.append(side)
        if status:
            where.append(STATUS_FILTERS[status])
        if dimension is not None:
            identity(config, dimension)
            where.append('dimension=%s'); extra.append(dimension)
        filtered = ' FROM register WHERE ' + ' AND '.join(where)
        cur.execute(sql + ', summary AS (' + summary_sql + '), filtered AS MATERIALIZED (SELECT *' + filtered +
            '), page AS (SELECT * FROM filtered ORDER BY ' + SORTS[sort] + ' LIMIT %s OFFSET %s)' +
            " SELECT (SELECT row_to_json(summary) FROM summary) AS overview, (SELECT COUNT(*) FROM filtered) AS total," +
            " COALESCE((SELECT json_agg(page) FROM page),'[]'::json) AS rows",
            params + [REPEATED_ATTEMPTS] + extra + [limit,offset])
        result = cur.fetchone()
        overview, total, rows = result['overview'], result['total'], result['rows']
        cur.execute('SELECT DISTINCT username FROM recommendations ORDER BY username')
        users = [r['username'] for r in cur.fetchall()]
        cur.execute("SELECT to_regclass('public.pipeline_run_stages') AS tracked")
        recent_runs = []
        if cur.fetchone()['tracked']:
            cur.execute("""SELECT s.run_id,s.status,s.exit_code,s.started_at,s.completed_at
                FROM pipeline_run_stages s WHERE s.stage_key='batch_label'
                ORDER BY s.started_at DESC LIMIT 5""")
            recent_runs = [dict(r) for r in cur.fetchall()]
        return dict(config=config,scope=scope,overview=overview,rows=rows,total=total,offset=offset,limit=limit,
                    users=users,recent_labeling_runs=recent_runs,model_versions=versions,limitations=LIMITATIONS,thresholds=dict(repeated_attempts=REPEATED_ATTEMPTS,frequent_selections=FREQUENT_SELECTIONS))


def get_dimension(dimension, scope, offset=0, limit=25, history_offset=0):
    with reader() as cur:
        data = get_register(scope, dimension=dimension, limit=1, _cursor=cur)
        config = data['config']
        scope = data['scope']
        sql, params = scope_cte(scope, config)
        query = ''' FROM observations o JOIN scoped r ON r.username=o.user_id AND r.rating_key=o.rating_key
            WHERE o.dimension=%s'''
        cur.execute(sql + ' SELECT COUNT(*) AS total' + query, params + [dimension])
        data['recommendation_total'] = cur.fetchone()['total']
        cur.execute(sql + ''' SELECT r.*,o.shap_value,o.modified_at AS shap_timestamp,
            ARRAY(SELECT group_name FROM selected s WHERE s.username=r.username AND s.rating_key=r.rating_key
                AND %s=ANY(s.dimensions)) AS selected_groups''' + query +
            ' ORDER BY ABS(o.shap_value) DESC NULLS LAST,r.username,r.rating_key LIMIT %s OFFSET %s',
            params + [dimension,dimension,limit,offset])
        data['recommendations'] = [dict(r) for r in cur.fetchall()]
        for key,table,order,condition,values in (
            ('history','embedding_label_history','history_id','dimension=%s',[dimension]),
            ('assessments','embedding_dimension_assessments','assessment_id','config_id=%s AND dimension=%s',[config['config_id'],dimension]),
            ('actions','embedding_dimension_actions','action_id','config_id=%s AND dimension=%s',[config['config_id'],dimension]),
            ('reviews','embedding_dimension_reviews','review_id','config_id=%s AND dimension=%s',[config['config_id'],dimension]),
        ):
            cur.execute(f'SELECT COUNT(*) AS total FROM {table} WHERE {condition}', values)
            data[key+'_total'] = cur.fetchone()['total']
            cur.execute(f'SELECT * FROM {table} WHERE {condition} ORDER BY {order} DESC LIMIT 20 OFFSET %s',values+[history_offset])
            data[key] = [dict(r) for r in cur.fetchall()]
    return data


def get_prediction(username, rating_key, scored_at, model_version):
    with reader() as cur:
        config = get_active_config(cur)
        sql, params = scope_cte(dict(username=username,model_version=model_version), config)
        cur.execute(sql + ' SELECT * FROM scoped WHERE rating_key=%s',params+[rating_key])
        row = cur.fetchone()
        if not row:
            return None
        if row['scored_at'].isoformat() != scored_at:
            from fastapi import HTTPException
            raise HTTPException(409,'This recommendation has been rescored. Return to the dimension and reload its current row.')
        cur.execute(sql + ''' SELECT o.*,el.label,el.display_label,el.label_type,
            ARRAY(SELECT group_name FROM selected s WHERE s.username=o.user_id AND s.rating_key=o.rating_key
                AND o.dimension=ANY(s.dimensions)) AS selected_groups
            FROM observations o LEFT JOIN LATERAL (SELECT saved.* FROM embedding_labels saved
                WHERE saved.dimension=o.dimension ORDER BY saved.updated_at DESC NULLS LAST,
                    saved.created_at DESC NULLS LAST,saved.label LIMIT 1) el ON true
            WHERE o.rating_key=%s ORDER BY ABS(o.shap_value) DESC NULLS LAST,o.dimension''', params+[rating_key])
        contributions = []
        for r in cur.fetchall():
            item = dict(r)
            if 0 <= item['dimension'] < config['media_dimensions'] + config['user_dimensions']:
                item.update(identity(config,item['dimension']))
            else:
                item.update(side='non-embedding / incompatible',local_index=None)
            contributions.append(item)
        cur.execute(sql + ' SELECT * FROM selected WHERE rating_key=%s',params+[rating_key])
        return dict(prediction=dict(row),contributions=contributions,selected=[dict(r) for r in cur.fetchall()],
                    config=config,limitations=LIMITATIONS)
