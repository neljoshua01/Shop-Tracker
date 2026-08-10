from purchase.models.product_reference import ProductReference
from purchase.services.product_loader import ProductLoader
from purchase.services.selection_resolver import SelectionResolver


def main():

    loader = ProductLoader()

    resolver = SelectionResolver()

    reference = ProductReference(
        shop_id=448087759,
        item_id=42720981321,
        url="https://shopee.ph/Apple-Watch-SE-3-GPS-Aluminium-Case-Sport-Band-i.448087759.42720981321",
    )

    product = loader.load(reference)

    variation = resolver.resolve(
        product,
        {
            "Color": "Midnight",
            "Watch Size": "44MM M L",
        },
    )

    print()
    print("========== MATCH ==========")

    if variation is None:
        print("No variation found.")
        return

    print(variation.model_id)
    print(variation.name)
    print(variation.price)


if __name__ == "__main__":
    main()