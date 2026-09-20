import json
import threading
from types import SimpleNamespace

import pytest

from purchase.services.promotion_event_observer import PromotionEventObserver


def make_observer(tmp_path):
    recorder = SimpleNamespace(
        events=[],
        record_event=lambda event, phase, details=None: recorder.events.append(
            (event, phase, details)
        ),
        write_observation_summary=lambda summary: (
            tmp_path.joinpath("observation_summary.json").write_text(
                json.dumps(summary),
                encoding="utf-8",
            )
        ),
    )

    session = SimpleNamespace(
        product=SimpleNamespace(item_id=123, product_url="https://shopee.ph/"),
        variation=SimpleNamespace(model_id=456),
        request=SimpleNamespace(
            reference=SimpleNamespace(url="https://shopee.ph/"),
        ),
    )

    observer = PromotionEventObserver(session, recorder)
    observer.recorder = recorder
    return observer, recorder


def test_observer_records_matching_sku_state(tmp_path):
    observer, recorder = make_observer(tmp_path)

    payload = {
        "data": {
            "item": {
                "models": [
                    {
                        "item_id": 123,
                        "model_id": 456,
                        "name": "Test SKU",
                        "price": 990000000,
                        "price_before_discount": 7549000000,
                        "price_stocks": [],
                    }
                ]
            },
            "bottom_banner": {
                "deep_discount": {
                    "promotion_id": 999,
                    "promotion_price": {"single_value": 990000000},
                    "reminder_event": {
                        "item_id": 123,
                        "shop_id": 1,
                        "start_time": 1,
                        "end_time": 4102444800,
                    },
                }
            },
        }
    }

    response = SimpleNamespace(
        url="https://shopee.ph/api/v4/pdp/get_pc",
    )

    import asyncio

    asyncio.run(
        observer.on_browser_response(
            response,
            json.dumps(payload).encode("utf-8"),
        )
    )

    assert observer.last_state["model_id"] == 456
    assert observer.last_state["price"] == 990000000
    assert observer.last_state["promotion_price"] == 990000000
    assert observer.last_state["promotion_event_status"] == "LIVE"
    assert recorder.events[-1][0] == "promotion_observer_state"
