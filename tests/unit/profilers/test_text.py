import pytest

from driftwatch.profilers.text import TextProfiler
from tests._fakes import FakeEmbedder

REFERENCE_TEXTS = [
    "the coffee machine broke again this morning",
    "great espresso and friendly staff at the cafe",
    "my order of a latte was delayed by ten minutes",
    "the barista made a wonderful cappuccino today",
    "coffee shop was out of oat milk for my order",
] * 10  # 50 short, topically-coherent "coffee shop reviews"

DRIFTED_TEXTS = [
    "quarterly earnings report shows strong revenue growth",
    "the merger between the two banks was finalized today",
    "stock prices fell sharply after the interest rate hike",
    "the central bank announced new monetary policy measures",
    "investors reacted positively to the earnings call",
] * 10  # topically unrelated "financial news" — should read as drifted

_CENTROID_THRESHOLD = 0.1


@pytest.fixture
def profiler():
    return TextProfiler(embedder=FakeEmbedder())


def test_no_drift_when_window_matches_baseline_topic(profiler):
    baseline = profiler.compute_baseline_stats(REFERENCE_TEXTS)
    window_features = [profiler.extract_features(t) for t in REFERENCE_TEXTS]
    results = profiler.compute_drift(baseline, window_features)

    centroid = next(r for r in results if r.metric_name == "embedding_centroid_distance")
    assert centroid.value < 0.05
    assert not centroid.is_drifted


def test_detects_topic_drift_via_embedding_centroid(profiler):
    baseline = profiler.compute_baseline_stats(REFERENCE_TEXTS)
    window_features = [profiler.extract_features(t) for t in DRIFTED_TEXTS]
    results = profiler.compute_drift(baseline, window_features)

    centroid = next(r for r in results if r.metric_name == "embedding_centroid_distance")
    assert centroid.value > _CENTROID_THRESHOLD
    assert centroid.is_drifted

    mmd = next(r for r in results if r.metric_name == "mmd")
    assert mmd.value > 0


def test_detects_vocab_drift(profiler):
    baseline = profiler.compute_baseline_stats(REFERENCE_TEXTS)
    window_features = [profiler.extract_features(t) for t in DRIFTED_TEXTS]
    results = profiler.compute_drift(baseline, window_features)

    vocab = next(r for r in results if r.metric_name == "vocab_js_divergence")
    assert vocab.value > 0.3
    assert vocab.is_drifted

    oov = next(r for r in results if r.metric_name == "oov_rate")
    assert oov.value > 0.5  # financial vocabulary barely overlaps with coffee-shop vocabulary


def test_detects_length_shift(profiler):
    baseline = profiler.compute_baseline_stats(REFERENCE_TEXTS)
    long_texts = [t + " " + t + " " + t for t in REFERENCE_TEXTS]  # ~3x longer, same topic
    window_features = [profiler.extract_features(t) for t in long_texts]
    results = profiler.compute_drift(baseline, window_features)

    length_ks = next(r for r in results if r.metric_name == "length_ks_statistic")
    assert length_ks.value > 0.5
    assert length_ks.is_drifted


def test_extract_features_accepts_str_and_list():
    profiler = TextProfiler(embedder=FakeEmbedder())
    assert profiler.extract_features("hello world") == {"text": ["hello world"]}
    assert profiler.extract_features(["a", "b"]) == {"text": ["a", "b"]}
    with pytest.raises(TypeError):
        profiler.extract_features(123)


def test_compute_drift_empty_window_returns_no_results(profiler):
    baseline = profiler.compute_baseline_stats(REFERENCE_TEXTS)
    assert profiler.compute_drift(baseline, []) == []
