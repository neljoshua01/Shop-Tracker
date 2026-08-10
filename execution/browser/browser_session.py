"""
Represents a browser session used during purchase execution.
"""

from dataclasses import dataclass

from playwright.async_api import BrowserContext
from playwright.async_api import Page


@dataclass(slots=True)
class BrowserSession:
    """
    Holds the browser objects associated with
    a single purchase execution.
    """

    context: BrowserContext

    page: Page

    @property
    def url(self) -> str:
        """
        Returns the current page URL.
        """

        return self.page.url

    async def close(self):
        """
        Closes the page if it is still open.
        """

        if self.page.is_closed():
            return

        await self.page.close()