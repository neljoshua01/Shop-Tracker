import inspect

from core.runtime.async_runtime import AsyncRuntime
from playwright.async_api import async_playwright
from execution.browser.browser_session import BrowserSession


class BrowserEngine:

    _instance = None

    def __init__(self):

        self.playwright = None
        self.browser = None
        self.runtime = AsyncRuntime.instance()

        #
        # Owner -> BrowserSession
        #
        self.sessions = {}

        #
        # Owner -> callback.  This is retained for callers that
        # register before opening their own session.
        self.response_callbacks = {}

        # BrowserSession id -> {callback owner -> callback}.
        # BrowserSession is mutable and deliberately not hashable,
        # so its object identity is the internal registry key.
        self.session_callbacks = {}

        # Compatibility bookkeeping for the old open_page/close_page
        # facade.  Production code uses BrowserSession directly.
        self._page_owners = {}

    # =====================================================
    # Singleton
    # =====================================================

    @classmethod
    def instance(cls):

        if cls._instance is None:
            cls._instance = cls()

        return cls._instance

    # =====================================================
    # Browser Connection
    # =====================================================

    async def connect(self):

        if self.browser:
            return self.browser

        print("[BrowserEngine] Starting Playwright...")

        self.playwright = await async_playwright().start()

        print("[BrowserEngine] Connecting to Chrome...")

        self.browser = await self.playwright.chromium.connect_over_cdp(
            "http://localhost:9222"
        )

        print("[BrowserEngine] Connected.")

        return self.browser

    # =====================================================
    # Page Management
    # =====================================================

    async def open_session(
        self,
        owner,
        url,
    ):

        await self.connect()

        context = self.browser.contexts[0]

        page = await context.new_page()

        session = BrowserSession(
            context=context,
            page=page,
        )

        #
        # IMPORTANT:
        #
        # The response listener is attached to the BrowserSession,
        # not permanently to the owner that happened to create it.
        #
        # This allows another component, such as SkuPriceMonitor,
        # to register a callback against the existing session later.
        #
        page.on(
            "response",
            lambda response: self._on_response(
                session,
                response,
            ),
        )

        await page.goto(
            url,
            wait_until="domcontentloaded",
        )

        self.sessions[owner] = session

        #
        # If the owner registered a callback before the session
        # existed, bind that callback to this newly created session.
        #
        owner_callback = self.response_callbacks.get(
            owner,
        )

        if owner_callback is not None:
            self._bind_session_callback(owner, session, owner_callback)

        print(
            f"[BrowserEngine] "
            f"Session opened ({owner})"
        )

        return session

    def _on_response(
        self,
        session,
        response,
    ):

        callbacks = list(self.session_callbacks.get(id(session), {}).values())

        if not callbacks:
            return

        if "/api/v4/pdp/get_pc" in response.url:
            print(
                "[BrowserEngine] "
                f"Response: {response.status} {response.url}"
            )

        for callback in callbacks:
            try:
                result = callback(response)

                if inspect.isawaitable(result):
                    self.runtime.submit(self._await_callback(result))

            except Exception as e:
                print(
                    "[BrowserEngine] "
                    f"Response callback error: {e}"
                )

    async def _await_callback(
        self,
        callback,
    ):

        try:

            await callback

        except Exception as e:

            print(
                "[BrowserEngine] "
                f"Async response callback error: {e}"
            )

    def _bind_session_callback(self, owner, session, callback):
        self.session_callbacks.setdefault(id(session), {})[owner] = callback

    async def get_session(
        self,
        owner,
        url,
    ):

        if owner in self.sessions:

            session = self.sessions[owner]

            if not session.page.is_closed():

                print(
                    f"[BrowserEngine] "
                    f"Reusing session ({owner})"
                )

                return session

            #
            # Existing session is no longer usable.
            #
            self._cleanup_session(
                owner,
                session,
            )

        return await self.open_session(
            owner,
            url,
        )

    async def close_session(
        self,
        owner,
    ):

        session = self.sessions.get(
            owner,
        )

        if session is None:
            return

        if session.page.is_closed():

            self._cleanup_session(
                owner,
                session,
            )

            return

        await session.close()

        self._cleanup_session(
            owner,
            session,
        )

        print(
            f"[BrowserEngine] "
            f"Session closed ({owner})"
        )

    def _cleanup_session(
        self,
        owner,
        session,
    ):

        callbacks = self.session_callbacks.pop(id(session), {})

        # A callback attached to a closing page cannot remain a live
        # owner registration.  This also prevents stale monitor
        # callbacks after an exceptional page close.
        for callback_owner in callbacks:
            self.response_callbacks.pop(callback_owner, None)

        #
        # Remove owner callback.
        #
        self.response_callbacks.pop(
            owner,
            None,
        )

        #
        # Remove session ownership.
        #
        self.sessions.pop(
            owner,
            None,
        )

        for page_id, page_owner in list(self._page_owners.items()):
            if page_owner is owner:
                self._page_owners.pop(page_id, None)

    # =====================================================
    # Response Callbacks
    # =====================================================

    def register_response_callback(
        self,
        owner,
        callback,
        session=None,
    ):

        #
        # Preserve the existing owner-based registration API.
        #
        self.response_callbacks[owner] = callback

        #
        # If a BrowserSession is supplied, bind the callback
        # directly to that session.
        #
        # This is the mechanism V2 components such as
        # SkuPriceMonitor will use.
        #
        if session is not None:

            self._bind_session_callback(owner, session, callback)

        else:

            #
            # If the owner already owns an existing session,
            # bind the callback to that session as well.
            #
            existing_session = self.sessions.get(
                owner,
            )

            if existing_session is not None:

                self._bind_session_callback(owner, existing_session, callback)

        print(
            "[BrowserEngine] "
            f"Response callback registered for owner: "
            f"{owner}"
        )

        if session is not None:

            print(
                "[BrowserEngine] "
                "Response callback bound to BrowserSession."
            )

    def unregister_response_callback(
        self,
        owner,
        session=None,
    ):

        #
        # If a specific session was supplied, remove only the
        # callback associated with that session.
        #
        if session is not None:

            callbacks = self.session_callbacks.get(id(session))
            if callbacks is not None:
                callbacks.pop(owner, None)
                if not callbacks:
                    self.session_callbacks.pop(id(session), None)

        #
        # Remove the owner's callback.
        #
        self.response_callbacks.pop(
            owner,
            None,
        )

        #
        # If the owner has a session and no explicit session
        # was supplied, remove that session callback too.
        #
        if session is None:

            existing_session = self.sessions.get(
                owner,
            )

            if existing_session is not None:

                callbacks = self.session_callbacks.get(id(existing_session))
                if callbacks is not None:
                    callbacks.pop(owner, None)
                    if not callbacks:
                        self.session_callbacks.pop(id(existing_session), None)

        print(
            "[BrowserEngine] "
            f"Response callback unregistered for owner: "
            f"{owner}"
        )

    # =====================================================
    # Browser Disconnect
    # =====================================================

    async def disconnect(self):

        #
        # Close every open session.
        #
        for owner in list(self.sessions.keys()):

            await self.close_session(
                owner,
            )

        #
        # Clear callback registries.
        #
        self.response_callbacks.clear()
        self.session_callbacks.clear()
        self._page_owners.clear()

        #
        # Disconnect browser.
        #
        if self.browser is not None:

            await self.browser.close()

            self.browser = None

        #
        # Stop Playwright.
        #
        if self.playwright is not None:

            await self.playwright.stop()

            self.playwright = None

        print(
            "[BrowserEngine] Disconnected."
        )

    # =====================================================
    # Legacy page facade
    # =====================================================

    async def open_page(self, url):
        """Compatibility wrapper for pre-session callers."""
        owner = object()
        session = await self.open_session(owner, url)
        self._page_owners[id(session.page)] = owner
        return session.page

    async def close_page(self, page):
        """Close a page opened through :meth:`open_page`."""
        owner = self._page_owners.pop(id(page), None)
        if owner is not None:
            await self.close_session(owner)
            return
        if not page.is_closed():
            await page.close()
