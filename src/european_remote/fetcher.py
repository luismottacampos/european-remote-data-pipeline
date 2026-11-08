import argparse
import logging
import requests
import time
import pyarrow as pa
import os

from pyarrow import parquet
from random import uniform
from datetime import datetime
from .toolbox import configure_logging, read_data_from


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; '
        'Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def parse_arguments() -> argparse.Namespace:
    """Ditto"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help='Each occurrence increments log verbosity from ERROR (default) to DEBUG.'
    )
    parser.add_argument(
        '--input', '-i', type=str, default='data/jobs',
        help='The folder storing data extracted from the emails. Defaults to "./data/jobs".'
    )
    parser.add_argument(
        '--output', '-o', type=str, default='data/jobs',
        help='The folder to be used for jobs enriched with descriptions. Defaults to "./data/jobs".'
    )
    return parser.parse_args()


def add_raw_content(job: dict, session: requests.Session) -> int:
    """Adds raw contents retrieved from job['url'] to the given job dictionary.

    Returns 1 if successful, 0 otherwise.
    """
    logger = logging.getLogger()
    job['last_fetch_attempt'] = datetime.now()

    # Map special status codes to fetch_status values
    STATUS_MAP = {403: 'throttled', 404: 'gone', 410: 'gone'}

    try:
        response = session.get(job['url'], timeout=10)
        job['last_fetch_status_code'] = response.status_code
        job['last_fetch_reason'] = response.reason

        if response.status_code == 200:
            try:
                job['raw_content'] = response.content.decode(encoding=response.encoding or 'utf-8')
                job['fetch_status'] = 'success'
                content_len = response.headers.get('Content-Length')
                job['content_length'] = int(content_len) if content_len else len(job['raw_content'])
                logger.info("Added %s bytes of raw content to job '%s'.",
                           job['content_length'], job['id'])
                return 1
            except UnicodeDecodeError as e:
                job['fetch_status'] = 'error'
                job['content_length'] = None
                logger.error("Got '%s' while decoding contents for job '%s'.", e, job['id'])
                return 0

        # All non-200 HTTP status codes
        job['fetch_status'] = STATUS_MAP.get(response.status_code, 'error')
        content_len = response.headers.get('Content-Length')
        job['content_length'] = int(content_len) if content_len else -1
        logger.warning("Got %s - %s while fetching from '%s' for job '%s'.",
                      response.status_code, response.reason, response.url, job['id'])
        return 0

    except requests.RequestException as e:
        job['fetch_status'] = 'error'
        job['last_fetch_status_code'] = getattr(e.response, 'status_code', None)
        job['last_fetch_reason'] = getattr(e.response, 'reason', 'Unknown Reason')
        job['content_length'] = None
        req = getattr(e, 'request', None)
        url = req.url if req and hasattr(req, 'url') else 'Unknown URL'
        logger.error("Job %s: network error fetching '%s': %s", job['id'], url, str(e))
        return 0


def main() -> None:
    """Where everything happens"""
    args = parse_arguments()
    configure_logging(verbosity=args.verbose)

    logger = logging.getLogger()

    session = requests.Session()
    session.headers.update(HEADERS)

    jobs = read_data_from(args.input)

    all_jobs, enriched_jobs = 0, 0
    for job in jobs:
        all_jobs += 1
        if job.get('fetch_status', 'not_fetched') in ('success', 'gone'):
            continue

        enriched_jobs += add_raw_content(job, session)
        # rate limiting with a random component ensures ATSs still allow us through.
        time.sleep(uniform(0.5, 2.0))

    logger.info("Enriched %d out of %d processed jobs.", enriched_jobs, all_jobs)

    # Delegate accessing cloud resources to PyArrow.
    if '://' not in args.output:
        # Avoid silly things like writing to non-existent dirs.
        os.makedirs(args.output, exist_ok=True)

    parquet.write_table(table=pa.Table.from_pylist(jobs), where=os.path.join(args.output, "jobs.parquet"))
    logger.info('Wrote %s jobs to file.', all_jobs)


if __name__ == '__main__':
    main()
