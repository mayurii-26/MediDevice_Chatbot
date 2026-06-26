"""
logger.py
Append-only search logger. Writes to logs/search_logs.txt.
"""
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "logs", "search_logs.txt")


def log_search(
    question: str,
    source: str,
    matched_product: str = "",
    matched_category: str = "",
    confidence: float = 0.0,
) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"[{timestamp}] "
            f"SOURCE={source} | "
            f"CONFIDENCE={confidence:.2f} | "
            f"PRODUCT={matched_product or 'N/A'} | "
            f"CATEGORY={matched_category or 'N/A'} | "
            f"QUESTION={question}\n"
        )
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print("Logger error:", e)
