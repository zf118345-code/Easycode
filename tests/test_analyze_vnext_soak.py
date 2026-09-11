from __future__ import annotations

from scripts.analyze_vnext_soak import evaluate


def _report(*, status: str = "completed", elapsed: float = 3600.0) -> dict:
    samples = [
        {
            "elapsed_seconds": index * 60.0,
            "rss_bytes": 100 * 1024 * 1024 + index * 1024,
            "handle_count": 400,
            "process_count": 1,
            "data_root_bytes": 1024 * 1024 + index * 1024,
        }
        for index in range(61)
    ]
    return {
        "status": status,
        "requested_hours": 1.0,
        "sample_seconds": 60.0,
        "exercise_seconds": 300.0,
        "samples": samples,
        "exercises": [{"status": "completed"}] * 12,
        "failures": [],
        "summary": {"elapsed_seconds": elapsed},
    }


def test_soak_evaluator_accepts_complete_stable_report() -> None:
    result = evaluate(_report())

    assert result["status"] == "passed"
    assert all(check["passed"] for check in result["checks"])


def test_soak_evaluator_never_promotes_partial_report() -> None:
    result = evaluate(_report(status="running", elapsed=1800.0))

    assert result["status"] == "incomplete"
    assert next(check for check in result["checks"] if check["id"] == "duration")["passed"] is False


def test_soak_evaluator_detects_monotonic_handle_leak() -> None:
    payload = _report()
    for index, sample in enumerate(payload["samples"]):
        sample["handle_count"] = 400 + index

    result = evaluate(payload)

    assert result["status"] == "failed"
    assert next(check for check in result["checks"] if check["id"] == "handle_trend")["passed"] is False


def test_soak_evaluator_requires_disk_samples_and_bounds_growth() -> None:
    payload = _report()
    for sample in payload["samples"]:
        sample.pop("data_root_bytes")

    result = evaluate(payload)

    assert result["status"] == "failed"
    disk = next(check for check in result["checks"] if check["id"] == "data_root_growth")
    assert disk["passed"] is False
    assert disk["actual"] is None
