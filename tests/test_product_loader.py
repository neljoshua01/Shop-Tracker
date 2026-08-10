from purchase.models.product_reference import ProductReference
from purchase.services.product_loader import ProductLoader


def main():

    loader = ProductLoader()

    reference = ProductReference(
        shop_id=448087759,
        item_id=42720981321,
        url="https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321",
    )

    product = loader.load(reference)

    print()
    print("========== PRODUCT ==========")
    print(product.product_name)
    print(product.item_id)
    print(product.shop_id)

    print()
    print("========== VARIATIONS ==========")
    print(len(product.available_variations))


if __name__ == "__main__":
    main()