import re
from playwright.sync_api import sync_playwright, Page, expect

def verify_theme_toggle(page: Page):
    """
    This test verifies that the theme toggle buttons work correctly.
    """
    # 1. Arrange: Go to the application homepage.
    page.goto("http://localhost:3000/")

    # Wait for the header to be visible
    header = page.locator("header")
    expect(header).to_be_visible()

    # 2. Act: Find the dark theme button and click it.
    dark_mode_button = page.get_by_label("Switch to dark theme")
    expect(dark_mode_button).to_be_visible()
    dark_mode_button.click()

    # 3. Assert: Check that the 'dark' class is applied to the html element
    html_element = page.locator("html")
    expect(html_element).to_have_class(re.compile(r"dark"))

    # 4. Screenshot: Capture the dark mode for visual verification.
    page.screenshot(path="jules-scratch/verification/verification-dark.png")

    # 5. Act: Find the light theme button and click it.
    light_mode_button = page.get_by_label("Switch to light theme")
    expect(light_mode_button).to_be_visible()
    light_mode_button.click()

    # 6. Assert: Check that the 'dark' class is removed from the html element
    expect(html_element).not_to_have_class(re.compile(r"dark"))

    # 7. Screenshot: Capture the light mode for visual verification.
    page.screenshot(path="jules-scratch/verification/verification-light.png")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        verify_theme_toggle(page)
        browser.close()

if __name__ == "__main__":
    main()
