import requests
from typing import List, Dict

ARASAAC_SEARCH_URL = "https://api.arasaac.org/v1/pictograms/{lang}/search/{term}"
ARASAAC_PICTO_URL = "https://static.arasaac.org/pictograms/{id}/{id}_500.png"


class ArasaacClient:
    def __init__(self, lang: str = "fr", timeout: float = 5.0):
        self.lang = lang
        self.timeout = timeout

    def search(self, term: str, limit: int = 5) -> List[Dict]:
        """
        Search pictograms for a term.
        Returns a list of dicts with at least: id, keywords
        """
        term = term.strip().lower()
        if not term:
            return []

        url = ARASAAC_SEARCH_URL.format(lang=self.lang, term=term)
        resp = requests.get(url, timeout=self.timeout)

        if resp.status_code != 200:
            return []

        results = resp.json()
        return results[:limit]

    def pictogram_url(self, picto_id: int) -> str:
        """
        Return a direct URL to the pictogram image (PNG).
        """
        return ARASAAC_PICTO_URL.format(id=picto_id)
