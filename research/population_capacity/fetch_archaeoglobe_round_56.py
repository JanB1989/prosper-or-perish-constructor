"""Restore the pinned public data cache used by the round56 historical prior."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import requests

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT/'research/population_capacity'
CACHE=ROOT/'artifacts/data/population_capacity/repair_round_56/sources/archaeoglobe'


def main():
    sources=json.loads((RESEARCH/'archaeoglobe_source_objects.json').read_text())
    CACHE.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        target=CACHE/item['file']
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==item['sha256']:
            return
        url=f"https://raw.githubusercontent.com/benmarwick/ArchaeoGLOBE/{item['commit']}/{item['path']}"
        response=requests.get(url,timeout=60);response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest()!=item['sha256']:
            raise ValueError('Pinned upstream object changed: '+url)
        target.write_bytes(response.content)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch,sources))
    (CACHE/'manifest.json').write_text(json.dumps(sources,indent=2))
    print(f'Verified {len(sources)} pinned upstream objects; data CC0, attribution requested.')


if __name__=='__main__':main()
