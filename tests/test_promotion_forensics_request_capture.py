import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

from purchase.services.promotion_forensics import PromotionForensicsRecorder


def make_recorder(tmp_path):
    recorder = PromotionForensicsRecorder.__new__(PromotionForensicsRecorder)
    recorder.session = SimpleNamespace(
        product=SimpleNamespace(item_id=123),
        variation=SimpleNamespace(model_id=456),
    )
    recorder.run_dir = tmp_path
    recorder.api_dir = tmp_path / "api"
    recorder.page_dir = tmp_path / "pages"
    recorder.api_dir.mkdir()
    recorder.page_dir.mkdir()
    recorder._sequence = 0
    recorder._sequence_lock = threading.Lock()
    recorder._file_lock = threading.Lock()
    return recorder


class FakeRequest:
    method = "POST"
    resource_type = "xhr"
    post_data = json.dumps(
        {
            "item_id": 123,
            "model_id": 456,
            "promotion_id": 789,
            "checkout_id": "checkout-1",
            "card_number": "4111111111111111",
            "password": "secret",
        }
    )


class FakeResponse:
    url = "https://shopee.ph/api/v4/checkout"
    status = 200
    request = FakeRequest()

    @property
    def headers(self):
        return {"content-type": "application/json"}

    async def body(self):
        return json.dumps(
            {
                "item_id": 123,
                "model_id": 456,
                "promotion_id": 789,
                "price": 990000000,
            }
        ).encode()


def test_request_body_is_captured_and_target_observations_are_recorded(tmp_path):
    recorder = make_recorder(tmp_path)

    asyncio.run(recorder.on_browser_response(FakeResponse()))

    events = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    event = json.loads(events[-1])

    assert event["method"] == "POST"
    assert event["request_body_format"] == "json"
    assert "request_body_file" in event
    assert event["target_request_observations"][0]["promotion_id"] == 789

    request_path = tmp_path / event["request_body_file"]
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert payload["item_id"] == 123
    assert payload["model_id"] == 456
    assert payload["promotion_id"] == 789
    assert payload["card_number"] == "<redacted>"
    assert payload["password"] == "<redacted>"


def test_non_json_request_body_is_preserved_as_text(tmp_path):
    recorder = make_recorder(tmp_path)

    class TextRequest(FakeRequest):
        post_data = "item_id=123&model_id=456"

    class TextResponse(FakeResponse):
        request = TextRequest()

    asyncio.run(recorder.on_browser_response(TextResponse()))

    events = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    event = json.loads(events[-1])

    assert event["request_body_format"] == "text"
    assert event["request_body_bytes"] > 0
    request_path = tmp_path / event["request_body_file"]
    assert request_path.read_text(encoding="utf-8") == "item_id=123&model_id=456"
