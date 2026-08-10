import json

from purchase.parser.shopee_api_parser import ShopeeAPIParser


def main():

    with open(
        "tests/get_pc.json",
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    parser = ShopeeAPIParser()

    product = parser.parse(data)

    print("\n========== PRODUCT ==========")

    print(f"Name      : {product.product_name}")
    print(f"Shop      : {product.shop_name}")
    print(f"Item ID   : {product.item_id}")
    print(f"Shop ID   : {product.shop_id}")
    print(f"Currency  : {product.currency}")
    print(f"Image     : {product.image}")

    print("\n========== VARIATIONS ==========")

    for variation in product.available_variations:

        print("------------------------------")

        print(f"Name       : {variation.name}")
        print(f"Options    : {variation.options}")
        print(f"Model ID   : {variation.model_id}")
        print(f"Price      : {variation.price}")
        print(f"Old Price  : {variation.price_before_discount}")
        print(f"Stock      : {variation.has_stock}")
        print(f"Tier Index : {variation.tier_index}")
        print(f"Image      : {variation.sku_image}")


if __name__ == "__main__":
    main()