"""Unchanged XGBoost fitting and fold-only feature vocabularies."""
import time
import numpy as np
from .contracts import ContractError,fingerprint
from .features import Vocabulary
from .evaluation import evaluate
def fit(rows, vocabulary, *, progress=lambda value: None):
    import xgboost as xgb
    y = np.array([r['label'] for r in rows], dtype=np.int32)
    if set(y) != {0, 1}:
        raise ContractError('Training requires both classes')
    weights = np.array([r['sample_weight'] for r in rows], dtype=np.float32) * np.where(y == 0, (y == 1).sum() / (y == 0).sum(), 1.0)

    class Observer(xgb.callback.TrainingCallback):

        def after_iteration(self, model, epoch, evals_log):
            if epoch % 10 == 0 or epoch == 99:
                progress(dict(phase=f'boosting round {epoch + 1}/100; examples={len(rows)}'))
            return False
    classifier = xgb.XGBClassifier(objective='binary:logistic', eval_metric='aucpr', n_estimators=100, max_depth=6, learning_rate=0.1, subsample=0.8, random_state=42, scale_pos_weight=1.0, n_jobs=2, callbacks=[Observer()])
    classifier.fit(vocabulary.transform(rows), y, sample_weight=weights)
    classifier.set_params(callbacks=None)
    classifier.get_booster().feature_names = vocabulary.names
    classifier._plexintel_training_keys = sorted({r['media_key'] for r in rows})
    return classifier

def metrics(classifier, vocabulary, rows):
    return evaluate(classifier, vocabulary, rows, training_keys=getattr(classifier, '_plexintel_training_keys', ()))

def fit_compare(train_rows, test_rows, *, include_poster, progress=lambda value: None):
    if not test_rows:
        raise ContractError('Evaluation cohort lacks heldout examples')
    vocabulary = Vocabulary.fit(train_rows, include_poster=include_poster)
    started = time.perf_counter()
    classifier = fit(train_rows, vocabulary, progress=progress)
    elapsed = time.perf_counter() - started
    result = evaluate(classifier, vocabulary, test_rows, training_keys={r['media_key'] for r in train_rows})
    result.update(training_seconds=elapsed, train_rows=len(train_rows), feature_count=len(vocabulary.names), cohort_hash=fingerprint([(r['owner'], r['media_key'], r['prediction_at'], r['label']) for r in test_rows]), train_only_vocabulary=vocabulary.specification())
    return result
