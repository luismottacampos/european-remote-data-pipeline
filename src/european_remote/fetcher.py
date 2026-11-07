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
    """
    Adds raw contents retrieved from job['url'] to the given job dictionary.
    :return: 1 if the job contents were succesfully retrieved from the publisher, 0 otherwise.
    """
    logger = logging.getLogger()
    outcome = 0
    try:
        logger.info("Attempting to retrieve raw content for job '%s'", job['id'])
        response = session.get(job['url'], timeout=10)
        response.raise_for_status()

        job['raw_content'] = response.content.decode(encoding=response.encoding or 'utf-8')
        job['last_fetch_attempt'] = datetime.now()
        job['fetch_status'] = 'success'
        job['last_fetch_status_code'] = response.status_code
        job['last_fetch_reason'] = response.reason
        job['content_length'] = int(response.headers.get('Content-Length') or len(job['raw_content']))
        logger.info("Job '%s' now has %d bytes of raw_content.", job['id'], job['content_length'])
        outcome = 1

    except (requests.HTTPError, requests.RequestException) as e:
        match e:
            case requests.HTTPError(
                response=requests.Response(status_code=status_code, url=url, reason=reason, headers=headers)
            ):
                job['last_fetch_attempt'] = datetime.now()
                match status_code:
                    case 404, 410:
                        job['fetch_status'] = 'gone'
                    case 403:
                        job['fetch_status'] = 'throttled'
                    case _:
                        job['fetch_status'] = 'error'
                job['last_fetch_status_code'] = status_code
                job['last_fetch_reason'] = reason
                job['content_length'] = int(headers.get('Content-Length') or -1)
                logger.warning("Got 'HTTP/%s - %s' while fetching '%s' to enrich job '%s'.",
                               status_code, reason, url, job['id'])
            case _:
                job['last_fetch_attempt'] = datetime.now()
                job['fetch_status'] = 'error'
                job['last_fetch_status_code'] = getattr(e.response, 'status_code', None)
                job['last_fetch_reason'] = getattr(e.response, 'reason', 'Unknown Reason')
                job['content_length'] = None
                logger.error(
                    "Job %s: fetching '%s' failed: 'HTTP/%s - %s'.",
                    job['id'], getattr(e.response, 'url', 'Unknown URL'),
                    job['last_fetch_status_code'], job['last_fetch_reason']
                )

    except UnicodeDecodeError as e:
        job['last_fetch_attempt'] = datetime.now()
        job['fetch_status'] = 'error'
        job['last_fetch_status_code'] = None
        job['last_fetch_reason'] = None
        job['content_length'] = None
        logger.error("Got '%s' while attempting to decode retrieved contents for job '%s'.", e, job['id'])

    return outcome


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
