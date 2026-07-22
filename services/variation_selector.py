class VariationSelector:

    async def prepare(self, page):

        headings = page.locator("text=/Case Finish|Size/")

        count = await headings.count()

        groups = []

        for i in range(count):

            heading = headings.nth(i)

            title = await heading.inner_text()

            group = {
                "name": title,
                "options": []
            }

            parent = heading.locator("xpath=..")

            buttons = parent.locator("button")

            button_count = await buttons.count()

            for j in range(button_count):

                button = buttons.nth(j)

                text = (await button.inner_text()).strip()

                disabled = (
                    await button.get_attribute("aria-disabled")
                ) == "true"

                group["options"].append({
                    "text": text,
                    "disabled": disabled,
                    "button": button
                })

            groups.append(group)

        return groups


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

            for option in group["options"]:

                if option["disabled"]:
                    continue

                await option["button"].click()

                await page.wait_for_timeout(500)

                print(f"✓ {option['text']}")

                break

        print()
        print("Variation selection complete.")