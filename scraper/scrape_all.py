import json

from scrape_product import scrape_product
from urls import PRODUCT_URLS

all_products = []

for url in PRODUCT_URLS:
    print("Total URLs:", len(PRODUCT_URLS))
    print(f"\nScraping: {url}")

    try:

        product = scrape_product(url)

        all_products.append(product)

        print("Success")

    except Exception as e:

        print("Failed:", e)

with open(
    "../data/products.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        all_products,
        f,
        indent=4,
        ensure_ascii=False
    )

print("\nProducts saved successfully")