"""
Isolated diagnostic for Shopee promotion/campaign lifecycle changes.

This test does NOT modify production monitoring, cart, checkout, or IME code.
It repeatedly reloads one Shopee product URL and records the selected SKU's
price, stock, promotion, and campaign-related fields from PDP get_pc.

The purpose is to learn what changes across time before any production
architecture is changed to support promotional-event monitoring.

Usage:
    python3 tests/test_shopee_campaign_lifecycle.py
    python3 tests/test_shopee_campaign_lifecycle.py --duration 120 --interval 10
    python3 tests/test_shopee_campaign_lifecycle.py --model-id 139454633402
    python3 tests/test_shopee_campaign_lifecycle.py --dump /tmp/shopee_campaign_lifecycle.json
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from threading import Event, Lock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.browser.browser_connector import BrowserConnector

URL = "https://shopee.ph/product/1275798143/26342037051"
DEFAULT_MODEL_ID = 139454633402


class CampaignLifecycleInspector:
    """Collect read-only SKU lifecycle evidence from Shopee get_pc."""

    def __init__(self, model_id):
        self.browser = BrowserConnector()
        self.model_id = model_id
        self.response_event = Event()
        self.lock = Lock()
        self.session = None
        self.snapshots = []
        self.last_payload = None
        self.response_count = 0

    def run(self, url, duration, interval):
        self.browser.connect()
        self.browser.engine.register_response_callback(self, self.on_response)

        started_at = time.time()
        deadline = started_at + duration
        sample_number = 0
        final_url = url

        try:
            self.session = self.browser.open_session(self, url)
            final_url = self.session.url

            self._wait_for_response(timeout=min(20, max(1, interval)))
            self._record_latest_snapshot(sample_number=1)
            sample_number = 1

            while time.time() < deadline:
                remaining = deadline - time.time()
                sleep_for = min(interval, max(0, remaining))
                if sleep_for > 0:
                    time.sleep(sleep_for)

                if time.time() >= deadline:
                    break

                sample_number += 1
                self.response_event.clear()

                # Test-only direct reload. This diagnostic never participates
                # in production IME execution and makes no production changes.
                self.browser.runtime.submit(
                    self.session.page.reload(wait_until="domcontentloaded")
                ).result(timeout=30)

                self._wait_for_response(timeout=10)
                self._record_latest_snapshot(sample_number)

            final_url = self.session.url
        finally:
            self.browser.close_session(self)
            self.session = None
            self.browser.engine.unregister_response_callback(self)

        return final_url, started_at

    def _wait_for_response(self, timeout):
        if not self.response_event.wait(timeout=timeout):
            print("[CampaignLifecycleInspector] Timed out waiting for get_pc response.")

    async def on_response(self, response):
        if "/api/v4/pdp/get_pc" not in response.url:
            return

        try:
            payload = await response.json()
        except Exception as exc:
            print(f"[CampaignLifecycleInspector] Failed to decode get_pc JSON: {exc}")
            self.response_event.set()
            return

        with self.lock:
            self.last_payload = payload
            self.response_count += 1

        self.response_event.set()

    def _record_latest_snapshot(self, sample_number):
        with self.lock:
            payload = self.last_payload

        snapshot = self._extract_snapshot(payload)
        snapshot["sample"] = sample_number
        snapshot["captured_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.snapshots.append(snapshot)

        print(
            f"[{snapshot['captured_at']}] sample={sample_number} "
            f"model={snapshot['model_id']} price={snapshot['price']} "
            f"before={snapshot['price_before_discount']} "
            f"stock={snapshot['has_stock']} promotion={snapshot['promotion_id']} "
            f"type={snapshot['promotion_type']} "
            f"reserve={snapshot['current_promotion_has_reserve_stock']}"
        )

    def _extract_snapshot(self, payload):
        item = {}
        if isinstance(payload, dict):
            data = payload.get("data", {})
            if isinstance(data, dict):
                item = data.get("item", {})
                if not isinstance(item, dict):
                    item = {}

        model = self._find_model(item.get("models", []))
        product_price = item.get("product_price", {})
        if not isinstance(product_price, dict):
            product_price = {}

        price_promotion = product_price.get("price_promotion", {})
        if not isinstance(price_promotion, dict):
            price_promotion = {}

        price_model = product_price.get("price_model", {})
        if not isinstance(price_model, dict):
            price_model = {}

        return {
            "item_id": item.get("item_id"),
            "shop_id": item.get("shop_id"),
            "title": item.get("title"),
            "model_id": model.get("model_id"),
            "price": model.get("price"),
            "price_before_discount": model.get("price_before_discount"),
            "has_stock": model.get("has_stock"),
            "promotion_id": model.get("promotion_id"),
            "promotion_type": model.get("promotion_type"),
            "current_promotion_has_reserve_stock": model.get(
                "current_promotion_has_reserve_stock"
            ),
            "current_promotion_reserved_stock": model.get(
                "current_promotion_reserved_stock"
            ),
            "price_stocks": model.get("price_stocks"),
            "is_lowest_price_at_shopee": model.get("is_lowest_price_at_shopee"),
            "product_price_model_id": price_model.get("price_single_model_id"),
            "product_price_promotion_id": price_promotion.get(
                "price_single_promotion_id"
            ),
            "product_price_promotion_type": price_promotion.get(
                "price_single_promotion_type"
            ),
        }

    def _find_model(self, models):
        if not isinstance(models, list):
            return {}
        for model in models:
            if isinstance(model, dict) and model.get("model_id") == self.model_id:
                return model
        return {}

    def build_report(self, source_url, final_url, duration, interval):
        return {
            "source_url": source_url,
            "final_url": final_url,
            "model_id_requested": self.model_id,
            "duration_seconds": duration,
            "interval_seconds": interval,
            "get_pc_response_count": self.response_count,
            "snapshots": self.snapshots,
            "interpretation_notes": [
                "This report is observational only; it does not establish the semantic meaning of promotion_type values.",
                "Compare snapshots across a known campaign boundary before changing production logic.",
                "A missing model is recorded as an empty model snapshot rather than inferred from another SKU.",
            ],
        }


def print_report(report):
    print()
    print("=" * 90)
    print("SHOPEE CAMPAIGN / PROMOTION LIFECYCLE INSPECTION")
    print("=" * 90)
    print("Source URL        :", report["source_url"])
    print("Final URL         :", report["final_url"])
    print("Requested model   :", report["model_id_requested"])
    print("Duration          :", report["duration_seconds"], "seconds")
    print("Interval          :", report["interval_seconds"], "seconds")
    print("get_pc responses  :", report["get_pc_response_count"])

    print()
    print("-------------------- LIFECYCLE SNAPSHOTS --------------------")
    print(
        "sample | captured_at              | price | before | stock | "
        "promotion_id | type | reserve | lowest"
    )
    print("-" * 90)
    for snapshot in report["snapshots"]:
        print(
            f"{snapshot['sample']:>6} | {snapshot['captured_at']:<24} | "
            f"{str(snapshot['price']):>5} | {str(snapshot['price_before_discount']):>6} | "
            f"{str(snapshot['has_stock']):<5} | {str(snapshot['promotion_id']):>12} | "
            f"{str(snapshot['promotion_type']):>4} | "
            f"{str(snapshot['current_promotion_has_reserve_stock']):<7} | "
            f"{str(snapshot['is_lowest_price_at_shopee'])}"
        )

    print()
    print("-------------------- PRODUCT-LEVEL LINKAGE --------------------")
    for snapshot in report["snapshots"]:
        print(
            f"sample {snapshot['sample']}: "
            f"product_price_model_id={snapshot['product_price_model_id']}, "
            f"product_price_promotion_id={snapshot['product_price_promotion_id']}, "
            f"product_price_promotion_type={snapshot['product_price_promotion_type']}"
        )

    print()
    print("-------------------- NOTES --------------------")
    for note in report["interpretation_notes"]:
        print("-", note)
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=URL, help="Shopee product URL to inspect.")
    parser.add_argument(
        "--model-id",
        type=int,
        default=DEFAULT_MODEL_ID,
        help="Exact Shopee model/SKU ID to track.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=120,
        help="How long to observe, in seconds.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Seconds between PDP reloads.",
    )
    parser.add_argument("--dump", help="Optional path for the complete lifecycle JSON report.")
    args = parser.parse_args()

    if args.duration < 0:
        parser.error("--duration must be >= 0")
    if args.interval <= 0:
        parser.error("--interval must be > 0")

    inspector = CampaignLifecycleInspector(args.model_id)
    final_url, _ = inspector.run(
        args.url,
        duration=args.duration,
        interval=args.interval,
    )
    report = inspector.build_report(
        args.url,
        final_url,
        args.duration,
        args.interval,
    )
    print_report(report)

    if args.dump:
        path = Path(args.dump).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[CampaignLifecycleInspector] Full report written to: {path}")


if __name__ == "__main__":
    main()
