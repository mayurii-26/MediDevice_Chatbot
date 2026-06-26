from scraper.scrape_product import scrape_product

url = "https://www.philips.co.in/healthcare/product/HC989803205831/single-patient-pediatric-adult-spo2-clip-sensor-pulse-oximetry-supplies"

product = scrape_product(url)

print(product)