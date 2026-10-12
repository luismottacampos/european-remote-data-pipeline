import sys
import io
import re
import email.parser
import email.message

from bs4 import BeautifulSoup


# filename:str = "sample.eml"
# with io.open(filename, mode="rb") as fh:
#     m:email.message.Message = email.parser.BytesParser().parse(fh)

m:email.message.Message = email.parser.BytesParser().parse(sys.stdin.buffer)

if m.is_multipart():
    raise ValueError("Multi-Part Mime messages not supported")

payload = bytes(m.get_payload(decode=True)).decode(encoding=m.get_content_charset() or "utf-8")

soup = BeautifulSoup(payload, "html.parser")

employer_re = re.compile(r'\(at (?P<employer>[^\)]+)\)')

jobs = [
    {
        "url": link['href'],
        "title": link.span.string,
        "raw_employer": (raw := link.span.next_sibling.next_sibling.string),
        "employer": mo.group("employer") if (mo := employer_re.search(raw)) else None,

    }
    for link in soup.css.select("li a")
]

from pprint import pprint
pprint(jobs)
