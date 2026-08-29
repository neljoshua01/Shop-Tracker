"""Unit tests for Step 7E post-order navigation classification."""

from purchase.services.post_order_tracker import PostOrderTracker


def test_safe_url_redacts_query_values():
    url = (
        "https://shopee.ph/verify/otp?operation=301&client_id=3&"
        "next=https%3A%2F%2Fexample.com%2Fsecret"
    )

    safe = PostOrderTracker._safe_url(url)

    assert "operation=<redacted>" in safe
    assert "client_id=<redacted>" in safe
    assert "next=<redacted>" in safe
    assert "secret" not in safe


def test_classifies_shopee_otp_page():
    state = PostOrderTracker._classify_state(
        "shopee.ph",
        "/verify/otp",
        "Shopee One Time Password",
        "Enter Verification Code",
    )

    assert state == "OTP_ENTRY"


def test_classifies_paylater_continuation():
    state = PostOrderTracker._classify_state(
        "h5.paylater.scredit.ph",
        "/pay_v2",
        "",
        "",
    )

    assert state == "PAYMENT_CONTINUATION"


def test_classifies_completion_from_confirmation_text():
    state = PostOrderTracker._classify_state(
        "shopee.ph",
        "/buyer/orders/123",
        "Shopee",
        "Order placed successfully. Order number: 123",
    )

    assert state == "PURCHASE_COMPLETED"


def test_generic_order_page_is_not_marked_complete_without_confirmation():
    state = PostOrderTracker._classify_state(
        "shopee.ph",
        "/buyer/orders",
        "Shopee Orders",
        "Your orders",
    )

    assert state == "POST_ORDER_NAVIGATION"


if __name__ == "__main__":
    tests = (
        test_safe_url_redacts_query_values,
        test_classifies_shopee_otp_page,
        test_classifies_paylater_continuation,
        test_classifies_completion_from_confirmation_text,
        test_generic_order_page_is_not_marked_complete_without_confirmation,
    )

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print("All Step 7E unit tests passed.")
