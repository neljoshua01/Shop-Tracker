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

        self._prepare_quantity(
            browser,
            sections,
            session.request.quantity,
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

            # Shopee can leave a transient promotional layer over PDP
            # controls. These locators are already scoped to the exact
            # requested variation button, so force is safe here.
            browser.force_click(
                button["locator"]
            )

            browser.wait_for_timeout(300)

            print(
                f"[VariationSelector] Selected: "
                f"{title} -> {value}"
            )

    def _prepare_quantity(
        self,
        browser,
        sections,
        requested_quantity,
    ):
        """Set and verify the PDP quantity before Add To Cart."""

        try:
            requested_quantity = int(
                requested_quantity
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Purchase quantity must be an integer."
            ) from exc

        if requested_quantity < 1:
            raise ValueError(
                "Purchase quantity must be at least 1."
            )

        print(
            "[VariationSelector] "
            f"Preparing requested quantity: "
            f"{requested_quantity}"
        )

        quantity_section = next(
            (
                section
                for section in sections
                if section["title"].strip().lower()
                == "quantity"
            ),
            None,
        )

        if quantity_section is None:
            raise RuntimeError(
                "PDP Quantity section not found."
            )

        section = quantity_section["locator"]

        quantity_inputs = browser.find_all(
            "input[aria-label='Quantity']",
            parent=section,
        )

        if browser.count(quantity_inputs) == 0:
            quantity_inputs = browser.find_all(
                "input",
                parent=section,
            )

        if browser.count(quantity_inputs) == 0:
            raise RuntimeError(
                "PDP quantity input not found."
            )

        quantity_input = browser.first(
            quantity_inputs
        )

        current_value = browser.attribute(
            quantity_input,
            "value",
        )

        try:
            current_quantity = int(
                current_value
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "PDP quantity could not be read."
            ) from exc

        print(
            "[VariationSelector] "
            f"PDP quantity before adjustment: "
            f"{current_quantity}"
        )

        increase = browser.find_all(
            "button[aria-label='Increase']",
            parent=section,
        )

        decrease = browser.find_all(
            "button[aria-label='Decrease']",
            parent=section,
        )

        increase_count = browser.count(increase)
        decrease_count = browser.count(decrease)

        if current_quantity < requested_quantity:

            if increase_count == 0:
                raise RuntimeError(
                    "PDP Increase quantity control not found."
                )

            increase_button = browser.first(
                increase
            )

            for _ in range(
                requested_quantity - current_quantity
            ):
                print(
                    "[VariationSelector] "
                    "Increasing quantity..."
                )
                browser.force_click(
                    increase_button
                )
                browser.wait_for_timeout(300)

        elif current_quantity > requested_quantity:

            if decrease_count == 0:
                raise RuntimeError(
                    "PDP Decrease quantity control not found."
                )

            decrease_button = browser.first(
                decrease
            )

            for _ in range(
                current_quantity - requested_quantity
            ):
                print(
                    "[VariationSelector] "
                    "Decreasing quantity..."
                )
                browser.force_click(
                    decrease_button
                )
                browser.wait_for_timeout(300)

        else:
            print(
                "[VariationSelector] "
                "Requested quantity already selected."
            )

        final_value = browser.attribute(
            quantity_input,
            "value",
        )

        try:
            final_quantity = int(
                final_value
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "PDP quantity could not be verified."
            ) from exc

        print(
            "[VariationSelector] "
            f"PDP quantity after adjustment: "
            f"{final_quantity}"
        )

        if final_quantity != requested_quantity:
            raise RuntimeError(
                "PDP quantity does not match requested quantity: "
                f"expected {requested_quantity}, "
                f"got {final_quantity}."
            )

        print(
            "[VariationSelector] "
            f"PDP quantity verified: {final_quantity}"
        )

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

            section = locator.nth(i)

            titles = browser.find_all(
                "h2",
                parent=section,
            )

            title_count = browser.count(titles)

            if title_count == 0:
                continue

            title = browser.text(
                titles.first,
            )

            buttons = browser.find_all(
                "button",
                parent=section,
            )

            button_count = browser.count(buttons)

            section_buttons = []

            for j in range(button_count):

                button = buttons.nth(j)

                value = browser.attribute(
                    button,
                    "aria-label",
                )

                if not value:
                    continue

                section_buttons.append(
                    {
                        "value": value.strip(),
                        "locator": button,
                    }
                )

            if not section_buttons:
                continue

            sections.append(
                {
                    "title": title,
                    "buttons": section_buttons,
                    "locator": section,
                }
            )

        return sections
