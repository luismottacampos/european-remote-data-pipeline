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
    return parser.parse_args()


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

    jobs = read_data_from(args.input)
    logger.info("Read %d jobs from input.", len(jobs))

    enriched_jobs = 0
    for job in jobs:
        # Skip jobs without raw_content or already processed
        if not job.get('raw_content') or job.get('extraction_status') == 'success':
            continue

        job_id = job.get('id', 'unknown')
        logger.info("Enriching job '%s' (%s)...", job_id, job.get("url"))
        start = time.perf_counter()

        job['extraction_status'] = 'error'
        try:
            job['content'] = extractor.extract(content=job['raw_content'])
            job['extraction_status'] = 'success'
            enriched_jobs += 1
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

    logger.info("Enriched %d out of %d processed jobs.", enriched_jobs, len(jobs))

    # Write output
    if '://' not in args.output:
        os.makedirs(args.output, exist_ok=True)

    pq.write_table(
        table=pa.Table.from_pylist(jobs),
        where=os.path.join(args.output, "jobs.parquet")
    )
    logger.info('Wrote %s jobs to file.', len(jobs))


if __name__ == '__main__':
    main()
