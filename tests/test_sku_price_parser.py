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


if __name__ == "__main__":
    main()