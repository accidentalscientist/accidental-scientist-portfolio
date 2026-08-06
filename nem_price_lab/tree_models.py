"""Random Forest and Gradient Boosting forecasters.

These are the only parts of the lab that need scikit-learn, and it is
deliberately kept OUT of the production requirements. Training happens
offline; the page reads predictions from `ForecastPoint` rows, so the web
server never imports this module. Install with:

    pip install -r requirements-ml.txt

The import is therefore soft: if scikit-learn is absent the two tree models
are simply unavailable and the rest of the lab carries on unaffected.

A note on what these models can and cannot do. They see richer inputs than
the temperature model, but they see the same *kind* of information: price
history, calendar, forecast weather. None of that describes an outage, a
bidding change, or a network constraint, which is what actually produces
the extremes. Expect them to sharpen the ordinary intervals and to miss the
spikes exactly like everything else here.
"""

import math

from .features import (
    FEATURE_NAMES,
    build_prediction_set,
    build_training_set,
)
from .forecasting import MARKET_PRICE_FLOOR, clamp

RANDOM_FOREST = 'random_forest'
GRADIENT_BOOSTING = 'gradient_boosting'
NEURAL_NETWORK = 'neural_network'

# Fixed seed so a rerun of the same origin reproduces the same forecast.
# Without it the published archive would drift for no reason.
RANDOM_STATE = 20260806

# Deliberately modest. With ~17k training rows and one weekly refit, deeper
# forests buy very little and make the run slow enough to discourage the
# weekly cadence the whole product depends on.
FOREST_PARAMS = {
    'n_estimators': 300,
    'max_depth': 14,
    'min_samples_leaf': 8,
    'n_jobs': -1,
    'random_state': RANDOM_STATE,
}

BOOSTING_PARAMS = {
    'max_iter': 400,
    'max_depth': 6,
    'learning_rate': 0.06,
    'min_samples_leaf': 20,
    'l2_regularization': 1.0,
    'early_stopping': True,
    'validation_fraction': 0.15,
    'random_state': RANDOM_STATE,
}

# A genuinely different family from the two tree models. Trees partition the
# feature space into boxes and predict a constant inside each one, so they
# produce a step function and cannot extrapolate past the prices they were
# trained on. A network fits a smooth continuous surface instead, and CAN
# extrapolate, which is both its advantage and its main way of going wrong.
#
# Two hidden layers is the smallest architecture that can represent the
# interactions this problem obviously has (temperature matters differently
# depending on time of day). Anything deeper on 17k rows is asking to
# memorise the training set.
NETWORK_PARAMS = {
    'hidden_layer_sizes': (64, 32),
    'activation': 'relu',
    'solver': 'adam',
    'alpha': 0.001,
    'learning_rate_init': 0.003,
    'max_iter': 600,
    'early_stopping': True,
    'validation_fraction': 0.15,
    'n_iter_no_change': 20,
    'random_state': RANDOM_STATE,
}

MIN_TRAINING_ROWS = 500


class SklearnUnavailable(RuntimeError):
    """Raised when a tree model is requested without scikit-learn installed."""


def sklearn_available():
    try:
        import sklearn  # noqa: F401
    except ImportError:
        return False
    return True


def _estimator(model_key):
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
        from sklearn.neural_network import MLPRegressor
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise SklearnUnavailable(
            'scikit-learn is not installed; run `pip install -r requirements-ml.txt` '
            'to enable the learned models. The other models are unaffected.'
        ) from exc

    if model_key == RANDOM_FOREST:
        return RandomForestRegressor(**FOREST_PARAMS)
    if model_key == GRADIENT_BOOSTING:
        return HistGradientBoostingRegressor(**BOOSTING_PARAMS)
    if model_key == NEURAL_NETWORK:
        # Scaling is not optional here. Trees are indifferent to feature
        # magnitude, but a network is not: demand sits in the thousands while
        # the cyclic encodings sit in [-1, 1], so without standardisation the
        # demand feature would dominate every gradient and the rest would
        # barely train at all.
        return Pipeline([
            ('scale', StandardScaler()),
            ('mlp', MLPRegressor(**NETWORK_PARAMS)),
        ])
    raise ValueError(f'unknown learned model {model_key!r}')


def _asinh(value):
    """Negative-price-safe compression.

    NEM prices run from -$1,000 to five figures, so the target is violently
    right-skewed and a squared-error objective chases the spikes. A log is
    unusable because prices go negative; asinh behaves like a log for large
    values and like the identity near zero, so it handles both tails without
    special-casing the sign.
    """
    return math.asinh(value)


def _inverse_asinh(value):
    return math.sinh(value)


def fit_and_predict(model_key, prices, observed_temps, demands, targets, origin,
                    target_temps, training_weeks=52):
    """Train on history up to the origin, then predict the coming week.

    Returns (predictions, diagnostics). Predictions are empty when there is
    not enough history to train honestly, which is the correct answer rather
    than a model fitted on a handful of rows.
    """
    X_train, y_train, _ = build_training_set(
        prices, observed_temps, demands, origin, training_weeks
    )

    if len(X_train) < MIN_TRAINING_ROWS:
        return {}, {
            'trained': False,
            'training_rows': len(X_train),
            'reason': f'fewer than {MIN_TRAINING_ROWS} complete feature rows',
        }

    X_predict, index = build_prediction_set(
        targets, origin, prices, observed_temps, target_temps, demands
    )
    if not X_predict:
        return {}, {
            'trained': False,
            'training_rows': len(X_train),
            'reason': 'no complete feature rows for the forecast week',
        }

    transformed = [_asinh(v) for v in y_train]

    estimator = _estimator(model_key)
    estimator.fit(X_train, transformed)
    raw = estimator.predict(X_predict)

    # Bound predictions to the range of prices actually observed in training.
    #
    # This is not cosmetic. The target is compressed with asinh and inverted
    # with sinh, which grows exponentially: an overshoot of a few units in
    # transformed space becomes billions of dollars after inversion. The tree
    # models are immune because they average leaf values and so cannot leave
    # the training range, but a neural network fits a smooth surface and CAN,
    # and did: an unbounded run produced a Victorian forecast averaging
    # $3.8 billion per MWh.
    #
    # Clamping in transformed space first keeps sinh in a safe domain; the
    # second clamp states the honest modelling position, which is that a
    # seven-day forecast has no business predicting a price the market has
    # never printed.
    low_t, high_t = min(transformed), max(transformed)
    observed_high = max(y_train)

    predictions = {}
    for interval, value in zip(index, raw):
        bounded = min(max(float(value), low_t), high_t)
        predictions[interval] = min(clamp(_inverse_asinh(bounded)), observed_high)

    clipped = sum(
        1 for value in raw if not (low_t <= float(value) <= high_t)
    )

    diagnostics = {
        'trained': True,
        'training_rows': len(X_train),
        'predicted_intervals': len(predictions),
        'features': len(FEATURE_NAMES),
        'target_transform': 'asinh',
        'training_price_range': [round(min(y_train), 2), round(observed_high, 2)],
        'clipped_predictions': clipped,
        'params': {
            RANDOM_FOREST: FOREST_PARAMS,
            GRADIENT_BOOSTING: BOOSTING_PARAMS,
            NEURAL_NETWORK: NETWORK_PARAMS,
        }[model_key],
    }

    importances = _importances(estimator, X_train, y_train)
    if importances:
        diagnostics['top_features'] = importances

    return predictions, diagnostics


def _importances(estimator, X_train, y_train):
    """The ten features carrying the most weight, for publication.

    A model whose drivers are not inspectable does not belong on a page whose
    whole argument is transparency. Only the tree models expose importances;
    a network has no comparable single number per feature, and inventing one
    from its weights would be misleading, so it reports none.
    """
    values = getattr(estimator, 'feature_importances_', None)
    if values is None:
        return None
    ranked = sorted(zip(FEATURE_NAMES, values), key=lambda pair: pair[1], reverse=True)
    return [{'feature': name, 'importance': round(float(weight), 4)} for name, weight in ranked[:10]]


LEARNED_MODELS = (RANDOM_FOREST, GRADIENT_BOOSTING, NEURAL_NETWORK)

__all__ = [
    'RANDOM_FOREST', 'GRADIENT_BOOSTING', 'NEURAL_NETWORK', 'LEARNED_MODELS',
    'SklearnUnavailable', 'sklearn_available', 'fit_and_predict',
    'FOREST_PARAMS', 'BOOSTING_PARAMS', 'NETWORK_PARAMS', 'MIN_TRAINING_ROWS',
]
