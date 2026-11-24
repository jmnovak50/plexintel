"""Read-only percentile experiment, not a production recommendation selector.

Inputs contain media vectors, governed labels and retained media evidence only.
There is deliberately no viewer, SHAP, score, model or recommendation argument.
A percentile measures rarity within a coordinate, never semantic truth.
"""
import numpy as np

PERCENTILE_FLOOR = 95.0


def eligible(label):
    return (label.get('explainable') is True and not label.get('needs_review')
            and not label.get('suppressed') and bool((label.get('display_label') or '').strip()))


class DistributionTraits:
    def __init__(self, ids, values, labels, evidence, canonical):
        self.ids = list(ids)
        self.values = np.asarray(values, dtype=np.float32)
        if self.values.ndim != 2 or not np.isfinite(self.values).all() or len(ids) != len(self.values):
            raise ValueError('Finite, aligned media population required')
        self.index = {key: i for i, key in enumerate(ids)}
        self.sorted = np.sort(self.values, axis=0)
        self.labels = [r for r in labels if eligible(r)]
        self.evidence = evidence
        # Exact typed canonical aliases use one stable existing representative.
        self.representatives = {}
        for key in sorted(ids):
            if canonical.get(key): self.representatives.setdefault(canonical[key], key)
        self.canonical = canonical

    def percentile(self, dimension, value):
        column = self.sorted[:, dimension]
        return float(100*(np.searchsorted(column, value, side='left')+
                          np.searchsorted(column, value, side='right'))/(2*len(column)))

    def describe(self, key, label):
        dimension = label['dimension']
        value = float(self.values[self.index[key], dimension])
        retained = self.evidence.get(dimension, {})
        reasons = []
        if not retained.get('verified_lineage'): reasons.append('Retained evidence lineage unavailable')
        high, low = retained.get('high_values', []), retained.get('low_values', [])
        if not high or not low or retained.get('missing_keys'): reasons.append('Retained HIGH/LOW coordinates incomplete')
        if retained.get('independent_high', 0) < 3: reasons.append('Fewer than three independent HIGH titles/series')
        if high and low and min(high) <= max(low): reasons.append('Retained HIGH and LOW regions overlap')
        percentile = self.percentile(dimension, value)
        if percentile < PERCENTILE_FLOOR: reasons.append('Below frozen 95th-percentile floor')
        if high and value < min(high): reasons.append('Below the retained HIGH evidence region')
        return dict(dimension=dimension,label=label['display_label'],coordinate=value,percentile=percentile,
                    high_range=[min(high),max(high)] if high else None,
                    low_range=[min(low),max(low)] if low else None,
                    independent_high=retained.get('independent_high'),
                    evidence_id=retained.get('assessment_id'),abstention_reasons=reasons)

    def compare(self, key, limit=3):
        canonical = self.canonical.get(key)
        if not canonical or canonical not in self.representatives:
            return dict(canonical=None,representative_key=None,raw=[],proposed=[],candidates=[],
                        abstention='No verified canonical media identity')
        representative = self.representatives[canonical]
        candidates = [self.describe(representative,label) for label in self.labels]
        def unique(rows):
            result=[];seen=set()
            for row in rows:
                if row['label'] in seen: continue
                result.append(row);seen.add(row['label'])
                if len(result)>=limit:break
            return result
        raw=unique(sorted(candidates,key=lambda r:(-r['coordinate'],r['dimension'])))
        proposed=unique(sorted((r for r in candidates if not r['abstention_reasons']),
                               key=lambda r:(-r['percentile'],r['dimension'])))
        return dict(canonical=canonical,representative_key=representative,raw=raw,proposed=proposed,
                    candidates=sorted(candidates,key=lambda r:(-r['percentile'],r['dimension'])),
                    abstention=None if proposed else 'No eligible label meets retained-evidence and percentile requirements')
