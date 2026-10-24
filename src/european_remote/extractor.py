import sys
import re
import email.parser
import email.message
import json

from bs4 import BeautifulSoup

m:email.message.Message = email.message_from_binary_file(sys.stdin.buffer)

if m.is_multipart():
    raise ValueError("Multi-Part Mime messages not supported")

payload = bytes(m.get_payload(decode=True)
                ).decode(encoding=m.get_content_charset() or "utf-8")

soup = BeautifulSoup(payload, "html.parser")

employer_re = re.compile(r'\(at (?P<employer>[^\)]+)\)')

jobs = [
    {
        "url": link['href'],
        "raw_title": link.span.string,
        "raw_employer": (
            raw_employer := link.span.next_sibling.next_sibling.string
        ),
        "employer": (
            mo.group("employer")
            if (mo := employer_re.search(raw_employer))
            else None
        ),
    }
    for link in soup.css.select("li a")
]

json.dump(obj=jobs, fp=sys.stdout)
