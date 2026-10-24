import re
import requests

from datetime import datetime
from typing import Any, Pattern, Dict
from functools import cache

from jobfetcher.jobfetcher import JobFetcher


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
