import json
import requests
from bs4 import BeautifulSoup

DEVICE_FILE = "../data/device_urls.json"
OUTPUT_FILE = "../data/Anaesthesia/products.json"


def scrape_philips(url):

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=20
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        title = soup.find("h1")

        product_name = (
            title.text.strip()
            if title
            else "Unknown Product"
        )

        description = ""

        meta_desc = soup.find(
            "meta",
            attrs={
                "name": "description"
            }
        )

        if meta_desc:
            description = meta_desc.get(
                "content",
                ""
            )

        return {
            "product_name": product_name,
            "description": description,
            "url": url
        }

    except Exception as e:

        print(f"Error scraping {url}")
        print(e)

        return None


def main():

    with open(
        DEVICE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        devices = json.load(f)

    results = []

    for device in devices["Anaesthesia"]:

        url = device["url"]

        data = scrape_philips(url)

        if data:

            data["category"] = device["category"]
            data["device_type"] = device["device_type"]

            results.append(data)

            print(
                "Scraped:",
                data["product_name"]
            )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(
        "\nSaved:",
        len(results),
        "products"
    )


if __name__ == "__main__":
    main()