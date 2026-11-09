import argparse
import dotenv
import httpx
import logging
import os
import pyarrow as pa
import time

from .llm_extractor import GenericJobAdExtractor
from .toolbox import configure_logging, read_data_from
from pyarrow import parquet as pq
from pydantic import ValidationError
from bs4 import BeautifulSoup


def positive_int(value: str) -> int:
    """Validate that the value is a positive integer."""
    try:
        num = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'"{value}" is not a valid integer')

    if num <= 0:
        raise argparse.ArgumentTypeError(f'"{value}" must be greater than zero')

    return num


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--verbose', '-v', action='count', default=0,
        help='Each occurrence increments log verbosity from ERROR (default) to DEBUG.'
    )
    parser.add_argument(
        '--input', '-i', type=str, default='data/jobs',
        help='The folder storing data from fetcher. Defaults to "./data/jobs".'
    )
    parser.add_argument(
        '--output', '-o', type=str, default='data/jobs',
        help='The folder to be used for jobs enriched with extracted content. Defaults to "./data/jobs".'
    )
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    parser.add_argument('--limit', '-l', type=positive_int, default=None,
                        help='The maximum number of records to process.')
    return parser.parse_args()


def clean(content: str) -> str:
    return BeautifulSoup(content, 'html.parser').get_text()


def main() -> None:
    """Main entry point for job ad extraction."""
    dotenv.load_dotenv()
    args = parse_arguments()
    configure_logging(args.verbose)

    logger = logging.getLogger()

    try:
        extractor = GenericJobAdExtractor(
            model_provider=os.environ['MODEL_PROVIDER'],
            model_name=os.environ['MODEL_NAME'],
            api_key=os.environ['MODEL_API_KEY'],
        )
    except KeyError as e:
        logger.critical(msg=str(e))
        raise

    records = read_data_from(args.input)
    record_count = len(records)

    logger.info("Read %d jobs from input.", record_count)
    if args.limit and args.limit >= record_count:
        logger.info('Willing to process up to %s jobs.', args.limit)

    enriched_jobs = 0
    for job in records:
        if args.limit and enriched_jobs >= args.limit:
            break

        # Skip jobs without raw_content or already processed
        if not job.get('raw_content') or job.get('extraction_status') == 'success':
            continue

        job_id = job.get('id', 'unknown')
        logger.info("Enriching job '%s' (%s)...", job_id, job.get("url"))
        start = time.perf_counter()

        job['extraction_status'] = 'error'
        try:
            logger.debug("Job '%s' has %s bytes of raw content.", job['id'], job['content_length'])

            logger.debug('RAW CONTENT SAMPLE ' + '=' * 31 + '\n%s\n' + '=' * 50, job['raw_content'][:200])
            clean_content = clean(job['raw_content'])
            logger.debug('CLEAN CONTENT SAMPLE ' + '=' * 29 + '\n%s\n' + '=' * 50, clean_content[:200])

            job['content'] = extractor.extract(content=clean_content)
            job['extraction_status'] = 'success'
            enriched_jobs += 1
            logger.debug('EXTRACTED ' + '=' * 40 + '\n%s\n' + '=' * 50, job['content'])
            logger.info(
                "Successfully extracted %d bytes of information from job '%s'.",
                len(str(job["content"])), job_id
            )
        except ValidationError:
            logger.warning(
                "Validation Error: no data extracted from job '%s' (%s). Raw content sample: '%s'",
                job_id, job.get("url"), (job.get("raw_content") or "")[:100] or "None"
            )
            continue
        except httpx.HTTPStatusError as e:
            logger.warning("Job '%s' (%s): Got HTTP/%d.", job_id, job.get("url"), e.response.status_code)
            continue
        except httpx.TimeoutException:
            logger.warning("Job '%s' (%s): Extraction timed out.", job_id, job.get("url"))
            continue

        duration = time.perf_counter() - start
        logger.info(
            "Job '%s' (%s) processed in %.2fs (model: %s)",
            job_id, job.get('url'), duration, extractor.model_name
        )

    if args.limit:
        logger.info(
            "Enriched %d out of %d processed jobs, respecting the imposed limit of %d jobs.",
            enriched_jobs, record_count, args.limit
        )
    else:
        logger.info("Enriched %d out of %d processed jobs.", enriched_jobs, record_count)

    # Write output
    if '://' not in args.output:
        os.makedirs(args.output, exist_ok=True)

    if args.dry_run:
        logger.warning('Would have written "%s".', os.path.join(args.output, "jobs.parquet"))
    else:
        pq.write_table(
            table=pa.Table.from_pylist(records),
            where=os.path.join(args.output, "jobs.parquet")
        )
        logger.info('Wrote %s jobs to file.', len(records))


if __name__ == '__main__':
    main()
