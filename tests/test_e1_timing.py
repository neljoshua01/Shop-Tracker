import asyncio

from purchase.services.e1_timing import E1TimingRecorder


class FakeRequest:
    url = "https://shopee.ph/api/v4/pdp/get_pc"
    method = "GET"
    timing = {
        "startTime": 1_000.0,
        "responseStart": 1_012.0,
        "responseEnd": 1_025.0,
    }


class FakeResponse:
    request = FakeRequest()


def test_e1_recorder_tracks_all_execution_points():
    recorder = E1TimingRecorder()
    recorder.start()

    for point in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"):
        recorder.mark(point)

    metrics = recorder.metrics()

    assert all(recorder.points.get(point) is not None for point in recorder.POINTS)
    assert metrics["network_latency_ms"] is not None
    assert metrics["parsing_latency_ms"] is not None
    assert metrics["trigger_to_checkout_ms"] is not None


def test_e1_records_playwright_get_pc_network_timing():
    recorder = E1TimingRecorder()
    recorder.start()

    recorder.record_get_pc_network(
        FakeRequest(),
        callback_received_ns=1_026_000_000_000,
    )

    assert recorder.points["T1"] == 1_000_000_000
    assert recorder.points["T2"] == 1_025_000_000
    assert recorder.network["url"].endswith("/api/v4/pdp/get_pc")
    assert recorder.metrics()["network_latency_ms"] == 25.0
    assert recorder.metrics()["browser_observation_latency_ms"] == 1.0


def test_e1_network_timing_records_completed_request_timing():
    recorder = E1TimingRecorder()
    recorder.start()

    async def finish_response():
        response = FakeResponse()
        await asyncio.sleep(0)
        recorder.record_get_pc_network(
            response.request,
            callback_received_ns=1_026_000_000_000,
        )

    asyncio.run(finish_response())

    assert recorder.metrics()["network_latency_ms"] == 25.0
