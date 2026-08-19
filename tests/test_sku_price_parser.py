import json

from purchase.parser.sku_price_parser import SkuPriceParser


def main():

    path = (
        "api_logs/2026-08-08_13-47-29/"
        "responses/get_pc.json"
    )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:

        data = json.load(f)

    parser = SkuPriceParser()

    result = parser.parse(
        data,
        model_id=208721552326,
    )

    if result is None:

        print("FAILED: SKU not found.")
        return

    print()
    print("========== SKU PRICE STATE ==========")

    print(
        f"Item ID: "
        f"{result.item_id}"
    )

    print(
        f"Model ID: "
        f"{result.model_id}"
    )

    print(
        f"Name: "
        f"{result.name}"
    )

    print(
        f"Price: "
        f"{result.price}"
    )

    print(
        f"Price Before Discount: "
        f"{result.price_before_discount}"
    )

    print(
        f"Promotion ID: "
        f"{result.promotion_id}"
    )

    print(
        f"Promotion Types: "
        f"{result.promotion_types}"
    )

    print(
        f"Deep Discount: "
        f"{result.deep_discount}"
    )

    print(
        f"Promotion Price: "
        f"{result.promotion_price}"
    )

    print(
        f"Promotion Event Status: "
        f"{result.promotion_event_status}"
    )

    print(
        f"Seconds Until Start: "
        f"{result.promotion_seconds_until_start}"
    )

    print(
        f"Seconds Until End: "
        f"{result.promotion_seconds_until_end}"
    )

    print(
        f"Promotion Skin: "
        f"{result.promotion_skin}"
    )

    print(
        f"Promotion Reminder Event: "
        f"{result.promotion_reminder_event}"
    )

    print(
        f"Promotion Is LPP: "
        f"{result.promotion_is_lpp}"
    )


if __name__ == "__main__":
    main()