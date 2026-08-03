from monitoring.api.shopee_adapter import ShopeeAdapter

adapter = ShopeeAdapter()

product = adapter.read_product()

print(product)