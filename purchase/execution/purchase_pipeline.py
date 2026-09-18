"""
Coordinates the Intelligent Monitoring Engine purchase pipeline.

Phase 1 deliberately removes the cart as an execution dependency:

    Product Profile
        -> selected PDP variation/quantity
        -> SKU monitoring
        -> IME execution decision
        -> native PDP Buy Now DOM dispatch
        -> Checkout verification

Auto Checkout OFF stops at the trigger and leaves the browser session on the
selected product context. Auto Checkout ON continues into direct checkout,
but the final Place Order action remains separately safety-gated.
"""

import threading

from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_status import PurchaseStatus
from purchase.models.ime_state import IMEState
from purchase.models.execution_decision import ExecutionDecision
from purchase.execution.direct_checkout_initializer import DirectCheckoutInitializer
from purchase.execution.checkout_executor import CheckoutExecutor
from purchase.services.sku_price_monitor import SkuPriceMonitor
from purchase.services.promotion_forensics import PromotionForensicsRecorder


class PurchasePipeline:

    def __init__(self):
        self.direct_checkout_initializer = DirectCheckoutInitializer()
        self.sku_monitor = SkuPriceMonitor()
        self.checkout_executor = CheckoutExecutor()
        self.execution_decision: ExecutionDecision | None = None
        self._cancelled = threading.Event()

    def stop(self):
        """Stop monitoring without closing the purchase browser session."""
        self._cancelled.set()
        try:
            self.sku_monitor.stop()
        except Exception as e:
            print(
                "[PurchasePipeline] "
                f"Monitor stop warning: {e}"
            )

    def run(
        self,
        session: PurchaseSession,
        on_trigger=None,
        ime_state: IMEState | None = None,
    ):
        print()
        print(
            "[PurchasePipeline] "
            "========== STARTING PURCHASE PIPELINE =========="
        )

        monitor_thread = None
        self.execution_decision = None
        session.execution_decision = None
        forensics = PromotionForensicsRecorder.start(session)

        forensics.attach_engine(self.direct_checkout_initializer.browser.engine)
        forensics.record_event(
            "pipeline_started",
            "startup",
            {"cart_flow_enabled": False},
        )

        try:
            if self._cancelled.is_set():
                print("[PurchasePipeline] Pipeline already cancelled.")
                return False

            # =================================================
            # 1. PREPARE PRODUCT CONTEXT — NO CART
            # =================================================
            session.status = PurchaseStatus.PREPARING
            forensics.record_event(
                "product_context_preparation_started",
                "pdp",
            )

            print(
                "[PurchasePipeline] "
                "Preparing selected product context without cart..."
            )
            self.direct_checkout_initializer.prepare(session)

            if session.browser_session is not None:
                forensics.bind_session(session.browser_session)
                forensics.record_phase(
                    "product_context_prepared",
                    session.browser_session.page,
                )

            forensics.record_event(
                "product_context_preparation_completed",
                "pdp",
                {
                    "item_id": session.product.item_id,
                    "model_id": session.variation.model_id,
                    "variation_options": dict(session.request.options),
                    "quantity": session.request.quantity,
                },
            )

            # =================================================
            # 2. START SKU MONITOR
            # =================================================
            print("[PurchasePipeline] Starting SKU monitor...")
            forensics.record_event("sku_monitor_started", "pdp")

            monitor_thread = threading.Thread(
                target=self.sku_monitor.monitor,
                args=(session,),
                kwargs={
                    "poll_interval": session.request.polling_interval,
                    "cancellation_event": self._cancelled,
                },
                daemon=True,
            )
            monitor_thread.start()

            # =================================================
            # 3. WAIT FOR TRIGGER
            # =================================================
            print("[PurchasePipeline] Waiting for purchase trigger...")
            triggered = self.sku_monitor.wait_for_trigger(
                cancellation_event=self._cancelled,
            )

            if not triggered:
                if self._cancelled.is_set():
                    print("[PurchasePipeline] Pipeline cancelled.")
                    return False

                print("[PurchasePipeline] Purchase trigger not received.")
                session.status = PurchaseStatus.FAILED
                return False

            # =================================================
            # 4. BUILD EXECUTION DECISION
            # =================================================
            print()
            print(
                "[PurchasePipeline] "
                "========== PURCHASE TRIGGER RECEIVED =========="
            )

            current_ime_state = ime_state or session.ime_state
            latest_state = self.sku_monitor.latest_state

            if current_ime_state is not IMEState.EXECUTION_READY:
                print(
                    "[PurchasePipeline] "
                    f"IME state is {current_ime_state}; execution is not ready."
                )
                return False

            if latest_state is None:
                print(
                    "[PurchasePipeline] "
                    "No latest SKU state is available for execution decision."
                )
                return False

            self.execution_decision = ExecutionDecision(
                item_id=latest_state.item_id,
                model_id=latest_state.model_id,
                variation_options=tuple(sorted(
                    (str(key), str(value))
                    for key, value in session.request.options.items()
                )),
                quantity=session.request.quantity,
                promotion_id=latest_state.promotion_id,
                target_price=session.request.target_price,
                execution_state=current_ime_state,
            )
            session.execution_decision = self.execution_decision

            forensics.record_event(
                "purchase_trigger_received",
                "trigger",
                {
                    "item_id": session.monitored_item_id,
                    "model_id": session.monitored_model_id,
                    "sku_identity_verified": session.monitored_sku_identity_verified,
                    "ime_state": current_ime_state.value,
                    "execution_decision": {
                        "item_id": self.execution_decision.item_id,
                        "model_id": self.execution_decision.model_id,
                        "variation_options": dict(
                            self.execution_decision.variation_options
                        ),
                        "quantity": self.execution_decision.quantity,
                        "promotion_id": self.execution_decision.promotion_id,
                        "target_price": self.execution_decision.target_price,
                        "execution_state": self.execution_decision.execution_state.value,
                    },
                },
            )

            if on_trigger:
                on_trigger()

            # =================================================
            # 5. STOP MONITORING
            # =================================================
            print("[PurchasePipeline] Stopping SKU monitor...")
            self.sku_monitor.stop()
            self._cancelled.set()

            if monitor_thread is not None and monitor_thread.is_alive():
                monitor_thread.join(timeout=10)

            # =================================================
            # 6. AUTO CHECKOUT OFF
            # =================================================
            if not session.request.auto_checkout:
                print()
                print("[PurchasePipeline] Auto Checkout is OFF.")
                print(
                    "[PurchasePipeline] "
                    "Trigger recorded; browser remains on the selected PDP context."
                )
                forensics.record_event(
                    "auto_checkout_disabled",
                    "trigger",
                    {"cart_flow_enabled": False},
                )
                return True

            # =================================================
            # 7. DIRECT CHECKOUT
            # =================================================
            print()
            print("[PurchasePipeline] Auto Checkout is ON.")
            print(
                "[PurchasePipeline] "
                "Starting direct checkout without cart..."
            )
            forensics.record_event(
                "checkout_execution_started",
                "checkout",
                {
                    "checkout_route": "pdp_native_buy_now",
                    "cart_flow_enabled": False,
                    "buy_now_click_enabled": True,
                },
            )

            session.status = PurchaseStatus.CHECKING_OUT

            direct_checkout_started = forensics.record_event(
                "direct_checkout_initialization_started",
                "checkout",
                {
                    "item_id": self.execution_decision.item_id,
                    "model_id": self.execution_decision.model_id,
                    "promotion_id": self.execution_decision.promotion_id,
                    "checkout_route": "pdp_native_buy_now",
                },
            )

            checkout_initialized = self.direct_checkout_initializer.initialize(
                session,
                self.execution_decision,
            )

            if not checkout_initialized:
                print(
                    "[PurchasePipeline] "
                    "Direct checkout initialization failed."
                )
                forensics.record_event(
                    "direct_checkout_initialization_failed",
                    "checkout",
                    {
                        "cart_flow_fallback": False,
                        "checkout_route": "pdp_native_buy_now",
                    },
                )
                session.status = PurchaseStatus.FAILED
                return False

            forensics.record_event(
                "direct_checkout_initialization_completed",
                "checkout",
                {
                    "cart_flow_enabled": False,
                    "url": session.browser_session.page.url,
                },
            )

            checkout_success = self.checkout_executor.execute(
                session,
                forensics=forensics,
            )

            if not checkout_success:
                print("[PurchasePipeline] Checkout execution failed.")
                forensics.record_event(
                    "checkout_execution_failed",
                    "checkout",
                )
                session.status = PurchaseStatus.FAILED
                return False

            forensics.record_event(
                "checkout_execution_completed",
                "checkout",
                {
                    "item_id": session.product.item_id,
                    "model_id": session.variation.model_id,
                    "cart_flow_enabled": False,
                    "checkout_route": "pdp_native_buy_now",
                },
            )

            session.status = PurchaseStatus.COMPLETED

            print()
            print(
                "[PurchasePipeline] "
                "Checkout page reached and verified."
            )
            print("[PurchasePipeline] Place Order detected.")

            # CheckoutExecutor intentionally stops here unless a separate
            # runtime safety authorization is explicitly present.
            return True

        except Exception:
            session.status = PurchaseStatus.FAILED
            raise

        finally:
            try:
                self.sku_monitor.stop()
            except Exception as e:
                print(
                    "[PurchasePipeline] "
                    f"Final monitor stop warning: {e}"
                )

            if monitor_thread is not None and monitor_thread.is_alive():
                monitor_thread.join(timeout=10)

            try:
                forensics.record_event(
                    "pipeline_finished",
                    "final",
                    {
                        "status": getattr(
                            session.status,
                            "value",
                            str(session.status),
                        ),
                        "browser_session_preserved": session.browser_session is not None,
                        "cart_flow_enabled": False,
                    },
                )
            except Exception as e:
                print(
                    "[PurchasePipeline] "
                    f"Forensics terminal event warning: {e}"
                )

            PromotionForensicsRecorder.stop(session)

            print(
                "[PurchasePipeline] "
                "Pipeline finished; browser session preserved."
            )
