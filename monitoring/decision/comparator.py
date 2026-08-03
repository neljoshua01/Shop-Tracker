from monitoring.models.event import Event


class ProductComparator:

    def compare(self, old_product, new_product):

        events = []

        if old_product.current_price != new_product.current_price:

            events.append(
                Event(
                    event_type="PRICE_CHANGED",
                    field="current_price",
                    old_value=old_product.current_price,
                    new_value=new_product.current_price
                )
            )

        if old_product.stock != new_product.stock:

            events.append(
                Event(
                    event_type="STOCK_CHANGED",
                    field="stock",
                    old_value=old_product.stock,
                    new_value=new_product.stock
                )
            )

        return events