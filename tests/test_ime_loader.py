from purchase.services.ime_loader import IMELoader


def main():

    loader = IMELoader()

    product = loader.load(
        "https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321?is_from_login=true"
    )

    if product is None:

        print("No product returned.")
        return

    print()
    print("========== PRODUCT ==========")
    print("Name      :", product.product_name)
    print("Shop      :", product.shop_name)
    print("Item ID   :", product.item_id)
    print("Shop ID   :", product.shop_id)
    print("Currency  :", product.currency)
    print("Image     :", product.image)

    print()
    print("========== VARIATIONS ==========")

    for variation in product.available_variations:

        print("------------------------------")
        print("Name       :", variation.name)
        print("Model ID   :", variation.model_id)
        print("Price      :", variation.price)
        print("Old Price  :", variation.price_before_discount)
        print("Stock      :", variation.has_stock)


if __name__ == "__main__":
    main()