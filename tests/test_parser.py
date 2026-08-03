from execution.browser.browser_connector import BrowserConnector
from services.page_parser import PageParser

connector = BrowserConnector()
page = connector.connect()

parser = PageParser(page)

product = parser.parse()

print("\nParsed Product")
print("=" * 40)

print(f"Name           : {product.name}")
print(f"Current Price  : {product.current_price}")
print(f"Original Price : {product.original_price}")
print(f"Discount       : {product.discount}")
print(f"Rating         : {product.rating}")
print(f"Sold           : {product.sold}")
print(f"Stock          : {product.stock}")