import time
from playwright.sync_api import sync_playwright, Page, expect

def verify_dashboard_theme(page: Page):
    """
    This test verifies that the glass morphism theme is applied to the Dashboard page.
    """
    # 1. Arrange: Go to the Dashboard page.
    # The dev server is running on port 5173.
    time.sleep(5) # Wait for the dev server to be ready
    page.goto("http://localhost:5173")

    # 2. Act: Wait for the main heading to be visible.
    # This ensures the page has loaded before we take the screenshot.
    dashboard_heading = page.get_by_role("heading", name="Dashboard")
    expect(dashboard_heading).to_be_visible()

    # 3. Screenshot: Capture the final result for visual verification.
    page.screenshot(path="jules-scratch/verification/verification.png")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        verify_dashboard_theme(page)
        browser.close()

if __name__ == "__main__":
    main()
