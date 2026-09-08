"""Focused tests for supported Shopee product URL formats."""

from purchase.parser.url_parser import URLParser


STANDARD_URL = "https://shopee.ph/Some-Product-i.1275798143.26342037051"
PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"


def assert_reference(url, expected_shop_id, expected_item_id):
    reference = URLParser.parse(url)
    assert reference.shop_id == expected_shop_id
    assert reference.item_id == expected_item_id
    assert reference.url == url


def test_standard_product_url():
    assert_reference(
        STANDARD_URL,
        1275798143,
        26342037051,
    )


def test_promotional_product_url():
    assert_reference(
        PROMOTIONAL_URL,
        1275798143,
        26342037051,
    )


def test_promotional_product_url_with_query_string():
    url = f"{PROMOTIONAL_URL}?sp_atk=test"
    assert_reference(
        url,
        1275798143,
        26342037051,
    )


def test_invalid_url_is_rejected():
    try:
        URLParser.parse("https://shopee.ph/product/not-a-product")
    except ValueError as exc:
        assert str(exc) == "Invalid Shopee product URL."
    else:
        raise AssertionError("Invalid Shopee URL was accepted.")


if __name__ == "__main__":
    test_standard_product_url()
    test_promotional_product_url()
    test_promotional_product_url_with_query_string()
    test_invalid_url_is_rejected()
    print("URL parser tests: PASS")
