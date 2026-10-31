"""Download and extract conda-forge ngspice .tar.bz2 for win-64."""

import requests
import tarfile
import os

url = "https://conda.anaconda.org/conda-forge/win-64/ngspice-exe-36-h7a24507_6.tar.bz2"
lib_url = "https://conda.anaconda.org/conda-forge/win-64/ngspice-38-h57928b3_0.tar.bz2"

tools_dir = "c:/CircuitLens/tools/ngspice"
os.makedirs(tools_dir, exist_ok=True)

for u in [url, lib_url]:
    fname = u.split("/")[-1]
    local_path = os.path.join(tools_dir, fname)
    print(f"Downloading {fname}...")
    r = requests.get(u, stream=True)
    with open(local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1048576):
            if chunk:
                f.write(chunk)
    print(f"Extracting {fname} ({os.path.getsize(local_path)} bytes)...")
    with tarfile.open(local_path, "r:bz2") as tar:
        tar.extractall(tools_dir)

print("Files in tools_dir:")
for root, dirs, files in os.walk(tools_dir):
    for f in files:
        if f.endswith(".exe") or f.endswith(".dll"):
            print(os.path.join(root, f))
