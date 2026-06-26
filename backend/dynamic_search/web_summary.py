"""
dynamic_search/web_summary.py
Summarises raw DuckDuckGo search snippets into a clean context
string that can be passed into the Gemini prompt.
"""


def summarise_web_results(results: list[str]) -> str:
    if not results:
        return ""
    combined = "\n\n".join(results)
    return f"[Web Search Results]\n{combined}"
