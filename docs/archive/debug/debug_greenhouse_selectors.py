"""
Debug Greenhouse CSS selectors to find the right one for job descriptions.

This script will:
1. Fetch a test Stripe job using the scraper
2. Save the HTML content
3. Test various CSS selectors to find which one extracts the description
4. Identify the right selector to update
"""

import asyncio
import json
from playwright.async_api import async_playwright

async def test_greenhouse_selectors():
    """Test different CSS selectors on a real Greenhouse page"""

    # Use a known Stripe job URL that we know should have content
    test_url = "https://stripe.com/jobs/listing/account-executive-startups-india/7294247"

    print(f"Testing Greenhouse job URL: {test_url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(test_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(1)  # Wait for JS rendering

            # Get page title
            title = await page.title()
            print(f"Page title: {title}\n")

            # Test various selectors
            selectors_to_test = [
                ('div.ArticleMarkdown', 'ArticleMarkdown'),
                ('div[class*="ArticleMarkdown"]', 'ArticleMarkdown wildcard'),
                ('div[class*="JobPostingDynamics"]', 'JobPostingDynamics'),
                ('main', 'main tag'),
                ('article', 'article tag'),
                ('div[role="main"]', 'div with role=main'),
                ('div[class*="Content"]', 'Content wildcard'),
                ('section[class*="job"]', 'job section'),
                # Try finding by text content patterns
                ('body', 'entire body'),
            ]

            print("Testing CSS selectors:\n")
            for selector, label in selectors_to_test:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for i, elem in enumerate(elements[:1]):  # Just test first element
                            text = await elem.text_content()
                            text_len = len(text.strip()) if text else 0

                            if text_len > 100:
                                print(f"[SUCCESS] {label}")
                                print(f"  Selector: {selector}")
                                print(f"  Text length: {text_len} chars")
                                print(f"  Preview: {text[:150]}...\n")
                            else:
                                print(f"[SMALL]   {label} ({text_len} chars)")
                    else:
                        print(f"[EMPTY]   {label} (no elements found)")
                except Exception as e:
                    print(f"[ERROR]   {label}: {str(e)[:50]}")

            # Also check what classes are on major containers
            print("\n\nAnalyzing page structure:")
            main_divs = await page.query_selector_all('div[class*="Job"], div[class*="Article"], main, article')
            print(f"Found {len(main_divs)} major containers")

            for i, div in enumerate(main_divs[:5]):
                class_attr = await div.get_attribute('class')
                text_length = len(await div.text_content())
                print(f"  {i+1}. class='{class_attr}' (text: {text_length} chars)")

        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(test_greenhouse_selectors())
