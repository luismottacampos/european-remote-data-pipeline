import html
import re
import requests

from datetime import datetime
from typing import Any, Pattern, Dict, Tuple
from functools import cache

from jobfetcher.jobfetcher import JobFetcher


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

