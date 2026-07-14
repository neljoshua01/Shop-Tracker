from services.browser_connector import BrowserConnector

connector = BrowserConnector()
page = connector.connect()

sections = page.locator("section").all()

print("\nFOUND", len(sections), "SECTIONS")
print("=" * 70)

for i, section in enumerate(sections):

    try:
        text = section.inner_text().strip()

        if not text:
            continue

        print(f"\nSECTION {i+1}")
        print("-" * 70)
        print(text[:800])

    except Exception:
        pass