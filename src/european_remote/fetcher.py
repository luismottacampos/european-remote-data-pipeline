import json
import logging
import requests
import sys

from pprint import pprint

from redirect_resolver import RedirectResolver

# FIXME accept logging configuraiton parameters
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    stream=sys.stderr
)


logger = logging.getLogger()
resolver = RedirectResolver()

def resolve_job_urls(jobs, resolver=RedirectResolver()):
    for job in jobs:
        logger.info("Processing %s...", job['url'])
        direct_url = None
        if 'url' in job:
            try:
                direct_url = resolver.resolve(job['url'])
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    logger.warning("Job %s is no longer available. Ignoring.", job['url'])
                else:
                    raise
            if direct_url is not None and job['url'] != direct_url:
                logger.info("'%s' transformed into '%s'.", job['url'], direct_url)
        else:
            logger.warning("'%s' does not contain a 'url' field.", job)
        job['direct_url'] = direct_url
        yield job

for job in resolve_job_urls(json.load(sys.stdin.buffer)):
    pprint(job)
    print('='*120)
