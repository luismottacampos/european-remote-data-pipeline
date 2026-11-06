import argparse
import logging
import requests
import time
import pyarrow as pa
import pyarrow.dataset as ds
import os

from pyarrow import parquet
from random import uniform
from requests import HTTPError
from datetime import datetime
from .schema import JOB_DATA_SCHEMA
from .toolbox import configure_logging
from typing import Any


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
        '--input', '-i', type=str, default='data/extracted',
        help='The folder storing data extracted from the emails. Defaults to "./data/extracted".'
    )
    parser.add_argument(
        '--output', '-o', type=str, default='data/with_description',
        help='The folder to be used for jobs enriched with descriptions. Defaults to "./data/with_description".'
    )
    return parser.parse_args()


def add_raw_content(job: dict, session: requests.Session) -> None:
    """
    Adds raw contents retrieved from job['url'] to the given job dictionary.
    """
    logger = logging.getLogger()
    try:
        logger.info("Attempting to retrieve raw content for job '%s'", job['id'])
        response = session.get(job['url'], timeout=10)
        response.raise_for_status()

        job["raw_content"] = response.content.decode(encoding=response.encoding or 'utf-8')
        logger.info("Job '%s' now has %d bytes of raw_content.", job['id'], len(job['raw_content']))
    except HTTPError as e:
        job["errors"] = (job.get("errors") or []) + [str(e)]
        logger.warning(
            "'%s' while trying to enrich job '%s' (%s).",
            str(e), job.get("raw_title", "No Title"), job.get("url", "No URL")
        )
    except requests.exceptions.RequestException as e:
        # Catches: ConnectionError, Timeout, TooManyRedirects, SSLError, etc.
        job["errors"] = (job.get("errors") or []) + [str(e)]
        logger.error("Request failed for '%s': %s", job.get("url", "No URL"), str(e))
    except UnicodeDecodeError as e:
        job["errors"] = (job.get("errors") or []) + [str(e)]
        logger.error("Failed to decode content from '%s': %s", job.get("url", "No URL"), str(e))


def _gather_parquet_files(table_dir: str) -> list[str]:
    """Gather all parquet files from the given directory."""
    logger = logging.getLogger()

    logger.debug('Attempting to read data from "%s"', table_dir)
    files = [
        os.path.join(table_dir, f)
        for f in os.listdir(table_dir)
        if f.endswith('.parquet')
    ]
    logger.info('Found %d parquet files in "%s".', len(files), table_dir)

    if not files:
        logger.warning('No parquet files found in "%s".', table_dir)
        raise FileNotFoundError('No parquet files found in "%s".', table_dir)

    return files


def _read_data_from(table_dir: str, filters=ds.field('raw_content').is_null()) -> list[dict[str, Any]]:
    """
    Read Parquet tables as a python list
    :param: table_dir: a directory where to find partial parquet files for the table.
    :param: filters: Filters passed straight to pyarrow.parquet.read_table().
    :return: a list of dictionaries representing the job records as defined in schema.py.
    """
    input_files = _gather_parquet_files(table_dir)
    combined = pa.concat_tables(
        parquet.read_table(file, schema=JOB_DATA_SCHEMA, filters=filters) for file in input_files
    )
    return combined.to_pylist()


def main() -> None:
    """Where everything happens"""
    args = parse_arguments()
    configure_logging(verbosity=args.verbose)

    logger = logging.getLogger()

    session = requests.Session()
    session.headers.update(HEADERS)

    jobs = _read_data_from(args.input)

    for job in jobs:
        add_raw_content(job, session)
        # rate limiting with a random component ensures ATSs still allow us through.
        time.sleep(uniform(0.5, 2.0))

    if '://' not in args.output:
        # Avoid silly things like writing to non-existent dirs.
        # Delegate accessing cloud resources to PyArrow.
        os.makedirs(args.output, exist_ok=True)

    output_file = os.path.join(args.output, f"part-{int(datetime.now().timestamp())}.parquet")
    logger.info('Writing enriched jobs to "%s"', output_file)
    output_table = pa.Table.from_pylist(jobs, schema=JOB_DATA_SCHEMA)
    parquet.write_table(output_table, output_file)


if __name__ == '__main__':
    main()
