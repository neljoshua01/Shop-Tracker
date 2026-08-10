# from execution.browser.browser_action import BrowserActions


# class PurchasePage:

#     def __init__(
#         self,
#         browser: BrowserActions,
#     ):

#         self.browser = browser

#     def _find_purchase_button(self):

#         buttons = self.browser.find_all(
#             "button, [role='button']"
#         )

#         count = self.browser.count(buttons)

#         print(
#             f"[PurchasePage] Buttons found: {count}"
#         )

#         for i in range(count):

#             button = buttons.nth(i)

#             text = self.browser.text(button)

#             print(
#                 f"[PurchasePage] Button {i}: {repr(text)}"
#             )

#             if not text:
#                 continue

#             text = " ".join(
#                 text.split()
#             ).strip().lower()

#             if text in {
#                 "buy now",
#                 "buy with voucher",
#             }:

#                 print(
#                     "[PurchasePage] "
#                     f"Purchase button found: {repr(text)}"
#                 )

#                 return button

#         return None

#     def _scroll_to_purchase_area(
#         self,
#     ):

#         self.browser.scroll_to_bottom()

#     def get_purchase_panel(
#         self,
#     ):

#         self._scroll_to_purchase_area()

#         self.browser.wait_for_selector(
#             "button:has-text('Buy Now'), "
#             "button:has-text('Buy With Voucher'), "
#             "[role='button']:has-text('Buy Now'), "
#             "[role='button']:has-text('Buy With Voucher')",
#             timeout=10000,
#         )

#         buy_button = self._find_purchase_button()

#         if buy_button is None:
#             raise RuntimeError(
#                 "Purchase button not found."
#             )

#         current = buy_button

#         for level in range(10):

#             quantity = self.browser.find_all(
#                 'button[aria-label="Decrease"]',
#                 parent=current,
#             )

#             if self.browser.count(quantity) > 0:

#                 print(
#                     "[PurchasePage] "
#                     f"Purchase panel found at ancestor {level}"
#                 )

#                 return current

#             current = self.browser.parent(current)

#         raise RuntimeError(
#             "Purchase panel could not be found."
#         )

#     def get_variation_sections(
#         self,
#     ):
#         raise NotImplementedError

#     def get_quantity_section(
#         self,
#     ):
#         raise NotImplementedError

#     def get_buy_now_button(
#         self,
#     ):
#         raise NotImplementedError