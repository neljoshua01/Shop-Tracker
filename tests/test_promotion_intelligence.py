from purchase.parser.sku_price_parser import SkuPriceParser
from purchase.services.promotion_intelligence import PromotionIntelligence


def test_exact_model_promotion_is_detected():
    model = {
        "model_id": 139454633406,
        "promotion_id": 487782888128821,
        "price_stocks": [
            {"promotion_type": 301},
            {"promotion_type": 0},
        ],
    }

    result = PromotionIntelligence.analyze(model)

    assert result.detected is True
    assert result.promotion_id == 487782888128821
    assert result.promotion_types == (301,)
    assert result.evidence == (
        "model_promotion_id",
        "model_promotion_type",
    )


def test_unpromoted_model_is_not_marked_from_sibling_models():
    model = {
        "model_id": 139454633409,
        "promotion_id": 0,
        "price_stocks": [
            {"promotion_type": 0},
        ],
    }

    result = PromotionIntelligence.analyze(model)

    assert result.detected is False
    assert result.promotion_id is None
    assert result.promotion_types == ()
    assert result.evidence == ()


def test_product_level_promotion_is_not_used_as_exact_sku_proof():
    model = {
        "model_id": 139454633409,
        "promotion_id": 0,
        "price_stocks": [{"promotion_type": 0}],
    }

    result = PromotionIntelligence.analyze(
        model,
        event_status="LIVE",
    )

    assert result.detected is False
    assert result.event_status == "LIVE"


def test_parser_exposes_exact_sku_promotion_detection():
    data = {
        "data": {
            "item": {
                "models": [
                    {
                        "item_id": 26342037051,
                        "model_id": 139454633406,
                        "name": "Cosmic Orange,256GB",
                        "price": 8349000000,
                        "price_before_discount": 8699000000,
                        "promotion_id": 487782888128821,
                        "price_stocks": [
                            {"promotion_type": 301},
                            {"promotion_type": 0},
                        ],
                        "has_stock": True,
                    },
                    {
                        "item_id": 26342037051,
                        "model_id": 139454633409,
                        "name": "Cosmic Orange,2TB",
                        "price": 14699000000,
                        "price_before_discount": 0,
                        "promotion_id": 0,
                        "price_stocks": [
                            {"promotion_type": 0},
                        ],
                        "has_stock": False,
                    },
                ],
            }
        }
    }

    result = SkuPriceParser().parse(
        data,
        model_id=139454633406,
    )

    assert result is not None
    assert result.model_id == 139454633406
    assert result.promotion_detected is True
    assert result.promotion_id == 487782888128821
    assert result.promotion_types == (301, 0)
    assert result.promotion_evidence == (
        "model_promotion_id",
        "model_promotion_type",
    )
