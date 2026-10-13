import sys
import json
import re
from typing import Any, Pattern, Dict
import requests

class GreenhouseJobFetcher:
    """
    Fetches job data from GreenHouse.io's API.

    Reference: https://docs.greenhouse.io/job-board.html#retrieve-a-job
    """
    JOB_POST_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.url_re: Pattern[str] = re.compile(
            r'https?://job-boards\.greenhouse\.io/(?P<board_token>[^/]+)/jobs/(?P<job_id>\d+)'
        )

    def _parse_url(self, url: str) -> tuple[str, str]:
        """Parse a GreenHouse.io URL into (board_token, job_id)."""
        if mo := self.url_re.search(url):
            return mo.group("board_token"), mo.group("job_id")
        raise ValueError(f"Invalid GreenHouse.io URL: {url}")

    def retrieve_greenhouse_job(self, url: str) -> dict[str, Any]:
        """Fetch a job posting from GreenHouse.io by its public URL."""
        board_token, job_id = self._parse_url(url)
        job_post_url = self.JOB_POST_URL_TEMPLATE.format(
            board_token=board_token, job_id=job_id
        )
        response = self.session.get(job_post_url)
        response.raise_for_status()
        return response.json()

class AshbyHQJobFetcher:
    """
    Retrieves jobs from AshbyHQ.
    Ashby only allows retrieving full boards, so we need to cache each board's data when we first retrieve it.
    """
    JOB_BOARD_API_URL_PATTERN = "https://api.ashbyhq.com/posting-api/job-board/{board_name}?includeCompensation=true"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.url_re: Pattern[str] = re.compile(
            r'https\:\/\/jobs\.ashbyhq\.com\/(?<board_name>[^\/]+)/(?<job_id>[0-9a-f-]+)'
        )
        self.board_cache = {}

    def _parse_url(self, url:str) -> tuple[str, str]:
        """
        Parse an AshbyHQ URL into (board_name, job_id).
        :return: a tuple with the board name and job id.
        :raise: ValueError for invalid URLs.
        """
        if mo := self.url_re.search(url):
            return mo.group("board_name"), mo.group("job_id")
        raise ValueError(f"Invalid AshbyHQ URL: {url}")

    def _retrieve_cached_board(self, board_name:str):
        """
        Checks a board with the given name is cached and returns it.
        Cache misses trigger a fetch from AshbyHQ.
        :returns: a dictionary representing the job board.
        :raise: ValueError if retrieval goes wrong.
        """
        if board_name in self.board_cache:
            return self.board_cache[board_name]

        board_url = self.JOB_BOARD_API_URL_PATTERN.format(board_name=board_name)
        response = self.session.get(board_url)
        response.raise_for_status()
        self.board_cache[board_name] = response.json()
        return self.board_cache[board_name]

for job in json.load(sys.stdin.buffer):
    print(job.get("url", None))
