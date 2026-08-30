import asyncio
from playwright.async_api import async_playwright
import os

ARTIFACTS_DIR = r"C:\Users\saleh\.gemini\antigravity-ide\brain\9763cabc-3bfd-42e9-9e71-aea76446f9fa"

async def capture_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. Login as Saleh
        print("1. Logging in as Saleh...")
        await page.goto("http://localhost:5173/login")
        await page.wait_for_selector("input[type='email']")
        await page.fill("input[type='email']", "saleh@alphapromena.com")
        await page.fill("input[type='password']", "Sales123!")
        await page.click("button[type='submit']")
        await page.wait_for_url("http://localhost:5173/**")
        await asyncio.sleep(2)

        # 2. Contacts Page showing STC Bank contacts attempt history
        print("2. Navigating to Contacts Page...")
        await page.goto("http://localhost:5173/contacts")
        await page.wait_for_selector("table")
        await asyncio.sleep(2)

        # Search for "stc Bank" or "Ayman Ali"
        search_input = page.locator("input[placeholder*='Search'], input[type='search'], input[placeholder*='بحث']").first
        if await search_input.count() > 0:
            await search_input.fill("stc Bank")
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)

        screenshot_path1 = os.path.join(ARTIFACTS_DIR, "phase10_stc_bank_attempts.png")
        await page.screenshot(path=screenshot_path1, full_page=False)
        print(f"Saved: {screenshot_path1}")

        # Clear search to show general contacts
        if await search_input.count() > 0:
            await search_input.fill("")
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)

        screenshot_path2 = os.path.join(ARTIFACTS_DIR, "phase10_saleh_contacts_attempts.png")
        await page.screenshot(path=screenshot_path2, full_page=False)
        print(f"Saved: {screenshot_path2}")

        # 3. Login as Aseel
        print("3. Logging in as Aseel...")
        await page.goto("http://localhost:5173/login")
        await page.wait_for_selector("input[type='email']")
        await page.fill("input[type='email']", "aseel@alphapromena.com")
        await page.fill("input[type='password']", "Sales123!")
        await page.click("button[type='submit']")
        await page.wait_for_url("http://localhost:5173/**")
        await asyncio.sleep(2)

        # Navigate to Lead Pool & Distribution Page
        print("4. Navigating to Lead Distribution...")
        await page.goto("http://localhost:5173/leads/pool")
        await page.wait_for_selector("body")
        await asyncio.sleep(2)

        screenshot_path3 = os.path.join(ARTIFACTS_DIR, "phase10_aseel_lead_pool.png")
        await page.screenshot(path=screenshot_path3, full_page=False)
        print(f"Saved: {screenshot_path3}")

        # Navigate to Distribution tab or distribution status page
        await page.goto("http://localhost:5173/leads/distribution")
        await asyncio.sleep(2)
        screenshot_path4 = os.path.join(ARTIFACTS_DIR, "phase10_aseel_distribution_management.png")
        await page.screenshot(path=screenshot_path4, full_page=False)
        print(f"Saved: {screenshot_path4}")

        await browser.close()
        print("[OK] All screenshots captured successfully!")

if __name__ == "__main__":
    asyncio.run(capture_screenshots())
