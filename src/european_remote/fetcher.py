import sys
import re
import json
from datetime import datetime
from functools import cache
from typing import Any, Pattern, Dict, Tuple
import requests
import html


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
        r'https://job-boards\.greenhouse\.io/(?P<board_token>[^/]+)/jobs/(?P<job_id>\d+)'
    )

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


class WorkableJobFetcher(JobFetcher):
    """
    Fetches job data from Workable's public widget API.
    Reference: https://dev.to/zsevic/integration-with-workable-public-jobs-api-3nk4
    """
    JOB_BOARD_API_URL = "https://apply.workable.com/api/v1/widget/accounts/{board}?details=true"
    URL_RE: Pattern[str] = re.compile(
        r'https://apply\.workable\.com/(?P<board>[^/]+)/j/(?P<job_id>[A-Za-z0-9]+)'
    )

    def __init__(self, session: requests.Session | None = None) -> None:
        super().__init__(session=session)

    @cache
    def parse_url(self, url: str) -> Tuple[str, str]:
        """Parse a Workable URL into (board, job_id)."""
        if mo := self.URL_RE.search(url):
            return mo.group("board"), mo.group("job_id")
        raise ValueError(f"Invalid Workable URL: {url}")

    @cache
    def _board(self, board: str) -> Dict[str, Any]:
        """
        Retrieves all jobs for a Workable account.
        """
        board_url = self.JOB_BOARD_API_URL.format(board=board)
        response = self.session.get(board_url)
        response.raise_for_status()
        data = response.json()
        return {
            job['shortcode']: {
                'id': job['shortcode'],
                'url': job['url'],
                'title': job['title'],
                'department': job.get('department'),
                'description': html.unescape(job.get('description', '')),
                'published_at': (
                    datetime.fromisoformat(
                        job.get('published_on', '').replace(' ', '')
                    ) if job.get('published_on') else None),
            }
            for job in data.get('jobs', [])
        }

    @cache
    def fetch(self, url: str) -> Dict[str, Any]:
        """
        Fetch a job posting from Workable by its public URL.
        """
        board, job_id = self.parse_url(url)
        return self._board(board).get(job_id, {})


for job in json.load(sys.stdin.buffer):
    match job:
        case {'url': url} if url.startswith('https://job-boards.greenhouse.io/'):
            print(f'Greenhouse Board: {url}')
        case {'url': url} if url.startswith('https://www.mongodb.com/careers/job/'):
            print(f'MongoDB Careers by Greenhouse: {url}')
        case {'url': url} if url.startswith('https://jobs.ashbyhq.com/'):
            print(f'AshbyHQ Board: {url}')
        case {'url': url} if url.startswith('https://careers.datadoghq.com/'):
            print(f'DatadogHQ by Greenhouse: {url}')
        case {'url': url} if url.startswith('https://apply.workable.com/j/'):
            print(f'Workable job board: {url}')
        case {'url': url}:
            print(f'UNIDENTIFIED: {url}')
        case _:
            continue
