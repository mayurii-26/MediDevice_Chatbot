from playwright.sync_api import sync_playwright

url = "https://www.philips.co.in/healthcare/product/HC989803205831/single-patient-pediatric-adult-spo2-clip-sensor-pulse-oximetry-supplies"

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    print("\nPAGE TITLE:")
    print(page.title())

    try:
        print("\nH1:")
        print(page.locator("h1").first.inner_text())
    except:
        print("No H1 Found")

    body_text = page.locator("body").inner_text()

    print("\nBODY SAMPLE:\n")
    print(body_text[:5000])

    input("\nPress Enter to close...")

    browser.close()