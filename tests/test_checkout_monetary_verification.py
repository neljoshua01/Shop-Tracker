import asyncio
import unittest

from execution.checkout.checkout_verifier import CheckoutVerifier
from purchase.models.product_info import ProductInfo
from purchase.models.product_reference import ProductReference
from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.variation import Variation


class CheckoutMonetaryVerificationTests(unittest.TestCase):

    def build_session(self, unit_price, quantity=1, target_price=1000):
        request = PurchaseRequest(
            reference=ProductReference(
                shop_id=1,
                item_id=2,
                url="https://shopee.ph/test",
            ),
            options={"color": "Black"},
            quantity=quantity,
            target_price=target_price * 100_000,
        )
        product = ProductInfo(
            item_id=2,
            shop_id=1,
            product_name="Test Product",
            shop_name="Test Shop",
            product_url="https://shopee.ph/test",
            currency="PHP",
            image="",
            available_variations=[],
        )
        variation = Variation(
            model_id=3,
            name="Black",
            options={"color": "Black"},
            price=unit_price,
            price_before_discount=unit_price,
            has_stock=True,
            tier_index=[0],
            sku_image="",
        )
        return PurchaseSession(
            request=request,
            product=product,
            variation=variation,
        )

    def run_summary(self, session, summary):
        verifier = CheckoutVerifier()
        verifier.selected_payment = session.request.payment_method.value
        return asyncio.run(
            verifier.verify_order_summary(None, session, summary)
        )

    def test_bavin_item_discount_and_voucher(self):
        session = self.build_session(688, target_price=1000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "seller": "Test Shop",
            "subtotal": 2899,
            "item_discount": 2211,
            "voucher_discount": 10,
            "shipping": 50,
            "total": 728,
        }
        self.assertTrue(self.run_summary(session, summary))

    def test_exact_sku_amount_passes(self):
        session = self.build_session(688, target_price=1000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 688,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 738,
        }
        self.assertTrue(self.run_summary(session, summary))

    def test_merchandise_above_sku_fails(self):
        session = self.build_session(688, target_price=1000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 700,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 750,
        }
        self.assertFalse(self.run_summary(session, summary))

    def test_quantity_two_uses_two_unit_ceiling(self):
        session = self.build_session(688, quantity=2, target_price=2000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 2,
            "subtotal": 1376,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 1426,
        }
        self.assertTrue(self.run_summary(session, summary))

    def test_quantity_two_above_ceiling_fails(self):
        session = self.build_session(688, quantity=2, target_price=2000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 2,
            "subtotal": 1377,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 1427,
        }
        self.assertFalse(self.run_summary(session, summary))

    def test_target_total_exceeded_fails_independently(self):
        session = self.build_session(688, target_price=1000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 688,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 1050,
        }
        self.assertFalse(self.run_summary(session, summary))

    def test_missing_voucher_with_item_discount_can_pass(self):
        session = self.build_session(16441, target_price=18000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 17990,
            "item_discount": 1549,
            "voucher_discount": None,
            "shipping": 50,
            "total": 17630,
        }
        self.assertTrue(self.run_summary(session, summary))

    def test_missing_voucher_and_incomplete_accounting_fails_closed(self):
        session = self.build_session(16441, target_price=18000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 17990,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 17630,
        }
        self.assertFalse(self.run_summary(session, summary))

    def test_missing_total_fails_closed(self):
        session = self.build_session(688, target_price=1000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 688,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": None,
        }
        self.assertFalse(self.run_summary(session, summary))

    def test_missing_target_fails_closed(self):
        session = self.build_session(688, target_price=1000)
        session.request.target_price = None
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 688,
            "item_discount": None,
            "voucher_discount": None,
            "shipping": 50,
            "total": 738,
        }
        self.assertFalse(self.run_summary(session, summary))

    def test_invalid_discount_accounting_fails_closed(self):
        session = self.build_session(688, target_price=1000)
        summary = {
            "product": "Test Product",
            "variation": "Black",
            "quantity": 1,
            "subtotal": 688,
            "item_discount": 700,
            "voucher_discount": None,
            "shipping": 50,
            "total": 738,
        }
        self.assertFalse(self.run_summary(session, summary))


if __name__ == "__main__":
    unittest.main()
