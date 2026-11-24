import inspect
import numpy as np
from research.title_traits.selector import DistributionTraits


def fixture():
    ids=list(range(100));values=np.arange(100,dtype='f4').reshape(-1,1)
    labels=[dict(dimension=0,display_label='fictional trait',explainable=True)]
    evidence={0:dict(verified_lineage=True,high_values=[97,98,99],low_values=[0,1,2],independent_high=3)}
    canonical={k:str(k) for k in ids};canonical[98]='99'
    return DistributionTraits(ids,values,labels,evidence,canonical)


def test_midrank_high_polarity_evidence_abstention_and_canonical_invariance():
    s=fixture()
    assert s.percentile(0,99)==99.5
    assert s.compare(99)['proposed']
    assert s.compare(98)==s.compare(99)
    assert not s.compare(0)['proposed']
    assert not s.compare(96)['proposed']  # High percentile alone is insufficient.
    s.evidence[0]['independent_high']=2
    assert not s.compare(99)['proposed']
    assert 'viewer' not in inspect.signature(DistributionTraits.compare).parameters
    assert 'shap' not in inspect.signature(DistributionTraits.__init__).parameters


def test_governance_exclusion_and_no_forced_traits():
    s=fixture();s.labels=[]
    assert s.compare(99)['proposed']==[]
    assert s.compare(99)['abstention']
