"""Download ngspice Windows binary archive from SourceForge."""

import re
import html
import requests
import os

url = "https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/ngspice-47_64.7z/download"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

print("Fetching download page...")
session = requests.Session()
r = session.get(url, headers=headers)
print("Page status:", r.status_code)

match = re.search(r'<meta\s+http-equiv=["\']refresh["\']\s+content=["\']\d+;\s*url=([^"\']+)["\']', r.text, re.I)
if not match:
    print("Could not find refresh URL in page!")
    exit(1)

mirror_url = html.unescape(match.group(1))
print("Found direct mirror URL:", mirror_url)

print("Streaming archive...")
archive_resp = session.get(mirror_url, headers=headers, stream=True)
print("Archive status:", archive_resp.status_code)

target_path = "c:/CircuitLens/tools/ngspice.7z"
with open(target_path, "wb") as f:
    for chunk in archive_resp.iter_content(chunk_size=1048576):
        if chunk:
            f.write(chunk)

size_mb = os.path.getsize(target_path) / (1024 * 1024)
print(f"Downloaded successfully: {size_mb:.2f} MB saved to {target_path}")
