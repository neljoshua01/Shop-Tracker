"""Validate that the monitored SKU became the newly-created Shopee order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PURCHASE_URL = "https://shopee.ph/user/purchase/"
ORDER_LIST_ENDPOINT = "/api/v4/order/get_all_order_and_checkout_list"


@dataclass(slots=True)
class MonitoredOrderIdentity:
    order_id: int
    checkout_id: int | None
    item_id: int
    model_id: int
    shop_id: int
    product_name: str
    variation: str | None
    status: str | None
    shop_name: str | None
    seller_username: str | None
    quantity: int | None
    item_price: int | None
    original_price: int | None
    order_price: int | None
    subtotal: int | None
    final_total: int | None
    source_url: str


class MonitoredOrderIdentityInspector:
    """Read-only order identity validation using Shopee's order-list response."""

    WAIT_TIMEOUT_MS = 15000
    LOAD_WAIT_MS = 2500

    async def inspect(self, source_page: Any, session: Any) -> MonitoredOrderIdentity | None:
        """Open My Purchase in a separate tab and validate the exact monitored SKU."""
        product = session.product
        variation = session.variation
        expected_item_id = self._int(product.item_id)
        expected_model_id = self._int(variation.model_id)
        expected_shop_id = self._int(product.shop_id)
        expected_name = self._normalize(getattr(product, "product_name", ""))

        if expected_item_id is None or expected_model_id is None or expected_shop_id is None:
            print("[MonitoredOrderIdentity] Missing monitored product identity; validation aborted.")
            return None

        page = await source_page.context.new_page()
        responses: list[Any] = []

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
            print("[MonitoredOrderIdentity] Opening /user/purchase/ in a separate browser tab...")
            await page.goto(PURCHASE_URL, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(self.LOAD_WAIT_MS)

            matches: list[MonitoredOrderIdentity] = []
            for source_url, payload in responses:
                for index, container in self._iter_containers(payload):
                    matches.extend(
                        self._extract_matches(
                            source_url,
                            index,
                            container,
                            expected_item_id,
                            expected_model_id,
                            expected_shop_id,
                            expected_name,
                        )
                    )

            unique: dict[tuple[Any, ...], MonitoredOrderIdentity] = {}
            for match in matches:
                unique[
                    (
                        match.order_id,
                        match.checkout_id,
                        match.item_id,
                        match.model_id,
                        match.shop_id,
                        match.product_name,
                    )
                ] = match
            matches = list(unique.values())

            if len(matches) != 1:
                print(
                    "[MonitoredOrderIdentity] "
                    f"Validation failed: expected exactly one matching order, found {len(matches)}."
                )
                return None

            match = matches[0]
            if match.order_id <= 0:
                print("[MonitoredOrderIdentity] Validation failed: invalid Order ID.")
                return None
            if match.order_id == match.checkout_id:
                print("[MonitoredOrderIdentity] Validation failed: Order ID equals Checkout ID.")
                return None

            print("[MonitoredOrderIdentity] PASS — unique monitored product -> created order match.")
            print(f"[MonitoredOrderIdentity] Order ID : {match.order_id}")
            print(f"[MonitoredOrderIdentity] Checkout : {match.checkout_id or '<not exposed>'}")
            print(f"[MonitoredOrderIdentity] Item ID  : {match.item_id}")
            print(f"[MonitoredOrderIdentity] Model ID : {match.model_id}")
            print(f"[MonitoredOrderIdentity] Shop ID  : {match.shop_id}")
            print(f"[MonitoredOrderIdentity] Product  : {match.product_name}")
            print(f"[MonitoredOrderIdentity] Status   : {match.status or '<not found>'}")
            return match
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass
            try:
                await page.close()
            except Exception:
                pass

    @classmethod
    def _extract_matches(
        cls,
        source_url: str,
        container_index: int,
        container: dict[str, Any],
        expected_item_id: int,
        expected_model_id: int,
        expected_shop_id: int,
        expected_name: str,
    ) -> list[MonitoredOrderIdentity]:
        info = container.get("info_card")
        if not isinstance(info, dict):
            return []

        checkout_id = cls._int(info.get("checkout_id"))
        container_order_id = cls._int(info.get("order_id"))

        status_value = container.get("status")
        status = None
        if isinstance(status_value, dict):
            label = status_value.get("list_view_status_label")
            if isinstance(label, dict):
                status = cls._text(label.get("text"))
            if not status:
                header = status_value.get("header_text")
                if isinstance(header, dict):
                    status = cls._text(header.get("text"))

        cards = info.get("order_list_cards")
        if not isinstance(cards, list):
            return []

        results: list[MonitoredOrderIdentity] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            order_id = cls._int(card.get("order_id")) or container_order_id
            if order_id is None:
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
            if expected_name and cls._normalize(product_name) != expected_name:
                continue

            results.append(
                MonitoredOrderIdentity(
                    order_id=order_id,
                    checkout_id=checkout_id,
                    item_id=item_id,
                    model_id=model_id,
                    shop_id=shop_id,
                    product_name=product_name,
                    variation=cls._text(item.get("model_name")),
                    status=status,
                    shop_name=cls._text(shop.get("shop_name")),
                    seller_username=cls._text(shop.get("username")),
                    quantity=cls._int(item.get("amount")),
                    item_price=cls._int(item.get("item_price")),
                    original_price=cls._int(item.get("price_before_discount")),
                    order_price=cls._int(item.get("order_price")),
                    subtotal=cls._int(info.get("subtotal")),
                    final_total=cls._int(info.get("final_total")),
                    source_url=source_url,
                )
            )

        return results

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
