from execution.browser.browser_connector import BrowserConnector
from execution.browser.browser_action import BrowserActions

from purchase.execution.purchase_page import PurchasePage

from purchase.models.product_reference import ProductReference


reference = ProductReference(
    shop_id=448087759,
    item_id=42720981321,
    url="https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321",
)


def main():

    browser = BrowserConnector()

    browser.connect()

    session = browser.open_session(
        "test_purchase_page",
        reference.url,
    )

    actions = BrowserActions(session)

    purchase_page = PurchasePage(actions)

    panel = purchase_page.get_purchase_panel()

    print()
    print("========== PURCHASE PANEL ==========")

    print(
        "Panel found:",
        panel is not None,
    )

    browser.close_session(
        "test_purchase_page",
    )

    browser.disconnect()


if __name__ == "__main__":
    main()