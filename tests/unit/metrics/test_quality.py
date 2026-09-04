from driftwatch.metrics.quality import compute_tabular_quality, compute_text_quality


def test_tabular_duplicate_rate():
    window_features = [{"x": [1.0]} for _ in range(10)]  # 10 identical single-row events
    results = compute_tabular_quality({"columns": {}}, window_features)
    dup = next(r for r in results if r.metric_name == "duplicate_rate")
    assert dup.value == 0.9  # 1 unique / 10


def test_tabular_no_duplicates():
    window_features = [{"x": [float(i)]} for i in range(10)]
    results = compute_tabular_quality({"columns": {}}, window_features)
    dup = next(r for r in results if r.metric_name == "duplicate_rate")
    assert dup.value == 0.0


def test_tabular_out_of_range_rate():
    baseline_stats = {"columns": {"x": {"kind": "numeric", "min": 0.0, "max": 10.0}}}
    window_features = [{"x": [v]} for v in [5.0, 15.0, -5.0, 3.0]]
    results = compute_tabular_quality(baseline_stats, window_features)
    oor = next(r for r in results if r.metric_name == "out_of_range_rate")
    assert oor.value == 0.5  # 2 of 4 values fall outside [0, 10]


def test_tabular_quality_empty_window():
    assert compute_tabular_quality({"columns": {}}, []) == []


def test_text_empty_and_duplicate_rate():
    window_features = [
        {"text": ["hello"]},
        {"text": ["hello"]},
        {"text": [""]},
        {"text": ["world"]},
    ]
    results = compute_text_quality(window_features)
    empty = next(r for r in results if r.metric_name == "empty_rate")
    dup = next(r for r in results if r.metric_name == "duplicate_rate")
    assert empty.value == 0.25
    assert dup.value == 0.25  # 3 unique / 4


def test_text_quality_empty_window():
    assert compute_text_quality([]) == []
