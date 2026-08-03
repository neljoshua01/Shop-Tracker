from execution.browser.browser_connector import BrowserConnector


class DeveloperInspector:

    def __init__(self):
        self.connector = BrowserConnector()
        self.page = self.connector.connect()

    def inspect_page(self):

        print("\n" + "=" * 70)
        print("PAGE INFORMATION")
        print("=" * 70)

        print(f"Title : {self.page.title()}")
        print(f"URL   : {self.page.url}")

        print("\n")

        headings = self.page.locator("h1, h2, h3").all()

        print("=" * 70)
        print("HEADINGS")
        print("=" * 70)

        for heading in headings:
            try:
                print(heading.inner_text())
            except:
                pass

        print("\n")

        sections = self.page.locator("section").all()

        print("=" * 70)
        print(f"FOUND {len(sections)} SECTIONS")
        print("=" * 70)

        for index, section in enumerate(sections, start=1):

            try:
                text = section.inner_text().strip()

                if len(text) > 300:
                    text = text[:300] + "..."

                print(f"\nSECTION {index}")
                print("-" * 40)
                print(text)

            except:
                continue