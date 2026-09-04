"""Proves the full write path: wrap() -> background writer -> store -> Parquet+SQLite on disk."""

import pandas as pd
import pytest

import driftwatch as dw


@pytest.fixture(autouse=True)
def _isolated_tracking_uri(tmp_path, monkeypatch):
    # Each test gets its own runs/ dir and a fresh store cache entry.
    uri = f"file:{tmp_path / 'runs'}"
    dw.set_tracking_uri(uri)
    yield uri


def fake_model(X: pd.DataFrame) -> list[int]:
    return [1 if row.income > 60000 else 0 for row in X.itertuples()]


def test_wrap_logs_events_end_to_end(tmp_path):
    session = dw.init(model_name="fraud-detector", modality="tabular")
    reference = pd.DataFrame(
        {"age": [30, 40, 50, 60], "income": [40000, 55000, 65000, 80000]}
    )
    session.log_baseline(reference)

    monitored = session.wrap(fake_model)

    n_calls = 12
    for i in range(n_calls):
        row = pd.DataFrame({"age": [30 + i], "income": [50000 + i * 1000]})
        result = monitored(row)
        assert result in ([0], [1])

    session.flush()

    events = session.store.query_events(session.session_id, limit=100)
    assert len(events) == n_calls
    assert all(e.status == "ok" for e in events)
    assert all(e.latency_ms is not None and e.latency_ms >= 0 for e in events)

    baseline = session.store.get_baseline(session.session_id)
    assert baseline is not None
    assert baseline.row_count == 4
    assert baseline.schema["age"] == "int64"

    # Parquet payload files actually landed on disk.
    payload_dir = session.store.root / "payloads" / session.session_id / "events"
    parquet_files = list(payload_dir.rglob("*.parquet"))
    assert len(parquet_files) >= 1

    db_path = session.store.root / "driftwatch.db"
    assert db_path.exists()


def test_wrap_logs_errors_without_swallowing_exception(tmp_path):
    session = dw.init(model_name="flaky-model", modality="tabular")
    session.log_baseline(pd.DataFrame({"x": [1, 2, 3]}))

    def boom(X):
        raise ValueError("model blew up")

    monitored = session.wrap(boom)

    with pytest.raises(ValueError, match="model blew up"):
        monitored(pd.DataFrame({"x": [1]}))

    session.flush()
    events = session.store.query_events(session.session_id)
    assert len(events) == 1
    assert events[0].status == "error"
    assert events[0].output is None


def test_auto_modality_resolved_from_baseline():
    session = dw.init(model_name="sentiment", modality="auto")
    with pytest.raises(RuntimeError, match="modality is still 'auto'"):
        session.wrap(lambda x: x)

    session.log_baseline(["great product", "terrible experience", "it was fine"])
    assert session.modality == "text"

    monitored = session.wrap(lambda texts: ["positive" for _ in texts])
    result = monitored(["good"])
    assert result == ["positive"]
