"""Phase 4 — historical/live promotional price forensics.

TEST-ONLY. This file does not modify production application code.

Purpose:
    1. Search local project artifacts for the historical 9.9 internal price
       990000000 and print the surrounding evidence.
    2. Capture the current live PDP get_pc response, save the COMPLETE raw
       JSON response bodies, and recursively locate every occurrence of
       990000000 plus all price/promotion fields associated with the requested
       item/model.

Safety boundary:
    - No production purchase pipeline is executed.
    - No Add To Cart.
    - No cart selection.
    - No checkout.
    - No payment.
    - No Place Order.
    - settings.json is not read or modified.
"""

import json
from datetime import datetime
from pathlib import Path

from core.runtime.async_runtime import AsyncRuntime
from execution.browser.browser_connector import BrowserConnector

PROMOTIONAL_URL = "https://shopee.ph/product/1275798143/26342037051"
ITEM_ID = 26342037051
SHOP_ID = 1275798143
TARGET_MODEL_IDS = {139454633402, 139454633406}
HISTORICAL_PRICE = 990000000
OBSERVE_SECONDS = 8
OWNER = "phase4_price_forensics"

SEARCH_ROOTS = (
    Path("tests/output"),
    Path("api_logs"),
    Path("logs"),
)
SEARCH_SUFFIXES = {".txt", ".json", ".log", ".md"}


def stamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def normalize_key(key):
    return str(key).strip().lower()


def number_like(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        raw = value.replace(",", "").replace("₱", "").strip()
        try:
            return float(raw)
        except ValueError:
            return value
    return value


def extract_target_records(node, path="root", out=None):
    """Collect target item/model records with every useful price/promo field."""
    if out is None:
        out = []

    if isinstance(node, dict):
        norm = {normalize_key(k): v for k, v in node.items()}
        item = norm.get("item_id", norm.get("itemid"))
        model = norm.get("model_id", norm.get("modelid"))
        if str(item) == str(ITEM_ID) or model in TARGET_MODEL_IDS:
            record = {
                "path": path,
                "item_id": item,
                "model_id": model,
                "shop_id": norm.get("shop_id", norm.get("shopid")),
                "name": norm.get("name") or norm.get("model_name") or norm.get("item_name"),
            }
            for key, value in norm.items():
                if (
                    "price" in key
                    or "promotion" in key
                    or "discount" in key
                    or key in {"final_price", "unit_price", "item_price"}
                ):
                    record[key] = number_like(value)
            out.append(record)
        for key, value in node.items():
            extract_target_records(value, f"{path}.{key}", out)

    elif isinstance(node, list):
        for index, value in enumerate(node):
            extract_target_records(value, f"{path}[{index}]", out)

    return out


def find_numeric_price_hits(node, target, path="root", out=None):
    """Find exact numeric/string occurrences of the historical price anywhere."""
    if out is None:
        out = []

    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            numeric = number_like(value)
            if isinstance(numeric, (int, float)) and not isinstance(numeric, bool):
                if numeric == target:
                    out.append(
                        {
                            "path": child_path,
                            "key": str(key),
                            "value": numeric,
                        }
                    )
            find_numeric_price_hits(value, target, child_path, out)

    elif isinstance(node, list):
        for index, value in enumerate(node):
            find_numeric_price_hits(value, target, f"{path}[{index}]", out)

    return out


def find_historical_hits():
    """Search local artifacts for the exact historical internal price."""
    hits = []
    checked = []

    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SEARCH_SUFFIXES:
                continue
            checked.append(str(path))
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            marker = str(HISTORICAL_PRICE)
            start = 0
            while True:
                index = text.find(marker, start)
                if index < 0:
                    break
                line_start = text.rfind("\n", 0, index) + 1
                line_end = text.find("\n", index)
                if line_end < 0:
                    line_end = len(text)
                context_start = max(0, line_start - 800)
                context_end = min(len(text), line_end + 800)
                hits.append(
                    {
                        "file": str(path),
                        "offset": index,
                        "line": text[line_start:line_end],
                        "context": text[context_start:context_end],
                    }
                )
                start = index + len(marker)

    return checked, hits


async def capture_live_get_pc(browser_session):
    page = browser_session.page
    responses = []

    def on_response(response):
        if "/api/v4/pdp/get_pc" in response.url.lower():
            responses.append(response)

    page.on("response", on_response)
    try:
        await page.goto(
            PROMOTIONAL_URL,
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await page.wait_for_timeout(OBSERVE_SECONDS * 1000)

        captured = []
        for index, response in enumerate(responses, start=1):
            entry = {
                "index": index,
                "url": response.url,
                "status": response.status,
                "method": response.request.method,
            }
            try:
                body = await response.json()
                # Preserve the complete raw get_pc response for later forensic
                # inspection. The previous test only retained extracted fields,
                # which could hide the exact promotion/price nesting.
                entry["body"] = body
                entry["target_records"] = extract_target_records(body)
                entry["historical_price_hits"] = find_numeric_price_hits(
                    body,
                    HISTORICAL_PRICE,
                )
            except Exception as exc:
                entry["json_error"] = repr(exc)
            captured.append(entry)
        return page.url, captured
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


def main():
    print("=" * 72)
    print("PHASE 4 — HISTORICAL/LIVE PROMOTIONAL PRICE FORENSICS")
    print("=" * 72)
    print(f"Target item:       {ITEM_ID}")
    print(f"Target models:     {sorted(TARGET_MODEL_IDS)}")
    print(f"Historical price:  {HISTORICAL_PRICE} (₱9,900)")
    print("Production code modified: NO")
    print("settings.json modified:   NO")
    print("Purchase actions:          NONE")
    print("=" * 72)

    checked, historical_hits = find_historical_hits()
    print()
    print("========== HISTORICAL ARTIFACT SCAN ==========")
    print(f"Files checked: {len(checked)}")
    print(f"990000000 hits: {len(historical_hits)}")

    for hit in historical_hits[:20]:
        print()
        print(f"[FORENSICS] HIT: {hit['file']}")
        print(f"[FORENSICS] Line: {hit['line']}")
        print("[FORENSICS] Context:")
        print(hit["context"])

    runtime = AsyncRuntime.instance()
    connector = BrowserConnector()
    browser_session = None
    run_dir = Path("tests/output") / f"phase4_price_forensics_{stamp()}"

    try:
        print()
        print("========== LIVE GET_PC CAPTURE ==========")
        browser_session = connector.open_session(OWNER, PROMOTIONAL_URL)
        final_url, live_records = runtime.submit(
            capture_live_get_pc(browser_session)
        ).result(timeout=60)

        run_dir.mkdir(parents=True, exist_ok=True)
        api_dir = run_dir / "api"
        api_dir.mkdir(parents=True, exist_ok=True)

        # Save each COMPLETE raw get_pc JSON body separately. This is the main
        # forensic artifact needed to determine whether 990000000 exists in
        # any nested price/promotion structure that the summary extractor
        # could otherwise miss.
        for response in live_records:
            body = response.get("body")
            if body is not None:
                save_json(
                    api_dir / f"get_pc_{response['index']:02d}.json",
                    body,
                )

        live_target_records = []
        live_price_hits = []
        for response in live_records:
            live_target_records.extend(response.get("target_records", []))
            live_price_hits.extend(response.get("historical_price_hits", []))

        # Also save the extracted evidence independently of the raw bodies so
        # it is easy to compare runs without parsing the large response again.
        save_json(api_dir / "get_pc_response_index.json", live_records)
        save_json(api_dir / "target_records.json", live_target_records)
        save_json(api_dir / "historical_price_hits.json", live_price_hits)

        print(f"Live final URL: {final_url}")
        print(f"get_pc responses: {len(live_records)}")
        print(f"Target records: {len(live_target_records)}")
        print(f"Live 990000000 hits: {len(live_price_hits)}")
        print(f"Raw get_pc directory: {api_dir}")

        for hit in live_price_hits:
            print(
                f"[FORENSICS] LIVE 990000000: {hit['path']} "
                f"({hit['key']})"
            )

        for record in live_target_records:
            if (
                record.get("model_id") in TARGET_MODEL_IDS
                or str(record.get("item_id")) == str(ITEM_ID)
            ):
                print(
                    "[FORENSICS] TARGET: "
                    f"path={record.get('path')} "
                    f"model={record.get('model_id')} "
                    f"name={record.get('name')} "
                    f"price={record.get('price')} "
                    f"price_before_discount={record.get('price_before_discount')} "
                    f"promotion_id={record.get('promotion_id')} "
                    f"promotion_type={record.get('promotion_type')}"
                )

        summary = {
            "timestamp": datetime.now().isoformat(),
            "target": {
                "item_id": ITEM_ID,
                "shop_id": SHOP_ID,
                "target_model_ids": sorted(TARGET_MODEL_IDS),
                "historical_price": HISTORICAL_PRICE,
            },
            "safety": {
                "production_code_modified": False,
                "settings_json_modified": False,
                "add_to_cart": False,
                "checkout": False,
                "payment": False,
                "place_order": False,
            },
            "historical_scan": {
                "files_checked": checked,
                "hit_count": len(historical_hits),
                "hits": historical_hits,
            },
            "live": {
                "final_url": final_url,
                "response_count": len(live_records),
                "target_records": live_target_records,
                "historical_price_hits": live_price_hits,
                "raw_response_files": [
                    str(path.relative_to(run_dir))
                    for path in sorted(api_dir.glob("get_pc_*.json"))
                ],
            },
        }
        save_json(run_dir / "forensics_summary.json", summary)

        print()
        print("========== RESULT ==========")
        if historical_hits:
            print("Historical 990000000 evidence: FOUND")
        else:
            print("Historical 990000000 evidence: NOT FOUND LOCALLY")
        if live_price_hits:
            print("Live 990000000 field: FOUND")
        else:
            print("Live 990000000 field: NOT PRESENT")
        print(f"Evidence directory: {run_dir}")
        print("Payment selected: NO")
        print("Place Order clicked: NO")
        print("=" * 72)

    finally:
        if browser_session is not None:
            # BrowserConnector.close_session expects the same owner key used
            # by open_session(), not the BrowserSession object itself.
            connector.close_session(OWNER)


if __name__ == "__main__":
    main()
