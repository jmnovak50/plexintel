"""Original eligibility/review behavior with synthetic evidence, no provider IO."""
from unittest.mock import MagicMock,Mock
from api.services import dimension_label_batch as batch


def test_candidates_include_negative_only_dimensions_and_preserve_review_cooldowns():
    conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
    # The SQL query, not a positive-SHAP filter, owns retained coordinate scope.
    cur.fetchall.side_effect=[[(12,2.0),(24,1.0),(36,.5),(48,.2)],[],[(12,True),(24,False),(36,False)],[]]
    evidence=Mock(context=dict(media_dimensions=768,user_dimensions=768,config_id='synthetic',model_sha256='model',feature_space_id='space'))
    evidence.prompt.return_value=dict(prompt_text='synthetic high/low',skipped_reason=None)
    rows,_=batch.candidates(conn,evidence)
    query=cur.execute.call_args_list[0].args[0]
    assert 'HAVING COUNT(*) FILTER(WHERE s.shap_value>0)' not in query
    assert 'context.model_version=%s' in query and 'r.scored_at=context.scored_at' in query
    assert 'next_review_at<=now()' in cur.execute.call_args_list[2].args[0]
    args=batch.parser().parse_args(['--selection-mode','eligible'])
    assert [r['dimension'] for r in batch.choose(rows,args)]==[48,12]
    args.selection_mode='importance'
    assert [r['dimension'] for r in batch.choose(rows,args)]==[48]


def test_same_prompt_abstentions_are_reused_until_an_explicit_review_is_due():
    args=batch.parser().parse_args(['--selection-mode','eligible'])
    rows=[dict(dimension=12,side='media',completed=False,abstained=True),
          dict(dimension=24,side='media',completed=True,review_due=False,abstained=True),
          dict(dimension=36,side='media',completed=True,review_due=True,abstained=True)]
    assert [r['dimension'] for r in batch.choose(rows,args)]==[36]
