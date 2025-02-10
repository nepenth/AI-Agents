import asyncio
import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables
load_dotenv()

# Configure logging to our main log file.
logging.basicConfig(
    filename='agent_program.log',
    level=logging.DEBUG,  # DEBUG for detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants and selectors
LOGIN_URL = "https://x.com/login"
USERNAME_SELECTOR = 'input[name="text"]'
PASSWORD_SELECTOR = 'input[name="password"]'
TWEET_SELECTOR = 'article[data-testid="tweet"], article[role="article"], article'
SCROLL_PIXELS = 1000
SCROLL_PAUSE = 5  # seconds
MAX_SCROLL_ITERATIONS = 100
MAX_NO_CHANGE_TRIES = 3

DATA_DIR = Path("data")
BOOKMARKS_FILE = DATA_DIR / "bookmarks_links.txt"
ARCHIVE_DIR = DATA_DIR / "archive_bookmarks"

async def scrape_x_bookmarks(headless: bool = True):
    # Ensure necessary directories exist.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    username = os.getenv("X_USERNAME")
    password = os.getenv("X_PASSWORD")
    bookmarks_url = os.getenv("X_BOOKMARKS_URL")

    if not (username and password and bookmarks_url):
        raise ValueError("X_USERNAME, X_PASSWORD, and X_BOOKMARKS_URL must be set in the environment.")

    async with async_playwright() as p:
        # Updated browser launch with container-friendly arguments
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',  # Overcome limited resource problems
                '--disable-gpu',  # Disable GPU hardware acceleration
                '--disable-software-rasterizer'  # Disable software rasterizer
            ]
        )
        page = await browser.new_page()

        # 1. Navigate to the login page and log in.
        logging.info("Navigating to login page...")
        await page.goto(LOGIN_URL, wait_until="networkidle")
        await page.wait_for_selector(USERNAME_SELECTOR, timeout=30000)
        await page.type(USERNAME_SELECTOR, username, delay=100)
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(3000)  # wait for transition

        await page.wait_for_selector(PASSWORD_SELECTOR, timeout=30000)
        await page.type(PASSWORD_SELECTOR, password, delay=100)
        await page.keyboard.press('Enter')

        try:
            # Attempt to wait for navigation after login.
            await page.wait_for_navigation(timeout=30000, wait_until="domcontentloaded")
        except Exception as nav_error:
            logging.error(f"Navigation after login did not complete: {nav_error}")

        current_url = page.url
        logging.debug(f"After login attempt, current URL: {current_url}")

        if LOGIN_URL in current_url:
            logging.error("Login appears to have failed. The page is still at the login URL.")
            raise Exception("Login failed: still on login page. Please check credentials or additional login steps.")

        logging.info("Logged in successfully.")

        # Attempt to dismiss any modal dialog (e.g., "Not now" prompt).
        try:
            await page.wait_for_selector('div[role="dialog"] button', timeout=5000)
            buttons = await page.query_selector_all('div[role="dialog"] button')
            for btn in buttons:
                btn_text = await btn.inner_text()
                if "Not now" in btn_text:
                    await btn.click()
                    logging.info("Dismissed 'Not now' dialog.")
                    break
        except Exception as e:
            logging.debug("No modal dialog to dismiss.")

        # 2. Navigate to the bookmarks page.
        logging.info("Navigating to the bookmarks page...")
        try:
            await page.goto(bookmarks_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as goto_error:
            logging.error(f"Error navigating to bookmarks page: {goto_error}")
            raise

        # Instead of waiting for networkidle, wait a fixed delay.
        await page.wait_for_timeout(10000)  # wait 10 seconds for dynamic content to load

        current_url = page.url
        logging.debug(f"After navigating to bookmarks, URL is: {current_url}")

        if LOGIN_URL in current_url:
            logging.error("Navigation to bookmarks page failed, still at login page.")
            raise Exception("Navigation to bookmarks page failed.")

        # Log page content length for debugging.
        content = await page.content()
        logging.debug(f"Bookmarks page content length: {len(content)}")

        # Try finding tweet elements; if none are found, log a warning.
        try:
            tweet_elements = await page.query_selector_all(TWEET_SELECTOR)
            if tweet_elements:
                logging.info(f"Found {len(tweet_elements)} tweet/article elements on the bookmarks page.")
            else:
                logging.warning("No tweet/article elements found on the bookmarks page.")
        except Exception as e:
            logging.error(f"Error querying tweet elements: {e}")

        # 3. Scroll to load all bookmarks.
        logging.info("Starting scroll to load bookmarks...")
        previous_height = await page.evaluate("() => document.body.scrollHeight")
        no_change_tries = 0
        all_bookmarks = set()

        for i in range(1, MAX_SCROLL_ITERATIONS + 1):
            links = await page.query_selector_all(f'{TWEET_SELECTOR} a[href*="/status/"]')
            current_links = []
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    current_links.append(href)
            for link in current_links:
                all_bookmarks.add(link)

            logging.info(f"Scroll iteration #{i}. Found so far: {len(all_bookmarks)} unique links.")

            await page.evaluate(f"window.scrollBy(0, {SCROLL_PIXELS});")
            await asyncio.sleep(SCROLL_PAUSE)

            current_height = await page.evaluate("() => document.body.scrollHeight")
            logging.info(f"Previous height: {previous_height}, Current height: {current_height}")

            if current_height == previous_height:
                no_change_tries += 1
                logging.info(f"No new content detected #{no_change_tries} time(s).")
                if no_change_tries >= MAX_NO_CHANGE_TRIES:
                    logging.info("No new content after multiple attempts, ending scroll.")
                    break
            else:
                no_change_tries = 0
                previous_height = current_height

        # Filter the bookmarks to remove unwanted links.
        bookmarks = [link for link in all_bookmarks if isinstance(link, str)
                     and "/analytics" not in link and "/photo/" not in link]
        logging.info(f"Extracted {len(bookmarks)} unique bookmark links.")

        # 4. Archive the existing bookmarks file if it exists.
        if BOOKMARKS_FILE.exists():
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            archive_file = ARCHIVE_DIR / f"bookmarks_links_{timestamp}.txt"
            BOOKMARKS_FILE.rename(archive_file)
            logging.info(f"Existing bookmarks file archived as: {archive_file}")

        # 5. Write the new bookmarks file.
        with BOOKMARKS_FILE.open('w', encoding='utf8') as f:
            f.write("\n".join(bookmarks))
        logging.info(f"Saved new bookmarks to {BOOKMARKS_FILE}")
        print(f"Saved {len(bookmarks)} bookmarks to {BOOKMARKS_FILE}")

        await browser.close()
        logging.info("Browser closed.")

if __name__ == "__main__":
    try:
        asyncio.run(scrape_x_bookmarks())
    except Exception as e:
        logging.error(f"An error occurred while updating bookmarks: {e}")
        print("An error occurred while updating bookmarks. Proceeding with existing bookmarks.")
