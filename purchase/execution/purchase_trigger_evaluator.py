"""Evaluate whether the current monitored SKU state should trigger purchase."""

from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState
from purchase.models.trigger_condition import TriggerCondition


class PurchaseTriggerEvaluator:

    def evaluate(
        self,
        session: PurchaseSession,
        state: SkuPriceState,
    ) -> bool:

        trigger = session.request.trigger

        if trigger is TriggerCondition.TRACK_ONLY:
            return False

        if trigger is TriggerCondition.STOCK_AVAILABLE:
            return state.has_stock

        target_price = session.request.target_price

        if target_price is None:
            print(
                "[PurchaseTriggerEvaluator] "
                "No target price configured."
            )
            return False

        # Transactional promotional pricing is a model-scoped state, not a
        # banner/timer signal. Trigger only when the exact selected SKU is
        # LIVE, in stock, associated with a valid promotion, and its actual
        # transactional model price equals the advertised promotion price
        # and is within the configured target.
        if trigger is TriggerCondition.PROMOTIONAL_PRICE_TARGET:
            is_live = state.promotion_event_status == "LIVE"
            has_stock = state.has_stock
            has_valid_promotion = (
                state.promotion_id is not None
                and state.promotion_id > 0
            )
            has_valid_promotion_price = (
                state.promotion_price is not None
                and state.promotion_price > 0
            )
            transactional_price_confirmed = (
                has_valid_promotion_price
                and state.price == state.promotion_price
            )
            price_reached = (
                transactional_price_confirmed
                and state.price <= target_price
            )

            print(
                "[PurchaseTriggerEvaluator] "
                f"Promotional state: LIVE={is_live}, "
                f"stock={has_stock}, "
                f"promotion_id_valid={has_valid_promotion}, "
                f"transactional_price_match={transactional_price_confirmed}"
            )
            print(
                "[PurchaseTriggerEvaluator] "
                f"Transactional SKU price: {state.price}"
            )
            print(
                "[PurchaseTriggerEvaluator] "
                f"Promotional event price: {state.promotion_price}"
            )
            print(
                "[PurchaseTriggerEvaluator] "
                f"Target price: {target_price}"
            )

            if (
                is_live
                and has_stock
                and has_valid_promotion
                and has_valid_promotion_price
                and price_reached
            ):
                print(
                    "[PurchaseTriggerEvaluator] "
                    "PROMOTIONAL TRANSACTIONAL PRICE TARGET REACHED."
                )
                return True

            print(
                "[PurchaseTriggerEvaluator] "
                "Promotional transactional trigger not reached."
            )
            return False

        #
        # Preserve the existing price-target behavior. In particular, the
        # legacy deep-discount interpretation remains unchanged on the
        # last-known-good branch behavior; the experiment has its own trigger
        # condition so it can be evaluated independently.
        #
        current_price = state.price

        if (
            state.deep_discount
            and state.promotion_event_status == "LIVE"
            and state.promotion_price is not None
            and state.promotion_price > 0
        ):
            current_price = state.promotion_price

            print(
                "[PurchaseTriggerEvaluator] "
                "LIVE deep discount detected."
            )

        print(
            "[PurchaseTriggerEvaluator] "
            f"Current price: {current_price}"
        )
        print(
            "[PurchaseTriggerEvaluator] "
            f"Target price: {target_price}"
        )

        price_reached = current_price <= target_price

        if trigger is TriggerCondition.PRICE_AND_STOCK:
            return price_reached and state.has_stock

        if price_reached:
            print(
                "[PurchaseTriggerEvaluator] "
                "TARGET REACHED."
            )
            return True

        print(
            "[PurchaseTriggerEvaluator] "
            "Target not reached."
        )
        return False
