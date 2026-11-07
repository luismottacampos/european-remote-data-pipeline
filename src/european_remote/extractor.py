import argparse
import email
import email.utils
import hashlib
import logging
import os
import pyarrow as pa
import pyarrow.parquet as parquet
import re
import uuid

from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from .toolbox import configure_logging, read_data_from


EMPLOYER_RE = re.compile(r'\(at (?P<employer>[^\)]+)\)')


def parse_arguments() -> argparse.Namespace:
    """Ditto"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help='Each occurrence increments log verbosity from ERROR (default) to DEBUG.'
    )
    parser.add_argument(
        '--output', type=str, default='data/jobs',
        help='The folder containing all the parquet data-files. Defaults to "data/jobs".'
    )
    parser.add_argument('files', nargs='+', help='Email files')
    return parser.parse_args()


def normalise_url(url: str) -> str:
    """
    URL Normalisation
    :return: a complete URL in canonical form, without query part.
    """
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query='', fragment='', path=parsed.path.rstrip('/')))


def build_job(link, published_at) -> dict:
    """Builds a job from the given bs4 Tag"""
    return {
        "id": str(uuid.uuid4()),
        "url": (url := str(link['href'])),
        "url_hash": hashlib.sha256(normalise_url(url).encode()).hexdigest(),
        "raw_title": str(link.span.string),
        "raw_employer": (raw_employer := str(link.span.next_sibling.next_sibling.string)),
        "employer": (
            mo.group("employer")
            if (mo := EMPLOYER_RE.search(raw_employer))
            else None
        ),
        "published_at": published_at,
    }


def main():
    """Where everything happens"""
    args = parse_arguments()
    configure_logging(verbosity=args.verbose)

    logger = logging.getLogger()

    jobs: list = read_data_from(args.output)
    existing_url_hashes: set = {job['url_hash'] for job in jobs}

    for file in args.files:
        logger.info('Processing "%s"', file)

        message = email.message_from_binary_file(open(file, 'rb'))
        date_tuple = email.utils.parsedate_tz(message['Date'])
        published_at = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple)) if date_tuple else None

        if message.is_multipart():
            logger.warning('Ignoring unsupported RFC 5322 multipart message in "%s"', file)
            continue

        payload = bytes(message.get_payload(decode=True)).decode(encoding=message.get_content_charset() or "utf-8")
        logger.info('Message in "%s" contains a payload of %d bytes', file, len(payload))

        soup = BeautifulSoup(payload, "html.parser")
        jobs += filter(
            lambda j: j['url_hash'] not in existing_url_hashes,
            [build_job(link, published_at) for link in soup.css.select("li a")]
        )

    if '://' not in args.output:
        # Avoid silly things like writing to non-existent dirs.
        # Delegate accessing cloud resources to PyArrow.
        os.makedirs(args.output, exist_ok=True)

    parquet.write_table(
        table=pa.Table.from_pylist(jobs),
        where=os.path.join(args.output, "jobs.parquet")
    )


if __name__ == '__main__':
    main()
