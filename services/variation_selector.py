class VariationSelector:

    async def prepare(self, page):

        print()
        print("============================================================")
        print("VARIATION SELECTOR")
        print("============================================================")

        panel = await self.find_purchase_panel(page)

        if panel is None:
            return []

        #
        # Child 3 is currently the variation container.
        #
        wrapper = panel.locator(":scope > *").nth(3)

        sections = wrapper.locator("section")

        section_count = await sections.count()

        print()
        print("========== VARIATION SECTIONS ==========")
        print(f"Sections: {section_count}")

        groups = []

        for i in range(section_count):

            section = sections.nth(i)

            heading = section.locator("h2")

            if await heading.count() == 0:
                continue

            title = (await heading.inner_text()).strip()

            print()
            print(f"[{title}]")

            #
            # Ignore Quantity.
            #
            if title.lower() == "quantity":

                print("Skipping Quantity")

                continue

            buttons = section.locator("button")

            button_count = await buttons.count()

            print(f"Buttons: {button_count}")

            #
            # Skip non-variation sections.
            # 
            if button_count == 0:
                continue

            group = {
                "name": title,
                "options": []
            }

            for j in range(button_count):

                button = buttons.nth(j)

                text = (await button.inner_text()).strip()

                disabled = (
                    await button.get_attribute("aria-disabled")
                ) == "true"

                print(f"   - {text}")

                group["options"].append({
                    "text": text,
                    "disabled": disabled,
                    "button": button
                })

            groups.append(group)

        return groups

    async def choose_option(self, group, page):

        for option in group["options"]:

            if option["disabled"]:
                continue

            await option["button"].click()

            await page.wait_for_timeout(500)

            print(f"✓ {option['text']}")

            return True

        print(f"No available option for [{group['name']}]")

        return False
        
    async def select_variations(self, page):

        print()
        print("============================================================")
        print("VARIATION SELECTOR")
        print("============================================================")

        groups = await self.prepare(page)

        for index in range(len(groups)):

            groups = await self.prepare(page)

            group = groups[index]

            print()
            print(f"Selecting [{group['name']}]")

            await self.choose_option(group, page)

        print()
        print("Variation selection complete.")

    async def find_purchase_panel(self, page):

        print()
        print("========== FINDING PURCHASE PANEL ==========")

        #
        # Reuse the same purchase button logic already proven
        #
        purchase_button = page.locator(
            "button:has-text('Buy Now'), button:has-text('Buy With Voucher')"
        ).first

        if await purchase_button.count() == 0:
            print("❌ Purchase button not found.")
            return None

        #
        # Walk upward through ancestors.
        #
        current = purchase_button

        for level in range(10):

            current = current.locator("xpath=..")

            try:
                text = await current.inner_text()
            except:
                continue

            has_quantity = "Quantity" in text

            has_buy_button = (
                "Buy Now" in text
                or
                "Buy With Voucher" in text
            )

            print(
                f"Ancestor {level} "
                f"(Quantity={has_quantity}, Buy={has_buy_button})"
            )

            if has_quantity and has_buy_button:

                print(f"✓ Purchase panel found at ancestor {level}")

                return current
            
        print("❌ Purchase panel not found.")
        return None