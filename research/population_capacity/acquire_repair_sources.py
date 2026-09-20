"""Download the repair's public sources, preserving bytes and provenance.

Run with ``uv run python research/population_capacity/acquire_repair_sources.py``.
Downloads are cached under artifacts; the small manifest is reviewable source.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "artifacts/data/population_capacity/repair_sources"
SERIES = ("land-use-over-the-long-term", "grazing-land-use-over-the-long-term")


def acquire() -> dict:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    records = []
    requests = [
        (f"{slug}.{extension}",
         f"https://ourworldindata.org/grapher/{slug}.{extension}?v=1&csvType=full&useColumnShortNames=false",
         "HYDE", "land transformation context; never independent population validation")
        for slug in SERIES for extension in ("csv", "metadata.json")
    ]
    requests.append(("madsen_robertson_ye_2019.pdf",
                     "https://api.research-repository.uwa.edu.au/ws/files/68455717/Malthus_Was_Right_Explaining_a_Millennium_of_Stagnation.pdf",
                     "European historical demographic studies", "adjustment-time comparison; Europe 900–1870"))
    requests.append(("hyde_grazing_full_metadata.json",
                     "https://api.ourworldindata.org/v1/indicators/1269906.metadata.json",
                     "HYDE", "provider version and licensing"))
    publications = [
        ("borsch_2014_maryut_basin.pdf", "https://www.ioa.uni-bonn.de/isl/de/forschung/publikationen/pdf-dateien-ask/ask-wp-14.pdf/@@download/file/ASK%20WP%2014.pdf",
         "Mamluk cadastral and irrigation records", "dated 1310 canal expansion and summer cropping; no per-location population fitting", "Bonn Annemarie Schimmel Kolleg working paper; cached for analysis, redistribution license unverified"),
        ("borsch_2000_nile_irrigation.pdf", "https://knowledge.uchicago.edu/records/6gbs3-fah93/files/MSR_IV_2000-Borsch.pdf?download=1",
         "Mamluk irrigation chronicles", "basin maintenance, flood timing and linked-system failure; compare chronology before applying to 1337", "CC BY 4.0; DOI 10.6082/M1R49NXD, confirmed in PDF copyright statement"),
        ("hawken_2014_angkor_fields.pdf", "https://cdn.angkordatabase.asia/libs/docs/publications/designs-of-kings-and-farmers-landscape-systems-of-the-greater-angkor-urban-complex/Designs_of_Kings_and_Farmers_Landscape_S.pdf",
         "Greater Angkor archaeological survey", "ricefield morphology and dated local hydraulic systems; related to Klassen's field-area evidence", "University of Hawaii Press copyright; cached for analysis, not redistributed"),
        ("suzhou_2026_water_management.html", "https://www.rddl.com.cn/EN/abstract/article/1001-5221/77454",
         "Chinese historical water-management records", "Tang-Song polder, drainage and flood-management mechanisms; availability is not area or adoption", "Tropical Geography journal copyright; cached for analysis, not redistributed"),
        ("klassen_2021_angkor_provisioning.pdf", "https://link.springer.com/content/pdf/10.1007/s10816-021-09535-5.pdf",
         "Greater Angkor archaeological survey", "dated ricefield extent and communal water management; geography must match the survey", "CC BY 4.0"),
        ("klassen_2021_angkor_supplement.docx", "https://media.springernature.com/original/springer-static/esm/art%3A10.1007%2Fs10816-021-09535-5/MediaObjects/10816_2021_9535_MOESM1_ESM.docx",
         "Greater Angkor archaeological survey", "agricultural infrastructure methods; same study, not independent validation", "CC BY 4.0"),
        ("li_2018_yuan_cropland.html", "https://www.geogsci.com/EN/abstract/article/1009-637X/40909",
         "Chinese historical land and household records", "1290 regional cropland reconstruction; population-dependent and not an independent demographic target", "Journal of Geographical Sciences copyright; cached for analysis, not redistributed"),
        ("li_2020_ming_cropland.html", "https://www.dlyj.ac.cn/EN/abstract/article/1000-0585/47073",
         "Chinese historical land and tax records", "1393 and 1583 corrected cropland; dated progression comparison, not a 1337 observation", "Geographical Research copyright; cached for analysis, not redistributed"),
        ("liu_1991_south_china_rice.pdf", "https://idv.sinica.edu.tw/ectjliu/%E5%8A%89%E7%BF%A0%E6%BA%B6%E5%AD%B8%E8%A1%93%E8%91%97%E4%BD%9C/W6-%E7%B6%93%E6%BF%9F%E5%8F%B22pdf/1991Rice%20Culture%20in%20South%20China.pdf",
         "Chinese agricultural historical records", "rice-wheat versus rice-rice calendars and intensification dates; 1500-1900 focus", "Author/journal copyright; cached for analysis, not redistributed"),
        ("water_rice_early_java_bali.pdf", "https://pure.mpg.de/rest/items/item_922657_3/component/file_3636125/content",
         "Old Javanese and Balinese inscriptions", "dated irrigated rice, canals and collective maintenance; no blanket regional yield coefficient", "Author/publisher copyright; cached for analysis, not redistributed"),
        ("hurtt_2020_luh2.pdf", "https://gmd.copernicus.org/articles/13/5425/2020/gmd-13-5425-2020.pdf",
         "LUH2/HYDE", "source semantics: grid-cell denominator and potential-biomass classes", "CC BY 4.0"),
        ("ma_2020_landcover_translation.pdf", "https://gmd.copernicus.org/articles/13/3203/2020/gmd-13-3203-2020.pdf",
         "LUH2/HYDE", "alternative land-use to land-cover interpretations; not an independent land-use validation", "CC BY 4.0"),
        ("bowman_rogan_1999_egypt.pdf", "https://www.thebritishacademy.ac.uk/documents/3871/96p001.pdf",
         "Egyptian agricultural history", "seasonal basin irrigation, cultivation and canal maintenance", "British Academy copyright; cached for analysis, not redistributed"),
        ("blaydes_2019_mamluk_land.pdf", "https://blaydes.people.stanford.edu/sites/g/files/sbiybj24621/files/media/file/land1.pdf",
         "Mamluk cadastral records", "dated assessed land; historical feddan and coverage audit", "SAGE/author copyright; cached for analysis, not redistributed"),
        ("sato_2004_mamluk_agriculture.pdf", "https://knowledge.uchicago.edu/records/qwvmm-bwf78/files/MSR_VIII-2_2004-Tsugitaka.pdf?download=1",
         "Mamluk documentary history", "dated Egyptian crop and water-management mechanisms", "CC BY 4.0"),
        ("pretty_1990_medieval_agriculture.pdf", "https://www.bahs.org.uk/AGHR/ARTICLES/38n1a1.pdf",
         "English manorial records", "low-input net crop yield check; Winchester 1283–1349", "Agricultural History Review copyright; cached for analysis, not redistributed"),
    ]
    licenses = {filename: license for filename, _, _, _, license in publications}
    requests.extend(item[:4] for item in publications)
    northeast = {
        "metadata.json": "https://api.figshare.com/v2/articles/25450468/versions/2",
        "readme.pdf": "https://ndownloader.figshare.com/files/45183079",
        "fractions.xlsx": "https://ndownloader.figshare.com/files/45183082",
        "paper.pdf": "https://essd.copernicus.org/articles/16/4971/2024/essd-16-4971-2024.pdf",
        **{name: "https://ndownloader.figshare.com/files/" + str(identifier) for name, identifier in {
            "1300.cpg": 45183172, "1300.dbf": 45183175, "1300.prj": 45183181,
            "1300.shp": 45183190, "1300.shx": 45183196,
            "1400.cpg": 45183151, "1400.dbf": 45183154, "1400.prj": 45183157,
            "1400.shp": 45183166, "1400.shx": 45183178,
            "1600.cpg": 45183100, "1600.dbf": 45183103, "1600.prj": 45183106,
            "1600.shp": 45183115, "1600.shx": 45183124,
        }.items()},
    }
    for name, url in northeast.items():
        filename = "jia_2024_northeast_v2/" + name
        requests.append((filename, url, "Northeast Chinese land and household records",
                         "dated regional counterexample to a blanket China uplift; population-derived land reconstruction, not independent demographic validation"))
        licenses[filename] = "CC BY 4.0; Figshare 10.6084/m9.figshare.25450468.v2 and ESSD article"
    gaez_assets = {
        "gaez_v5_2020_built_up.tif": "LR-LCC/GAEZ-V5.LR-LCC.LC01.tif",
        "gaez_v5_landcover_metadata.json": "LR-LCC/GAEZ-V5.LR-LCC.json",
        "gaez_v5_wheat_climate_rainfed.tif": "RES02-YLD/GAEZ-V5.RES02-YLD.HP8100.AGERA5.HIST.WHEA.LRLM.tif",
        "gaez_v5_wheat_climate_irrigated.tif": "RES02-YLD/GAEZ-V5.RES02-YLD.HP8100.AGERA5.HIST.WHEA.LILM.tif",
        "gaez_v5_climate_yield_metadata.json": "RES02-YLD/GAEZ-V5.RES02-YLD.json",
    }
    for filename, asset in gaez_assets.items():
        requests.append((filename, "https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET/" + asset,
                         "FAO/IIASA GAEZ v5", "diagnose modern land-mask effects; not medieval capacity or calibration labels"))
        licenses[filename] = "FAO dataset terms require verification before redistribution; analysis cache only"
    for filename, url, family, role in requests:
        path = DESTINATION / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            try:
                with urlopen(Request(url, headers={"User-Agent": "Population capacity research/1.0"}), timeout=60) as response:
                    data = response.read()
            except (HTTPError, URLError, TimeoutError) as error:
                records.append({"id": filename, "url": url, "source_family": family, "role": role,
                                "status": "download_unavailable", "reason": str(error),
                                "license": licenses.get(filename, "see provider metadata")})
                continue
            # Never mistake an HTML error page for a dataset.
            if filename.endswith(".pdf") and not data.startswith(b"%PDF"):
                raise ValueError(f"not a PDF: {url}")
            if filename.endswith(".json"):
                json.loads(data)
            if filename.endswith((".docx", ".xlsx")) and not data.startswith(b"PK"):
                raise ValueError(f"not an Office ZIP document: {url}")
            if filename.endswith(".csv") and b"Entity,Code,Year" not in data[:100]:
                raise ValueError(f"not an OWID CSV: {url}")
            temporary = path.with_suffix(path.suffix + ".part")
            temporary.write_bytes(data)
            temporary.replace(path)
        records.append({"id": filename, "url": url, "path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
                        "status": "cached_verified",
                        "source_family": family, "role": role,
                        "source_version": ("Figshare 25450468 version 2 (Jia et al., 2024)" if filename.startswith("jia_2024_northeast_v2/")
                                           else "HYDE 3.5, OWID release 2026-06-08" if family == "HYDE"
                                           else "GAEZ v5" if family == "FAO/IIASA GAEZ v5"
                                           else "publication identified by URL and content hash"),
                        "license": licenses.get(filename, "HYDE 3.5: CC BY-NC 4.0; OWID processing: CC BY 4.0" if family == "HYDE" else "Copyright Elsevier 2019; cached for analysis, not redistributed"),
                        "units": ("cropland/grazing: hectares; convert hectares to km2 by dividing by 100" if filename.endswith('.csv')
                                  else "percentage of 30 arc-second cell" if filename == 'gaez_v5_2020_built_up.tif'
                                  else "crop yield; resolve scale/units from cached GAEZ metadata" if filename.endswith('.tif')
                                  else "source document/metadata"),
                        "transformations": "none; original downloaded bytes"})
    manifest_path = Path(__file__).parent / "repair_source_manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    payload = {"schema_version": 1, "retrieved_at": previous.get('retrieved_at', datetime.now(timezone.utc).isoformat()),
               "verified_at": datetime.now(timezone.utc).isoformat(), "hyde_owid_version": "HYDE 3.5 (2025), OWID 2026-06-08 release",
               "sources": records, "independence": "OWID cropland/grazing, HYDE rasters, and HYDE population share a reconstruction family; LUH land-use products also inherit HYDE inputs."}
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(acquire(), indent=2))
