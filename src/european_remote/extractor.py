import argparse
import email.message
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
from .schema import JOB_DATA_SCHEMA
from .toolbox import configure_logging


EMPLOYER_RE = re.compile(r'\(at (?P<employer>[^\)]+)\)')


def parse_arguments() -> argparse.Namespace:
    """Ditto"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help='Each occurrence increments log verbosity from ERROR (default) to DEBUG.'
    )
    parser.add_argument(
        '--output', type=str, default='data/extracted',
        help='The folder to be used for data extracted from the emails. Defaults to "./data/extracted".'
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


def build_job(link) -> dict:
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
    }


def main():
    """Where everything happens"""
    args = parse_arguments()
    configure_logging(verbosity=args.verbose)

    logger = logging.getLogger()

    jobs = []

    for file in args.files:
        logger.info('Processing "%s"', file)

        message: email.message.Message = email.message_from_binary_file(open(file, 'rb'))

        if message.is_multipart():
            logger.warning('Ignoring unsupported RFC 5322 multipart message in "%s"', file)
            continue

        payload = bytes(message.get_payload(decode=True)).decode(encoding=message.get_content_charset() or "utf-8")
        logger.info('Message in "%s" contains a payload of %d bytes', file, len(payload))

        soup = BeautifulSoup(payload, "html.parser")
        jobs += [build_job(link) for link in soup.css.select("li a")]

    if '://' not in args.output:
        # Avoid silly things like writing to non-existent dirs.
        # Delegate accessing cloud resources to PyArrow.
        os.makedirs(args.output, exist_ok=True)

    # Using partial files here is definitively, totally overkill. :D
    filename = os.path.join(args.output, f"part-{int(datetime.now().timestamp())}.parquet")
    logger.info("Writing extracted jobs to '%s'.", filename)
    table = pa.Table.from_pylist(jobs, schema=JOB_DATA_SCHEMA)
    parquet.write_table(table, where=filename)


if __name__ == '__main__':
    main()
