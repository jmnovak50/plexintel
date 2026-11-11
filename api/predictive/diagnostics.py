"""Saved-list comparisons on a common eligible population; never new inference."""
from collections import Counter
import numpy as np
from .contracts import fingerprint


def ranking_comparison(conn):
    rows=[]
    with conn.cursor() as cur:
        cur.execute('SELECT DISTINCT username FROM prepared_recommendations ORDER BY username')
        owners=[r[0] for r in cur.fetchall()]
        for user_index,owner in enumerate(owners,1):
            cur.execute('''SELECT n.rating_key,n.predicted_probability,o.predicted_probability,l.media_type,
                    COALESCE(l.show_rating_key,l.rating_key),
                    ARRAY(SELECT g.name FROM public.media_genres mg JOIN public.genres g ON g.id=mg.genre_id WHERE mg.media_id=n.rating_key)
                FROM prepared_recommendations n JOIN public.library l USING(rating_key)
                LEFT JOIN public.recommendations o ON o.username=n.username AND o.rating_key=n.rating_key
                WHERE n.username=%s''',(owner,))
            saved=cur.fetchall();common=[r for r in saved if r[2] is not None]
            if not common:continue
            old=sorted(common,key=lambda r:(-r[2],r[0]));new=sorted(common,key=lambda r:(-r[1],r[0]))
            old_rank={r[0]:i+1 for i,r in enumerate(old)}
            def describe(population,index):
                top=population[:20];shows=Counter(r[4] for r in top if r[3]=='episode');genres=Counter(g for r in top for g in r[5])
                return dict(top_rows=len(top),movies=sum(r[3]=='movie' for r in top),episodes=sum(r[3]=='episode' for r in top),
                    distinct_series=len(shows),largest_series_fraction=max(shows.values(),default=0)/len(top),
                    largest_genre_fraction=max(genres.values(),default=0)/len(top),
                    score_quantiles=[float(x) for x in np.quantile([r[index] for r in population],[0,.1,.5,.9,1])])
            rows.append(dict(user='viewer_'+str(user_index),current_candidates=len(saved),common_candidates=len(common),
                new_only_candidates=len(saved)-len(common),top20_overlap=len({r[0] for r in old[:20]}&{r[0] for r in new[:20]}),
                mean_absolute_rank_displacement=float(np.mean([abs(i+1-old_rank[r[0]]) for i,r in enumerate(new)])),
                incumbent=describe(old,2),rebuilt=describe(new,1)))
    return dict(users=rows,limitation='Both lists reranked only within shared saved keys already passing the rebuilt eligibility policy. Current library genre/show metadata is used for both. This is ranking sensitivity, not engagement accuracy; no inference on the old classifier.')
