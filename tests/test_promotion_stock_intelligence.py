from purchase.services.promotion_stock_intelligence import (
    ENDED,
    LIVE,
    LIVE_NO_RESERVE,
    LIVE_RESERVE_AVAILABLE,
    NO_PROMOTION,
    UPCOMING,
    UNKNOWN,
    PromotionStockIntelligence,
)


def _model(**overrides):
    model = {
        "item_id": 26342037051,
        "model_id": 139454633406,
        "promotion_id": 487782888128821,
        "price_stocks": [
            {
                "promotion_type": 301,
                "allocated_stock": None,
            },
            {
                "promotion_type": 0,
                "allocated_stock": None,
            },
        ],
        "has_stock": True,
        "current_promotion_reserved_stock": None,
        "current_promotion_has_reserve_stock": False,
    }
    model.update(overrides)
    return model


def test_upcoming_promotion_is_not_classified_as_live_stock():
    result = PromotionStockIntelligence.analyze(
        _model(),
        promotion_detected=True,
        event_status="UPCOMING",
    )

    assert result.state == UPCOMING
    assert result.current_promotion_has_reserve_stock is False
    assert "model_promotion_id" in result.evidence


def test_live_reserve_signal_is_classified_as_available():
    result = PromotionStockIntelligence.analyze(
        _model(
            current_promotion_has_reserve_stock=True,
            current_promotion_reserved_stock=3,
        ),
        promotion_detected=True,
        event_status="LIVE",
    )

    assert result.state == LIVE_RESERVE_AVAILABLE
    assert result.current_promotion_reserved_stock == 3


def test_live_without_reserve_signal_remains_live_not_unknown():
    result = PromotionStockIntelligence.analyze(
        _model(
            current_promotion_has_reserve_stock=None,
            current_promotion_reserved_stock=None,
        ),
        promotion_detected=True,
        event_status="LIVE",
    )

    assert result.state == LIVE


def test_live_false_reserve_signal_is_not_inferred_as_reserve_available():
    result = PromotionStockIntelligence.analyze(
        _model(
            current_promotion_has_reserve_stock=False,
            current_promotion_reserved_stock=None,
        ),
        promotion_detected=True,
        event_status="LIVE",
    )

    assert result.state == LIVE_NO_RESERVE
    assert result.has_stock is True


def test_positive_allocated_stock_is_preserved_as_evidence():
    result = PromotionStockIntelligence.analyze(
        _model(
            current_promotion_has_reserve_stock=None,
            price_stocks=[
                {"promotion_type": 301, "allocated_stock": 7},
                {"promotion_type": 0, "allocated_stock": 12},
            ],
        ),
        promotion_detected=True,
        event_status="LIVE",
    )

    assert result.state == LIVE
    assert result.allocated_stock == 7
    assert "promotion_allocated_stock" in result.evidence


def test_missing_event_does_not_become_live():
    result = PromotionStockIntelligence.analyze(
        _model(),
        promotion_detected=True,
        event_status="NO_EVENT",
    )

    assert result.state == UNKNOWN


def test_no_exact_sku_promotion_is_no_promotion():
    result = PromotionStockIntelligence.analyze(
        _model(promotion_id=None, price_stocks=[]),
        promotion_detected=False,
        event_status="LIVE",
    )

    assert result.state == NO_PROMOTION


def test_ended_promotion_is_classified_explicitly():
    result = PromotionStockIntelligence.analyze(
        _model(),
        promotion_detected=True,
        event_status="ENDED",
    )

    assert result.state == ENDED
