from purchase.parser.sku_price_parser import SkuPriceParser
from purchase.services.promotion_stock_intelligence import (
    LIVE_NO_RESERVE,
    LIVE_RESERVE_AVAILABLE,
    UNKNOWN,
)


def _payload(**model_overrides):
    model = {
        "item_id": 26342037051,
        "model_id": 139454633406,
        "name": "Cosmic Orange,256GB",
        "price": 8349000000,
        "price_before_discount": 8699000000,
        "promotion_id": 487782888128821,
        "price_stocks": [
            {"promotion_type": 301, "allocated_stock": None},
            {"promotion_type": 0, "allocated_stock": None},
        ],
        "has_stock": True,
        "current_promotion_reserved_stock": None,
        "current_promotion_has_reserve_stock": False,
    }
    model.update(model_overrides)
    return {
        "data": {
            "item": {
                "models": [model],
            },
            "bottom_banner": {
                "deep_discount": {
                    "promotion_id": 487782888128821,
                    "is_lpp": False,
                    "promotion_price": {"single_value": 990000000},
                    "skin": {},
                    "reminder_event": {
                        "start_time": 1,
                        "end_time": 4102444800,
                    },
                },
            },
        }
    }


def test_parser_exposes_live_no_reserve_state():
    state = SkuPriceParser().parse(
        _payload(),
        model_id=26342037051 if False else 139454633406,
    )

    assert state is not None
    assert state.promotion_inventory_state == LIVE_NO_RESERVE
    assert state.current_promotion_has_reserve_stock is False
    assert state.promotion_allocated_stock is None


def test_parser_exposes_reserve_available_state():
    state = SkuPriceParser().parse(
        _payload(
            current_promotion_reserved_stock=2,
            current_promotion_has_reserve_stock=True,
        ),
        model_id=139454633406,
    )

    assert state is not None
    assert state.promotion_inventory_state == LIVE_RESERVE_AVAILABLE
    assert state.current_promotion_reserved_stock == 2


def test_parser_does_not_infer_live_without_event():
    payload = _payload()
    payload["data"]["item"]["models"][0]["promotion_id"] = 487782888128821
    payload["data"]["bottom_banner"] = None

    state = SkuPriceParser().parse(
        payload,
        model_id=139454633406,
    )

    assert state is not None
    assert state.promotion_event_status == "NO_EVENT"
    assert state.promotion_inventory_state == UNKNOWN
