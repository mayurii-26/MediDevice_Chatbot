from playwright.sync_api import sync_playwright


def scrape_product(url):

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        product_name = ""

        try:
            product_name = page.locator("h1").first.inner_text()
        except:
            pass

        text = page.locator("body").inner_text()

        browser.close()

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    product = {
        "product_name": product_name,
        "category": "",
        "description": "",
        "features": [],
        "specifications": {},
        "documentation": []
    }

    # -----------------------------
    # CATEGORY
    # -----------------------------

    try:

        title_index = lines.index(product_name)

        for i in range(title_index + 1, min(title_index + 10, len(lines))):

            if (
                len(lines[i]) > 3
                and lines[i] != product_name
                and not lines[i].startswith("+")
                and lines[i] not in ["Watch video", "New"]
            ):
                product["category"] = lines[i]
                break

    except:
        pass

    # -----------------------------
    # DESCRIPTION
    # -----------------------------

    try:

        features_index = lines.index("Features")

        for line in lines[:features_index]:

            if len(line) > 100:
                product["description"] = line
                break

    except:

        for line in lines:

            if len(line) > 100:
                product["description"] = line
                break

    # -----------------------------
    # FEATURES
    # -----------------------------

    try:

        features_index = lines.index("Features")

        if "Specifications" in lines:
            end_index = lines.index("Specifications")
        elif "Documentation" in lines:
            end_index = lines.index("Documentation")
        else:
            end_index = len(lines)

        feature_lines = lines[
            features_index + 1 :
            end_index
        ]

        i = 0

        while i < len(feature_lines):

            title = feature_lines[i]

            if title in ["Show more", "Read more"]:
                i += 1
                continue

            if i + 1 < len(feature_lines):

                description = feature_lines[i + 1]

                if len(description) > 20:

                    product["features"].append({
                        "title": title,
                        "description": description
                    })

            i += 2

    except:
        pass

    # -----------------------------
    # SPECIFICATIONS
    # -----------------------------

    try:

        specs_index = lines.index("Specifications")

        if "Documentation" in lines:
            end_index = lines.index("Documentation", specs_index)
        elif "Disclaimer" in lines:
            end_index = lines.index("Disclaimer")
        else:
            end_index = len(lines)

        spec_lines = lines[
            specs_index + 1 :
            end_index
        ]

        i = 0

        while i < len(spec_lines) - 1:

            key = spec_lines[i]

            value = spec_lines[i + 1]

            if (
                len(key) < 100
                and len(value) < 500
            ):
                product["specifications"][key] = value

            i += 2

    except:
        pass

    # -----------------------------
    # DOCUMENTATION
    # -----------------------------

    try:

        docs_index = lines.index("Documentation")

        if "Disclaimer" in lines:
            end_index = lines.index("Disclaimer")
        else:
            end_index = len(lines)

        doc_lines = lines[
            docs_index + 1 :
            end_index
        ]

        for line in doc_lines:

            if "PDF" in line:
                continue

            if "KB" in line:
                continue

            if len(line) > 3:

                product["documentation"].append(line)

    except:
        pass

    return product