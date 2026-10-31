"""Deterministic instance policies. No network, model, acquisition or discovery writes."""
from collections import Counter
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENGINE_VERSION = 'eligibility-v1'
RULE_IDS = ('short_movie', 'recorded_sport', 'documentary', 'tv_movie',
            'foreign_language', 'standup', 'concert')


class ConfirmedTitle(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    media_type: Literal['movie', 'tv']
    tmdb_id: int = Field(gt=0)
    evidence: str = Field(min_length=5, max_length=500)

    @field_validator('evidence')
    @classmethod
    def meaningful_evidence(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('Supporting evidence is required')
        return value.strip()


class Rule(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled: bool = True
    action: Literal['exclude', 'retain'] = 'retain'
    confirmed_titles: list[ConfirmedTitle] = Field(default_factory=list, max_length=5000)

    @model_validator(mode='after')
    def unique(self):
        keys = [(t.media_type, t.tmdb_id) for t in self.confirmed_titles]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate confirmed identity')
        return self


class Policy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    rules: dict[str, Rule] = Field(default_factory=lambda: {
        key: Rule(action='exclude' if key in ('short_movie', 'recorded_sport') else 'retain')
        for key in RULE_IDS
    })
    minimum_movie_minutes: int = Field(default=60, ge=1, le=600)
    local_languages: list[str] = Field(default_factory=lambda: ['en'], min_length=1, max_length=100)

    @model_validator(mode='after')
    def valid_rules(self):
        if set(self.rules) != set(RULE_IDS):
            raise ValueError('Policy must contain exactly the supported rule identifiers')
        if len(set(self.local_languages)) != len(self.local_languages) or any(
            not (2 <= len(v) <= 3 and v.isascii() and v.isalpha() and v.islower())
            for v in self.local_languages
        ):
            raise ValueError('Use unique lowercase ISO language codes')
        if any(self.rules[k].confirmed_titles for k in ('short_movie', 'foreign_language')):
            raise ValueError('Runtime and language rules use canonical fields only')
        return self


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, default=str).encode()).hexdigest()


def confirmation_index(policy):
    return {key: {(t.media_type, t.tmdb_id): t for t in rule.confirmed_titles}
            for key, rule in policy.rules.items()}


def evaluate(title, policy: Policy, confirmations=None):
    """All exclusions OR together; retain never overrides another rule. Unknown retains."""
    media, ident = title['media_type'], title['tmdb_id']
    confirmations = confirmation_index(policy) if confirmations is None else confirmations
    runtime = title.get('runtime')
    language = title.get('original_language')
    genres = title.get('genres')
    genre_ids = {g.get('id') for g in genres or [] if isinstance(g, dict)}
    reasons, uncertainties, outcomes = [], [], []
    for key in RULE_IDS:
        rule = policy.rules[key]
        if not rule.enabled:
            outcomes.append(dict(rule_id=key, state='disabled'))
            continue
        evidence = None
        if key == 'short_movie':
            if media != 'movie':
                state = 'not_applicable'
            elif type(runtime) is not int or runtime <= 0:
                state = 'unknown'
            else:
                state = 'match' if runtime < policy.minimum_movie_minutes else 'no_match'
                evidence = dict(field='runtime', value=runtime, threshold=policy.minimum_movie_minutes)
        elif key == 'foreign_language':
            if (not isinstance(language, str) or not language.isascii() or
                    not language.isalpha() or not language.islower() or
                    not 2 <= len(language) <= 3 or language in ('und', 'xx', 'zxx')):
                state = 'unknown'
            else:
                state = 'match' if language not in policy.local_languages else 'no_match'
                evidence = dict(field='original_language', value=language)
        else:
            confirmed = confirmations[key].get((media, ident))
            genre_id = {'documentary': 99, 'tv_movie': 10770}.get(key)
            if key == 'tv_movie' and media != 'movie':
                state = 'not_applicable'
            elif confirmed:
                state = 'match'
                evidence = dict(source='policy_confirmation', note=confirmed.evidence)
            elif genre_id is not None and genre_id in genre_ids:
                state = 'match'
                evidence = dict(field='genres', tmdb_genre_id=genre_id)
            else:
                # An absent genre is not proof of category absence. Seerr has no
                # definitive sporting-event, stand-up or concert discriminator.
                state = 'unknown'
        outcome = dict(rule_id=key, state=state, action=rule.action, evidence=evidence)
        outcomes.append(outcome)
        if state == 'match' and rule.action == 'exclude':
            reasons.append(dict(rule_id=key, code=key + '_excluded', evidence=evidence))
        if state == 'unknown' and rule.action == 'exclude':
            uncertainties.append(dict(rule_id=key, code=key + '_evidence_unknown'))
    return dict(media_type=media, tmdb_id=ident, outcome='excluded' if reasons else 'retained',
                reasons=reasons, uncertainties=uncertainties, rule_outcomes=outcomes)


def evaluate_all(inventory, policy):
    confirmations = confirmation_index(policy)
    return [evaluate(t, policy, confirmations) for t in inventory]


def summarize(results):
    counts = dict(total=len(results), retained=0, excluded=0, incomplete=0, movies=0, tv=0)
    reasons, breakdown = Counter(), {}
    for row in results:
        counts[row['outcome']] += 1
        counts['incomplete'] += bool(row['uncertainties'])
        counts['movies' if row['media_type'] == 'movie' else 'tv'] += 1
        part = breakdown.setdefault(row['media_type'], dict(total=0, retained=0, excluded=0, incomplete=0))
        part['total'] += 1
        part[row['outcome']] += 1
        part['incomplete'] += bool(row['uncertainties'])
        reasons.update(r['code'] for r in row['reasons'])
    return dict(counts=counts, exclusion_reasons=dict(reasons), by_media=breakdown)
