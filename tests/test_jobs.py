from pathlib import Path

from r2s.jobs import JobStore


def test_cancel_and_resume_preserve_attempt_history(tmp_path):
    store = JobStore(tmp_path / "runs")
    identifier = store.submit({"action": "inspect", "source": str(Path(__file__).parent / "fixtures/python_cli")})
    store.cancel(identifier)
    store.run(identifier)
    assert store.get(identifier)["status"] == "CANCELLED"
    store.resume(identifier)
    store.run(identifier)
    result = store.get(identifier)
    assert result["status"] == "SUCCEEDED" and result["attempt"] == 1
    assert result["result"]["run_id"].startswith("run_")
    assert any(event["stage"] == "CANCEL_REQUESTED" for event in result["events"])
    assert JobStore(store.output).get(identifier) == result


def test_job_failures_remain_inspectable(tmp_path):
    store = JobStore(tmp_path)
    identifier = store.submit({"action": "inspect", "source": str(tmp_path / "missing")})
    store.run(identifier)
    result = store.get(identifier)
    assert result["status"] == "FAILED"
    assert result["result"]["failure_class"]


def test_expired_worker_can_resume_without_losing_prior_events(tmp_path):
    store = JobStore(tmp_path)
    identifier = store.submit({"action": "inspect", "source": str(tmp_path / "missing")})
    with store.connect() as connection:
        connection.execute("UPDATE jobs SET status='RUNNING',lease=1 WHERE id=?", (identifier,))
    assert store.get(identifier)["status"] == "INTERRUPTED"
    store.resume(identifier)
    assert store.get(identifier)["attempt"] == 1
    assert any(event["stage"] == "INTERRUPTED" for event in store.get(identifier)["events"])
