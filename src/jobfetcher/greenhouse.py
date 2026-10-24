import html
import re
import requests

from datetime import datetime
from typing import Any, Pattern, Dict, Tuple
from functools import cache

from jobfetcher.jobfetcher import JobFetcher


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
