import json
import logging
import requests
import sys

from requests import HTTPError

# FIXME accept logging configuraiton parameters
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger()

def add_raw_content(job:dict, session:requests.Session) -> dict:
    """
    :return: a string representing the page fetched from the URL (hopefully 
             with information about the job) or None if url is None.
    :raise: HTTPError for the obvious reasons.
    """
    try:
        logger.info("Processing job '%s' (%s)...", job.get("raw_title"), job.get("url"))
        response = session.get(str(job.get("url")))
        response.raise_for_status()

        job["raw_content"] = response.content.decode(
            encoding=response.encoding or 'utf-8')
        logger.info("\tadded %d bytes to raw_content.", len(job["raw_content"]))
    except HTTPError as e:
        job["errors"] = job.get("errors", []).append(str(e))
        logger.warning(
            "'%s' while trying to enrich job '%s' (%s).",
            str(e), job.get("raw_title", "No Title"), job.get("url", "No URL")
        )
    return job

session = requests.Session()
jobs = [add_raw_content(job, session) for job in json.load(sys.stdin.buffer)]

json.dump(obj=jobs, fp=sys.stdout)
