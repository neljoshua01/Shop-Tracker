from datetime import datetime, timezone

from purchase.services.promotion_forensics import PromotionForensicsRecorder


class FakeEngine:
    def __init__(self):
        self.calls = []

    def register_response_callback(self, owner, callback, session=None, all_sessions=False):
        self.calls.append((owner, callback, session, all_sessions))

    def unregister_response_callback(self, owner, session=None, all_sessions=False):
        self.calls.append(("unregister", owner, session, all_sessions))


def _bare_recorder():
    recorder = object.__new__(PromotionForensicsRecorder)
    recorder.session = None
    recorder.browser_session = None
    recorder._engine_ref = None
    recorder._callback_registered = False
    recorder._append_event = lambda event: None
    return recorder


def test_forensics_can_register_before_browser_session_exists():
    recorder = _bare_recorder()
    engine = FakeEngine()

    recorder.attach_engine(engine)

    assert recorder._callback_registered is True
    assert recorder.browser_session is None
    assert len(engine.calls) == 1
    owner, callback, session = engine.calls[0]
    assert owner is recorder
    assert callback == recorder.on_browser_response
    assert session is None
    assert engine.calls[0][3] is True


def test_forensics_can_bind_existing_browser_session():
    recorder = _bare_recorder()
    engine = FakeEngine()
    browser_session = object()

    recorder.attach_engine(engine, browser_session)

    assert recorder._callback_registered is True
    assert recorder.browser_session is browser_session
    assert engine.calls[0][2] is browser_session
    assert engine.calls[0][3] is True


def test_relevant_endpoint_phases_distinguish_pdp_cart_and_checkout():
    assert PromotionForensicsRecorder._phase_for_endpoint(
        "api_v4_pdp_get_pc"
    ) == "pdp_get_pc"
    assert PromotionForensicsRecorder._phase_for_endpoint(
        "api_v4_cart_add_item"
    ) == "cart"
    assert PromotionForensicsRecorder._phase_for_endpoint(
        "api_v4_checkout"
    ) == "checkout"


def test_stop_writes_final_summary_for_normal_pipeline_exit(tmp_path):
    recorder = _bare_recorder()
    recorder.started_at = datetime.now(timezone.utc)
    recorder.run_dir = tmp_path / "run"
    recorder.api_dir = recorder.run_dir / "api"
    recorder.page_dir = recorder.run_dir / "pages"
    recorder.api_dir.mkdir(parents=True)
    recorder.page_dir.mkdir(parents=True)
    recorder._file_lock = __import__("threading").Lock()

    recorder.stop()

    summary_path = recorder.run_dir / "final_summary.json"
    assert summary_path.exists()

    summary = __import__("json").loads(summary_path.read_text(encoding="utf-8"))
    assert summary["schema_version"] == 1
    assert summary["finalization_status"] == "completed"
    assert summary["event_log"] == "events.jsonl"
    assert "forensics_stopped" in recorder.run_dir.joinpath("events.jsonl").read_text(encoding="utf-8")


def test_stop_still_writes_summary_when_cleanup_step_warns(tmp_path):
    recorder = _bare_recorder()
    recorder.started_at = datetime.now(timezone.utc)
    recorder.run_dir = tmp_path / "run"
    recorder.api_dir = recorder.run_dir / "api"
    recorder.page_dir = recorder.run_dir / "pages"
    recorder.api_dir.mkdir(parents=True)
    recorder.page_dir.mkdir(parents=True)
    recorder._file_lock = __import__("threading").Lock()
    recorder._callback_registered = True
    recorder._engine_ref = FakeEngine()
    recorder._engine_ref.unregister_response_callback = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("test cleanup warning"))

    recorder.stop()

    summary_path = recorder.run_dir / "final_summary.json"
    assert summary_path.exists()
    summary = __import__("json").loads(summary_path.read_text(encoding="utf-8"))
    assert summary["finalization_status"] == "completed_with_warnings"
    assert summary["finalization_warnings"][0]["step"] == "unregister_response_callback"
