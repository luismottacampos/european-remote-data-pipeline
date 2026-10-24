import json
import logging
import requests
import sys
import time

from random import uniform
from requests import HTTPError

# FIXME accept logging configuraiton parameters
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def add_raw_content(job:dict, session:requests.Session) -> dict:
    """
    :return: a string representing the page fetched from the URL (hopefully 
             with information about the job) or None if url is None.
    :raise: HTTPError for the obvious reasons.
    """
    try:
        logger.info("Processing job '%s' (%s)...", job.get("raw_title"), job.get("url"))
        response = session.get(url=str(job.get("url")), timeout=10)
        response.raise_for_status()

        job["raw_content"] = response.content.decode(
            encoding=response.encoding or 'utf-8')
        logger.info("\tadded %d bytes to raw_content.", len(job["raw_content"]))
    except HTTPError as e:
        job["errors"] = job.get("errors", []) + [str(e)]
        logger.warning(
            "'%s' while trying to enrich job '%s' (%s).",
            str(e), job.get("raw_title", "No Title"), job.get("url", "No URL")
        )
    except requests.exceptions.RequestException as e:
        # Catches: ConnectionError, Timeout, TooManyRedirects, SSLError, etc.
        job["errors"] = job.get("errors", []) + [str(e)]
        logger.error("Request failed for '%s': %s", job.get("url", "No URL"), str(e))
    except UnicodeDecodeError as e:
        job["errors"] = job.get("errors", []) + [str(e)]
        logger.error("Failed to decode content from '%s': %s", job.get("url", "No URL"), str(e))

    return job

session = requests.Session()
session.headers.update(HEADERS)

jobs = json.load(sys.stdin.buffer)
for i, job in enumerate(jobs):
    if i > 0:
        time.sleep(uniform(0.5, 2.0))
    jobs[i] = add_raw_content(job, session)

json.dump(obj=jobs, fp=sys.stdout)
