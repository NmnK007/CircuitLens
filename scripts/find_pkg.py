import requests
import re

r = requests.get('https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-ngspice')
print('Status:', r.status_code)
links = re.findall(r'href="([^"]+\.pkg\.tar\.[^"]+)"', r.text)
for l in links:
    print('Found link:', l)
