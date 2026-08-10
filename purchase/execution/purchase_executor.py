from execution.browser.browser_connector import BrowserConnector
from purchase.models.purchase_session import PurchaseSession
from purchase.execution.variation_selector import VariationSelector


class PurchaseExecutor:

    def __init__(self):

        self.browser = BrowserConnector()
        self.variation_selector = VariationSelector()

    def execute(
        self,
        session: PurchaseSession,
    ):

        self._open_product(session)

        self._select_variation(session)

        # self._verify_selection(session)

        # self._set_quantity(session)

        # self._buy_now(session)

    def _open_product(
        self,
        session: PurchaseSession,
    ):

        browser_session = self.browser.open_session(
            self,
            session.request.reference.url,
        )

        session.browser_session = browser_session

    def _select_variation(
        self,
        session,
    ):

        self.variation_selector.select(session)

    def close(self):

        self.browser.disconnect()