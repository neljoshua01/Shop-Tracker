"""Validate the established order identity reaching Shopee To Ship."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PURCHASE_TO_SHIP_URL = "https://shopee.ph/user/purchase/?type=7"
ORDER_LIST_ENDPOINT = "/api/v4/order/get_all_order_and_checkout_list"
EXPECTED_TO_SHIP_STATUS = "label_to_ship"


@dataclass(slots=True)
class SuccessfulPurchaseIdentity:
    """Validated continuity from the established order into To Ship."""

    order_id: int
    item_id: int
    model_id: int
    shop_id: int
    product_name: str
    variation: str | None
    status: str
    source_url: str
    authoritative: bool


class SuccessfulPurchaseIdentityInspector:
    """Read-only validation of an established order reaching To Ship."""

    DEFAULT_TIMEOUT_SECONDS = 1800.0
    POLL_INTERVAL_SECONDS = 10.0
    LOAD_WAIT_MS = 2500
    NAVIGATION_TIMEOUT_MS = 30000

    async def inspect(self, source_page: Any, session: Any) -> SuccessfulPurchaseIdentity | None:
        """Wait for the Step 1 order to appear as the same product in To Ship."""
        if not getattr(session, "monitored_order_identity_verified", False):
            print("[SuccessfulPurchaseIdentity] Step 1 identity is not verified; Step 2 aborted.")
            return None

        order_id = self._int(getattr(session, "monitored_order_id", None))
        item_id = self._int(getattr(session.product, "item_id", None))
        model_id = self._int(getattr(session.variation, "model_id", None))
        shop_id = self._int(getattr(session.product, "shop_id", None))
        product_name = self._normalize(getattr(session.product, "product_name", ""))
        variation = self._normalize(getattr(session.variation, "name", ""))

        if order_id is None or item_id is None or model_id is None or shop_id is None:
            print("[SuccessfulPurchaseIdentity] Required Step 1 identity fields are missing; Step 2 aborted.")
            return None

        timeout_seconds = self._timeout_seconds()
        started = asyncio.get_running_loop().time()
        attempt = 0

        page = await source_page.context.new_page()
        try:
            while True:
                attempt += 1
                elapsed = asyncio.get_running_loop().time() - started
                if elapsed >= timeout_seconds:
                    print(
                        "[SuccessfulPurchaseIdentity] To Ship validation timed out after "
                        f"{elapsed:.1f}s."
                    )
                    return None

                print(
                    "[SuccessfulPurchaseIdentity] STEP 2: checking To Ship "
                    f"(attempt {attempt}, elapsed {elapsed:.1f}s)..."
                )

                result = await self._check_once(
                    page,
                    order_id,
                    item_id,
                    model_id,
                    shop_id,
                    product_name,
                    variation,
                )
                if result is not None:
                    print("[SuccessfulPurchaseIdentity] PASS — same paid product is in To Ship.")
                    print(f"[SuccessfulPurchaseIdentity] Order ID : {result.order_id}")
                    print(f"[SuccessfulPurchaseIdentity] Item ID  : {result.item_id}")
                    print(f"[SuccessfulPurchaseIdentity] Model ID : {result.model_id}")
                    print(f"[SuccessfulPurchaseIdentity] Shop ID  : {result.shop_id}")
                    print(f"[SuccessfulPurchaseIdentity] Product  : {result.product_name}")
                    print(f"[SuccessfulPurchaseIdentity] Variation: {result.variation or '<not exposed>'}")
                    print(f"[SuccessfulPurchaseIdentity] Status   : {result.status}")
                    print(
                        "[SuccessfulPurchaseIdentity] Evidence : "
                        + ("authoritative order-list response" if result.authoritative else "page-visible continuity fallback")
                    )
                    return result

                remaining = timeout_seconds - (asyncio.get_running_loop().time() - started)
                if remaining <= 0:
                    continue
                await asyncio.sleep(min(self.POLL_INTERVAL_SECONDS, remaining))
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def _check_once(
        self,
        page: Any,
        order_id: int,
        item_id: int,
        model_id: int,
        shop_id: int,
        product_name: str,
        variation: str,
    ) -> SuccessfulPurchaseIdentity | None:
        responses: list[tuple[str, Any]] = []

        async def on_response(response: Any) -> None:
            if ORDER_LIST_ENDPOINT not in response.url.lower() or response.status != 200:
                return
            try:
                payload = await response.json()
            except Exception:
                return
            responses.append((response.url, payload))

        page.on("response", on_response)
        try:
            try:
                await page.goto(
                    PURCHASE_TO_SHIP_URL,
                    wait_until="domcontentloaded",
                    timeout=self.NAVIGATION_TIMEOUT_MS,
                )
            except Exception as exc:
                print(f"[SuccessfulPurchaseIdentity] Navigation warning: {exc}")
                return None

            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(self.LOAD_WAIT_MS)

            for source_url, payload in responses:
                for _, container in self._iter_containers(payload):
                    match = self._extract_authoritative_match(
                        source_url,
                        container,
                        order_id,
                        item_id,
                        model_id,
                        shop_id,
                        product_name,
                    )
                    if match is not None and match.status.casefold() == EXPECTED_TO_SHIP_STATUS:
                        return match

            body = await self._safe_body_text(page)
            if not body:
                return None

            normalized_body = body.casefold()
            product_visible = bool(product_name) and product_name.casefold() in normalized_body
            variation_visible = not variation or variation.casefold() in normalized_body
            to_ship_visible = "to ship" in normalized_body
            if not product_visible or not variation_visible or not to_ship_visible:
                return None

            visible_order_ids = await self._extract_order_ids_from_links(page)
            if visible_order_ids and order_id not in visible_order_ids:
                return None

            return SuccessfulPurchaseIdentity(
                order_id=order_id,
                item_id=item_id,
                model_id=model_id,
                shop_id=shop_id,
                product_name=product_name,
                variation=variation or None,
                status=EXPECTED_TO_SHIP_STATUS,
                source_url=PURCHASE_TO_SHIP_URL,
                authoritative=False,
            )
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass

    @classmethod
    def _extract_authoritative_match(
        cls,
        source_url: str,
        container: dict[str, Any],
        expected_order_id: int,
        expected_item_id: int,
        expected_model_id: int,
        expected_shop_id: int,
        expected_product_name: str,
    ) -> SuccessfulPurchaseIdentity | None:
        info = container.get("info_card")
        if not isinstance(info, dict):
            return None

        status = cls._extract_status(container)
        if not status:
            return None

        cards = info.get("order_list_cards")
        if not isinstance(cards, list):
            return None

        matches: list[SuccessfulPurchaseIdentity] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            card_order_id = cls._int(card.get("order_id"))
            if card_order_id != expected_order_id:
                continue

            shop = card.get("shop_info")
            shop = shop if isinstance(shop, dict) else {}
            item = cls._first_item(card)
            if item is None:
                continue

            item_id = cls._int(item.get("item_id"))
            model_id = cls._int(item.get("model_id"))
            shop_id = cls._int(shop.get("shop_id")) or cls._int(item.get("shop_id"))
            product_name = cls._text(item.get("name")) or ""

            if item_id != expected_item_id or model_id != expected_model_id or shop_id != expected_shop_id:
                continue
            if expected_product_name and cls._normalize(product_name) != expected_product_name:
                continue

            matches.append(
                SuccessfulPurchaseIdentity(
                    order_id=card_order_id,
                    item_id=item_id,
                    model_id=model_id,
                    shop_id=shop_id,
                    product_name=product_name,
                    variation=cls._text(item.get("model_name")),
                    status=status,
                    source_url=source_url,
                    authoritative=True,
                )
            )

        if len(matches) != 1:
            return None
        return matches[0]

    @staticmethod
    def _iter_containers(payload: Any) -> list[tuple[int, dict[str, Any]]]:
        if not isinstance(payload, dict):
            return []
        new_data = payload.get("new_data")
        if not isinstance(new_data, dict):
            return []
        entries = new_data.get("order_or_checkout_data")
        if not isinstance(entries, list):
            return []

        result: list[tuple[int, dict[str, Any]]] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            for key in ("checkout_list_detail", "order_list_detail"):
                container = entry.get(key)
                if isinstance(container, dict):
                    result.append((index, container))
                    break
        return result

    @staticmethod
    def _first_item(card: dict[str, Any]) -> dict[str, Any] | None:
        product_info = card.get("product_info")
        if not isinstance(product_info, dict):
            return None
        groups = product_info.get("item_groups")
        if not isinstance(groups, list):
            return None
        for group in groups:
            if not isinstance(group, dict):
                continue
            items = group.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    return item
        return None

    @staticmethod
    def _extract_status(container: dict[str, Any]) -> str | None:
        status_value = container.get("status")
        if not isinstance(status_value, dict):
            return None
        label = status_value.get("list_view_status_label")
        if isinstance(label, dict):
            value = SuccessfulPurchaseIdentityInspector._text(label.get("text"))
            if value:
                return value
        header = status_value.get("header_text")
        if isinstance(header, dict):
            value = SuccessfulPurchaseIdentityInspector._text(header.get("text"))
            if value:
                return value
        return None

    @staticmethod
    async def _safe_body_text(page: Any) -> str:
        try:
            return " ".join((await page.locator("body").inner_text(timeout=5000) or "").split())
        except Exception:
            return ""

    @staticmethod
    async def _extract_order_ids_from_links(page: Any) -> set[int]:
        try:
            links = await page.locator("a").evaluate_all(
                """
                els => els.map(el => ({
                    href: el.href || '',
                    text: (el.innerText || el.textContent || '').trim()
                }))
                """
            )
        except Exception:
            return set()

        found: set[int] = set()
        for link in links:
            text = f"{link.get('href', '')} {link.get('text', '')}"
            for value in re.findall(r"(?:order[_-]?id|orderid)[=/:-](\d{10,})", text, re.I):
                found.add(int(value))
        return found

    @classmethod
    def _timeout_seconds(cls) -> float:
        raw = os.getenv("SHOPEE_SUCCESSFUL_PURCHASE_TIMEOUT_SECONDS")
        if raw:
            try:
                return max(30.0, float(raw))
            except ValueError:
                pass
        return cls.DEFAULT_TIMEOUT_SECONDS

    @staticmethod
    def _int(value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None:
            return None
        value = " ".join(str(value).split()).strip()
        return value or None

    @classmethod
    def _normalize(cls, value: Any) -> str:
        return (cls._text(value) or "").casefold()

    @staticmethod
    def safe_url(url: str) -> str:
        parsed = urlsplit(url)
        pairs = [(key, "<redacted>") for key, _ in parse_qsl(parsed.query, keep_blank_values=True)]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), ""))
