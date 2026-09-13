from io import StringIO
from contextlib import redirect_stdout
import unittest

from purchase.execution.variation_selector import VariationSelector


class FakeBrowser:
    def __init__(self):
        self.clicked = []

    def force_click(self, locator):
        self.clicked.append(locator)

    def wait_for_timeout(self, milliseconds):
        pass


class VariationSelectorTests(unittest.TestCase):

    def setUp(self):
        self.selector = VariationSelector()

    @staticmethod
    def section(title, value="256GB", locator=None):
        return {
            "title": title,
            "buttons": [
                {
                    "value": value,
                    "locator": locator or f"{title}:{value}",
                }
            ],
            "locator": locator or title,
        }

    def test_storage_request_resolves_to_capacity(self):
        sections = [self.section("Capacity")]

        resolved, title = self.selector._resolve_section(
            sections,
            "Storage",
        )

        self.assertIsNotNone(resolved)
        self.assertEqual(title, "Capacity")

    def test_capacity_request_resolves_to_storage(self):
        sections = [self.section("Storage")]

        resolved, title = self.selector._resolve_section(
            sections,
            "Capacity",
        )

        self.assertIsNotNone(resolved)
        self.assertEqual(title, "Storage")

    def test_exact_match_wins_over_alias(self):
        sections = [
            self.section("Capacity", locator="capacity"),
            self.section("Storage", locator="storage"),
        ]

        resolved, title = self.selector._resolve_section(
            sections,
            "Storage",
        )

        self.assertEqual(title, "Storage")
        self.assertEqual(resolved["locator"], "storage")

    def test_invalid_variation_section_fails_safely(self):
        sections = [self.section("Color", value="Deep Blue")]

        resolved, title = self.selector._resolve_section(
            sections,
            "Storage",
        )

        self.assertIsNone(resolved)
        self.assertEqual(title, "Storage")

    def test_storage_alias_selects_live_capacity_option(self):
        browser = FakeBrowser()
        sections = [self.section("Capacity", locator="capacity:256GB")]

        output = StringIO()
        with redirect_stdout(output):
            self.selector._select_requested_variations(
                browser,
                sections,
                {"Storage": "256GB"},
            )

        self.assertEqual(browser.clicked, ["capacity:256GB"])
        self.assertIn(
            "Resolved variation section: Storage -> Capacity",
            output.getvalue(),
        )
        self.assertIn(
            "Selected: Capacity -> 256GB",
            output.getvalue(),
        )

    def test_capacity_alias_selects_live_storage_option(self):
        browser = FakeBrowser()
        sections = [self.section("Storage", locator="storage:256GB")]

        output = StringIO()
        with redirect_stdout(output):
            self.selector._select_requested_variations(
                browser,
                sections,
                {"Capacity": "256GB"},
            )

        self.assertEqual(browser.clicked, ["storage:256GB"])
        self.assertIn(
            "Resolved variation section: Capacity -> Storage",
            output.getvalue(),
        )
        self.assertIn(
            "Selected: Storage -> 256GB",
            output.getvalue(),
        )

    def test_missing_option_still_fails_safely_after_alias_resolution(self):
        browser = FakeBrowser()
        sections = [self.section("Capacity", value="512GB")]

        with self.assertRaisesRegex(
            RuntimeError,
            r"Variation option not found: Storage -> 256GB",
        ):
            self.selector._select_requested_variations(
                browser,
                sections,
                {"Storage": "256GB"},
            )

        self.assertEqual(browser.clicked, [])


if __name__ == "__main__":
    unittest.main()
