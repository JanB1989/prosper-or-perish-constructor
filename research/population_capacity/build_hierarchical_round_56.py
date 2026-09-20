"""Freeze one hierarchical evidence candidate; never use population as an input."""
from pathlib import Path
import hashlib
import json
import os
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT/'research/population_capacity'


def build():
    baseline = ROOT/'artifacts/data/population_simulation/repair_round_55/grouped_hyde/input/assignments.json'
    data = json.loads(baseline.read_text())
    data['source_hashes'] = {os.path.relpath((baseline.parent/k).resolve(), RESEARCH): v
                           for k, v in data.get('source_hashes', {}).items()}
    sources = ['hierarchical_management_round_56_evidence.json', 'java_bali_rice_presence_evidence.json',
               'eastern_java_rice_management_evidence.json', 'historical_system_observations.json']
    data['source_hashes'].update({name: hashlib.sha256((RESEARCH/name).read_bytes()).hexdigest() for name in sources})
    evidence=json.loads((RESEARCH/'hierarchical_management_round_56_evidence.json').read_text())
    cache=ROOT/'artifacts/data/population_capacity/repair_round_56/sources'
    for source in evidence['source_objects']:
        if source['status'] != 'downloaded':
            continue
        path=cache/source['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Research source object changed: '+str(path))
        data['source_hashes'][os.path.relpath(path,RESEARCH)] = source['sha256']
    data['status'] = 'round56 frozen hierarchical evidence experiment; no game export; not model acceptance'
    def assessment(scores, bounds, source):
        return dict(scores=scores, development_range=bounds, source_ids=[source])
    defaults = {
        'mixed_livelihood_uncertain': assessment([1,0,1,1], [6.25,31.25], 'round56_mixed_livelihood_uncertainty'),
        'cultivation_present': assessment([1,0,1,1], [6.25,31.25], 'round56_basic_maintained_cultivation'),
        'missing_evidence': assessment([1,0,1,1], [0,37.5], 'round56_missing_land_evidence'),
    }
    geography=pl.read_parquet(ROOT/'artifacts/data/population_simulation/repair_round_55/grouped_world/starting_ledger.parquet',columns=['province','region'])
    china_provinces=sorted(geography.filter((pl.col('region')=='east_china_region') &
        ~pl.col('province').str.contains('taiwan'))['province'].unique().to_list())
    gangetic_provinces=['arrah_province','patna_province','bhagalpur_province','darbhanga_province',
        'lower_kosi_province','east_gandak_province','west_gandak_province','bettiah_province',
        'gorakhpur_province','bahraich_province','upper_doab_province','central_doab_province',
        'lower_doab_province','braj_province','khairabad_province','azamgarh_province',
        'awadh_province','bareilly_province','lucknow_province','lower_ghaghara_province',
        'varanasi_province','rampur_rokhilkhand_province','budaun_province','manikpur_province',
        'delhi_province','nadia_province','pandua_province','gaur_province','bogra_province',
        'purnia_province','devkot_province']
    if set(gangetic_provinces)-set(geography['province']):
        raise ValueError('Historical plain crosswalk contains unknown provinces')
    rules = [
        dict(id='european_maintained_rotation_analogue', tier=1,
             selector={'macro_region':['western_europe','eastern_europe']},
             valid_years=[1200,1400], **assessment([2,0,1,1],[12.5,37.5],'round56_european_rotation_analogue')),
        dict(id='southern_chinese_maintained_cultivation', tier=2,
             selector={'province':china_provinces},
             valid_years=[1200,1400], **assessment([2,1,2,2],[31.25,56.25],'chen_pu_1149_regional_practice_analogue')),
        dict(id='gangetic_established_cultivation', tier=2,
             selector={'province':gangetic_provinces},
             valid_years=[1200,1400], **assessment([2,0,2,2],[25,50],'chakravarti_2008_early_medieval_agriculture')),
        dict(id='chola_maintained_fields', tier=3, selector={'province':['cola_nadu']},
             valid_years=[1200,1400], **assessment([3,1,2,2],[37.5,62.5],'heitzman_1987_chola_epigraphy')),
    ]
    data.pop('non_crop_management', None)
    data['management_hierarchy'] = dict(schema_version=1, defaults=defaults, rules=rules,
        recover_reconstructed_fields=True,
        contract='World uncertain livelihood/practice assessments, then dated regional and provincial analogues, then named systems. Cultivation presence selects applicability; neither hectares nor population scale development. Unknown is not foraging. Source potential classes never assign development in this candidate.')
    # Reuse the existing vetted crop-presence crosswalk, not a new island-wide mask.
    presence=json.loads((RESEARCH/'java_bali_rice_presence_evidence.json').read_text())
    tags=presence['records'][0]['location_tags']
    # Existing named systems win; broader practice inference fills uncovered sites.
    occupied=set()
    for s in data['systems']:
        occupied.update(s['selector'].get('location_tag', []))
    java_tags=sorted(set(tags)-occupied)
    data['systems'].append(dict(id='central_east_java_maintained_rice_analogue',
        selector={'location_tag':java_tags}, valid_years=[1200,1400], scores=[3,2,2,2],
        development_range=[43.75,68.75], source_ids=['christie_early_java_rice'],
        water_served_fraction_range=[.25,.75], recover_dated_cropland=True,
        interpretation='Regional maintained-field and water-service analogue on existing dated cultivation only; shared uncertainty, no added harvest or population fitting. Existing core assessments take precedence by excluding their tags.'))
    data['systems'].append(dict(id='kaveri_maintained_water_system',
        selector={'location_tag':['thanjavur','srirangam','tiruccirapalli','nagapattinam','jayankondam']},
        valid_years=[1200,1400], scores=[3,3,2,2], development_range=[50,75],
        source_ids=['heitzman_1987_chola_epigraphy'], water_served_fraction_range=[.25,.75],
        recover_dated_cropland=True,
        interpretation='Kaveri core regional analogue. Inscriptional system presence supports maintenance; selected game D and water-service fractions are uncertain inferences, not measured hectares. No whole-Deccan irrigation.'))
    data['systems'].append(dict(id='kyaukse_maintained_water_system',
        selector={'location_tag':['kyaukse']}, valid_years=[1200,1400], scores=[3,3,2,2],
        development_range=[50,75], source_ids=['aye_aye_than_2007_kyaukse'],
        water_served_fraction_range=[.25,.75], recover_dated_cropland=True,
        interpretation='Historical canal-system presence; shared uncertain managed-field assessment on existing reconstructed fields. No retrojection of colonial irrigated hectares or extension to all Burma.'))
    data['systems'].append(dict(id='red_river_embanked_fields',
        selector={'province':['thang_long_province','nam_sach_province','thien_truong_province']},
        valid_years=[1248,1400], scores=[3,3,2,2], development_range=[50,75],
        source_ids=['sakurai_1989_red_river_tran'], water_served_fraction_range=[.25,.75],
        recover_dated_cropland=True,
        interpretation='Delta-core shared management analogue based on Tran-period embankment research. Only existing dated cultivation is served; no entire-Vietnam entitlement or extra harvest. Modern/colonial dike length and hectares are excluded.'))
    output=RESEARCH/'historical_assignments_round_56.json'
    output.write_text(json.dumps(data,indent=2)+'\n')
    return output


if __name__ == '__main__':
    print(build())
