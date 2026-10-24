import requests
from typing import Any, Dict, Tuple
from functools import cache


class JobFetcher:
    """
    One JobFetcher to rule them all, one object to find them,
    One Parent Class to bring them all and in the source-code bind them
    In the Land of Web-Scrapping where the Data lie.
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        """
        Common initialisations to all JobFetcher subclasses.
        """
        self.session = session or requests.Session()

    @cache
    def parse_url(self, url:str) -> Tuple[str, str]:
        """
        Parse a job-post URL.
        :return: a tuple with the job's board and ID.
        :raise: ValueError if the URL is invalid.
        """
        raise NotImplementedError('Must be overriden by the specialised class')

    @cache
    def fetch(self, url:str) -> Dict[str, Any]:
        """
        Fetch the job post data through the appropriate API.
        :return: an object representing the data retrieved.
        :raise: HTTPError, as required.
        """
        raise NotImplementedError("Must be overriden by the specialised class")
