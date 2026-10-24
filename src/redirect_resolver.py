import requests

from functools import cache
from urllib.parse import urljoin

class RedirectResolver():
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    @cache
    def resolve(self, url:str) -> str:
        """
        Uses HEADER requests to determine if the request will be redirected.

        :return: if url redirects, returns the last fully-qualified URL of the redirect chain. Else, the original URL.
        :raise: HTTPError for the obvious reasons.
        """
        r = self.session.head(url, allow_redirects=True)
        r.raise_for_status()
        if r.history is not None and len(r.history) > 0 and r.history[-1].headers is not None and 'Location' in r.history[-1].headers:
            return urljoin(r.history[-1].url, r.history[-1].headers.get('Location'))
        return url
