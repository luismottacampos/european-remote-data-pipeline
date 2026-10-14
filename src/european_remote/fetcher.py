import sys
import json
import re
from datetime import datetime
from functools import cache
from typing import Any, Pattern, Dict, Tuple
import requests
import html

from pprint import pprint


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


class GreenhouseJobFetcher(JobFetcher):
    """
    Fetches job data from GreenHouse.io's API.

    Reference: https://docs.greenhouse.io/job-board.html#retrieve-a-job
    """
    JOB_POST_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
    URL_RE: Pattern[str] = re.compile(
        r'https?://job-boards\.greenhouse\.io/(?P<board_token>[^/]+)/jobs/(?P<job_id>\d+)'
    )

    # Mnemonic: (board, ID) => { job_title: '...', job_desc: '...', ...}
    _cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def __init__(self, session: requests.Session | None = None) -> None:
        super().__init__(session=session)   

    @cache
    def parse_url(self, url: str) -> Tuple[str, str]:
        """Parse a GreenHouse.io URL into (board_token, job_id)."""
        if mo := self.URL_RE.search(url):
            return mo.group("board_token"), mo.group("job_id")
        raise ValueError(f"Invalid GreenHouse.io URL: {url}")

    @cache
    def fetch(self, url: str) -> Dict[str, Any]:
        """
        Fetch a job posting from GreenHouse.io by its public URL.
        """
        board_token, job_id = self.parse_url(url)
        job_post_url = self.JOB_POST_URL_TEMPLATE.format(
            board_token=board_token, job_id=job_id
        )
        response = self.session.get(job_post_url)
        response.raise_for_status()
        data = dict(response.json())
        return {
            'id': data.get('id'),
            'url': data.get('absolute_url'),
            'department': next((d.get('name') for d in data.get('departments', []) if isinstance(d, dict)), None),
            'title': data.get('title'),
            'description': html.unescape(data['content']),
            'published_at': datetime.fromisoformat(data['first_published'].replace(' ', '')),
            'updated_at': datetime.fromisoformat(data['updated_at'].replace(' ', '')),
        }

class AshbyHQJobFetcher(JobFetcher):
    """
    Retrieves jobs from AshbyHQ.
    Ashby only allows retrieving full boards, so we need to cache each board's data when we first retrieve it.
    """
    JOB_BOARD_API_URL_PATTERN = "https://api.ashbyhq.com/posting-api/job-board/{board_name}?includeCompensation=true"
    URL_RE: Pattern[str] = re.compile(
        r'https\:\/\/jobs\.ashbyhq\.com\/(?P<board_name>[^\/]+)/(?P<job_id>[0-9a-f-]+)'
    )

    def __init__(self, session: requests.Session | None = None) -> None:
        super().__init__(session=session)

    @cache
    def parse_url(self, url:str) -> tuple[str, str]:
        """
        Parse an AshbyHQ URL into (board_name, job_id).
        :return: a tuple with the board name and job id.
        :raise: ValueError for invalid URLs.
        """
        if mo := self.URL_RE.search(url):
            return mo.group("board_name"), mo.group("job_id")
        raise ValueError(f"Invalid AshbyHQ URL: {url}")

    @cache
    def _board(self, board_token:str) -> Dict[str,Any]:
        """
        Retrieves a job board from Ashby's public API and returns it.

        :returns: a dictionary representing the job board.
        :raise: HTTPError if retrieval goes wrong.
        """
        board_url = self.JOB_BOARD_API_URL_PATTERN.format(board_name=board_token)
        response = self.session.get(board_url)
        response.raise_for_status()

        return {
            job['id']: {
                'id': job['id'],
                'url': job['jobUrl'],
                'department': job['department'],
                'team': job['team'],
                'title': job['title'],
                'description': job['descriptionPlain'],
                'published_at': datetime.fromisoformat(job['publishedAt'].replace(' ', '')),
            }
            for job in dict(response.json()).get('jobs', [])
        }

    @cache
    def fetch(self, url:str) -> Dict[str, Any]:
        """
        Fetch a job posting from AshbyHQ.com by its public URL.
        """
        board_token, job_id = self.parse_url(url=url)
        return self._board(board_token=board_token).get(job_id, {})

# fetcher = GreenhouseJobFetcher()
# j = fetcher.fetch(url="https://job-boards.greenhouse.io/canonical/jobs/6635671")

fetcher = AshbyHQJobFetcher()
j = fetcher.fetch(url="https://jobs.ashbyhq.com/duck-duck-go/80797cf4-64b2-4e94-9d87-6f2ecc45c862")

pprint(j)

# for job in json.load(sys.stdin.buffer):
#     print(job.get("url", None))


