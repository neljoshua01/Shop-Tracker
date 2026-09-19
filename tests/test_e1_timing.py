from purchase.services.e1_timing import E1TimingRecorder


def test_e1_timing_records_all_python_points_and_durations(tmp_path):
    recorder = E1TimingRecorder()

    values = iter(
        [
            1.0,  # T0
            1.1,  # T3
            1.2,  # T4
            1.3,  # T5
            1.4,  # T6
            1.5,  # T7
            1.7,  # T8
            1.9,  # T9
            2.1,  # T10
            2.3,  # T11
        ]
    )

    for name in ("T0", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"):
        recorder.record(name, monotonic=next(values))

    recorder.record_browser_timing(
        "T1",
        performance_time_origin_ms=1_000_000,
        performance_ms=100,
    )
    recorder.record_browser_timing(
        "T2",
        performance_time_origin_ms=1_000_000,
        performance_ms=125,
    )

    durations = recorder.durations()

    assert durations["network_latency_ms"] == 25.0
    assert durations["parse_to_state_ms"] == 100.0
    assert durations["trigger_evaluation_ms"] == 100.0
    assert durations["trigger_to_checkout_start_ms"] == 200.0
    assert durations["checkout_start_to_cart_resolved_ms"] == 200.0
    assert durations["cart_resolved_to_checkout_click_ms"] == 200.0
    assert durations["checkout_click_to_checkout_reached_ms"] == 200.0
    assert durations["trigger_to_checkout_reached_ms"] == 800.0


def test_e1_timing_persists_run_artifact(tmp_path):
    recorder = E1TimingRecorder()
    recorder.record("T0", monotonic=10.0)
    recorder.record("T7", monotonic=11.0)
    recorder.record("T11", monotonic=12.0)

    path = recorder.finalize(output_root=str(tmp_path))

    assert path.exists()
    payload = path.read_text(encoding="utf-8")

    assert recorder.run_id in payload
    assert "T0" in payload
    assert "T7" in payload
    assert "T11" in payload
