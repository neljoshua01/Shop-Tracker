from execution.browser.browser_action import BrowserActions

class VariationSelector:

    def select(
        self,
        session,
    ):

        print("[VariationSelector] Selecting variations...")

        browser = BrowserActions(
            session.browser_session,
        )

        browser.wait_for_selector(
            "section h2",
        )

        sections = self._get_sections(browser)

        self._select_requested_variations(
            browser,
            sections,
            session.variation.options,
        )

    def _select_requested_variations(
        self,
        browser,
        sections,
        requested_options,
    ):

        print()
        print("========== SELECTING VARIATIONS ==========")

        for title, value in requested_options.items():

            print(
                f"[VariationSelector] {title} -> {value}"
            )

            section = next(
                (
                    section
                    for section in sections
                    if section["title"].strip().lower()
                    == title.strip().lower()
                ),
                None,
            )

            if section is None:

                raise RuntimeError(
                    f"Variation section not found: {title}"
                )

            button = next(
                (
                    button
                    for button in section["buttons"]
                    if button["value"].strip().lower()
                    == value.strip().lower()
                ),
                None,
            )

            if button is None:

                raise RuntimeError(
                    f"Variation option not found: "
                    f"{title} -> {value}"
                )

            browser.click(
                button["locator"]
            )

            browser.wait_for_timeout(300)

            print(
                f"[VariationSelector] Selected: "
                f"{title} -> {value}"
            )

    def _print_sections(
        self,
        sections,
    ):

        print()
        print("========== VARIATION SECTIONS ==========")

        for section in sections:

            print(section["title"])

            for value in section["values"]:
                print(f"   - {value}")

            print()

    def _get_sections(
        self,
        browser,
    ):

        sections = []

        locator = browser.find_all("section")

        count = browser.count(locator)

        print(
            f"[VariationSelector] Sections found: {count}"
        )

        for i in range(count):

            print(f"\nChecking section {i}")

            section = locator.nth(i)

            titles = browser.find_all(
                "h2",
                parent=section,
            )

            title_count = browser.count(titles)

            print(f"h2 count: {title_count}")

            if title_count == 0:
                continue

            title = browser.text(
                titles.first,
            )

            print(f"Title: {title}")

            buttons = browser.find_all(
                "button",
                parent=section,
            )

            button_count = browser.count(buttons)

            print(f"Buttons: {button_count}")

            section_buttons = []

            for j in range(button_count):

                button = buttons.nth(j)

                value = browser.attribute(
                    button,
                    "aria-label",
                )

                print(
                    f"Button {j}: {value}"
                )

                if not value:
                    continue

                value = value.strip()

                section_buttons.append(
                    {
                        "value": value,
                        "locator": button,
                    }
                )

            if not section_buttons:
                continue

            sections.append(
                {
                    "title": title,
                    "buttons": section_buttons,
                }
            )

        return sections