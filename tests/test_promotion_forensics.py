from purchase.services.promotion_forensics import PromotionForensicsRecorder


class FakeEngine:
    def __init__(self):
        self.calls = []

    def register_response_callback(self, owner, callback, session=None):
        self.calls.append((owner, callback, session))

    def unregister_response_callback(self, owner, session=None):
        self.calls.append(("unregister", owner, session))


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


def test_forensics_can_bind_existing_browser_session():
    recorder = _bare_recorder()
    engine = FakeEngine()
    browser_session = object()

    recorder.attach_engine(engine, browser_session)

    assert recorder._callback_registered is True
    assert recorder.browser_session is browser_session
    assert engine.calls[0][2] is browser_session


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
