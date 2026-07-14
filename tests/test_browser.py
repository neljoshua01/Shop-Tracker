from services.browser_connector import BrowserConnector

connector = BrowserConnector()

page = connector.connect()

print("Connected!")

print(page.url)