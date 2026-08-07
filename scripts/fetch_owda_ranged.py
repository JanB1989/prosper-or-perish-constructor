"""Fetch the large official OWDA NetCDF with verified byte ranges.

The NOAA endpoint supports HTTP range requests but a single request can be
cut off by the transport proxy.  Each chunk is checked against Content-Range,
then concatenated in order and checked against the declared file length.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen


URL = "https://www.ncei.noaa.gov/pub/data/paleo/treering/reconstructions/europe/owda.nc"
SIZE = 228_226_363
CHUNK = 16_000_000


def fetch_one(index: int, directory: Path) -> Path:
    start = index * CHUNK
    end = min(SIZE - 1, start + CHUNK - 1)
    target = directory / f"part_{index:03d}"
    request = Request(URL, headers={"Range": f"bytes={start}-{end}"})
    with urlopen(request, timeout=180) as response:
        content_range = response.headers.get("Content-Range", "")
        expected = f"bytes {start}-{end}/{SIZE}"
        if content_range != expected:
            raise RuntimeError(f"range_mismatch:{content_range!r}!={expected!r}")
        data = response.read()
    if len(data) != end - start + 1:
        raise RuntimeError(f"chunk_size_mismatch:{index}:{len(data)}")
    target.write_bytes(data)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    chunks = (SIZE + CHUNK - 1) // CHUNK
    directory = args.output.parent / (args.output.name + ".chunks")
    directory.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_one, i, directory) for i in range(chunks)]
        for future in futures:
            future.result()
    digest = hashlib.sha256()
    with args.output.open("wb") as output:
        for i in range(chunks):
            data = (directory / f"part_{i:03d}").read_bytes()
            output.write(data)
            digest.update(data)
    if args.output.stat().st_size != SIZE:
        raise RuntimeError(f"assembled_size_mismatch:{args.output.stat().st_size}")
    print(f"{args.output} {args.output.stat().st_size} {digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

