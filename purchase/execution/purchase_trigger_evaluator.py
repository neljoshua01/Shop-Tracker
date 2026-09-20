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

        # This experiment deliberately separates the advertised deep-discount
        # price from the selected SKU's transactional model price. The new
        # condition only triggers when Shopee's actual selected-model price
        # equals the advertised promotional price and that promotional price
        # is at or below the configured target.
        if trigger is TriggerCondition.PROMOTIONAL_PRICE_TARGET:
            if (
                not state.deep_discount
                or state.promotion_event_status != "LIVE"
                or state.promotion_price is None
                or state.promotion_price <= 0
            ):
                print(
                    "[PurchaseTriggerEvaluator] "
                    "Promotional price condition not ready: "
                    "promotion is not LIVE with a valid promotional price."
                )
                return False

            transactional_price_confirmed = (
                state.price == state.promotion_price
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
            print(
                "[PurchaseTriggerEvaluator] "
                "Transactional promotional price confirmed: "
                f"{transactional_price_confirmed}"
            )

            if not transactional_price_confirmed:
                print(
                    "[PurchaseTriggerEvaluator] "
                    "Waiting for the selected SKU's transactional price "
                    "to match the promotional price."
                )
                return False

            price_reached = state.price <= target_price

            if price_reached:
                print(
                    "[PurchaseTriggerEvaluator] "
                    "PROMOTIONAL TRANSACTIONAL PRICE TARGET REACHED."
                )
                return True

            print(
                "[PurchaseTriggerEvaluator] "
                "Transactional promotional price is above target."
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
