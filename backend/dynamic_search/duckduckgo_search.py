from ddgs import DDGS


def search_web(query: str, max_results: int = 5):
    results = []

    search_query = (
        f"{query} medical device "
        f"healthcare hospital equipment"
)

    try:
        with DDGS() as ddgs:
            search_results = ddgs.text(
                search_query,
                max_results=max_results
            )

            for r in search_results:
                title = r.get("title", "")
                body = r.get("body", "")
                results.append(f"{title}: {body}")

    except Exception as e:
        print("DDGS Error:", e)

    return results