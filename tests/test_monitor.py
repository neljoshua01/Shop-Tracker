from execution.browser.browser_connector import BrowserConnector
from services.page_parser import PageParser
from monitoring.services.product_monitor import ProductMonitor

browser = BrowserConnector()

page = browser.connect()

parser = PageParser(page)

monitor = ProductMonitor(browser, parser)

monitor.start(interval=2)