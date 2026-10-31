import re

with open('c:/CircuitLens/tools/ngspice.7z', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

print("Refresh tags:")
for m in re.finditer(r'<meta[^>]*refresh[^>]*>', html, re.I):
    print(m.group(0))

print("\nDirect download links in html:")
for link in re.findall(r'href=["\']([^"\']+\.7z[^"\']*)["\']', html):
    print(link)
