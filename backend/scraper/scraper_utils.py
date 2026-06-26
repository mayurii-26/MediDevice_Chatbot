import requests

from bs4 import BeautifulSoup


def get_soup(url):

    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0"
        },
        timeout=20
    )

    return BeautifulSoup(
        response.text,
        "html.parser"
    )