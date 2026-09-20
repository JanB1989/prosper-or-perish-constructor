"""Flatten evaluated acceptance evidence without confusing diagnostic and gate status."""
import argparse
import json
from pathlib import Path
import polars as pl
from prosper_or_perish_constructor.simulation.cache import fingerprint


def run(output: Path):
    acceptance = json.loads((output / "acceptance.json").read_text())
    identity = acceptance["input_fingerprint"]
    groups, rows = [], []
    sources = [output / "acceptance.json"]
    for source in sorted((output / "evidence").glob("*.json")):
        evidence = json.loads(source.read_text())
        if evidence["input_fingerprint"] != identity:
            raise ValueError(f"Stale evidence: {source}")
        sources.append(source)
        group = evidence["requirement"]
        groups.append(dict(requirement=group, status=evidence["status"],
            missing_cases=evidence.get("missing_cases", []), evidence=str(source)))
        for index, case in enumerate(evidence.get("cases", [])):
            name = case.get("name", f"case_{index}")
            horizons = case.get("horizons", [])
            for horizon in horizons:
                year = horizon["year"]
                checks = [c for c in case.get("checks", []) if c.get("horizon", year) == year]
                booleans = [c["passed"] for c in checks if isinstance(c.get("passed"), bool)]
                status = ("failed" if not all(booleans) else "passed") if booleans else "not evaluated"
                rows.append(dict(requirement=group, case=name, year=year,
                    horizon_status=status, case_status=case["status"],
                    failed_checks="; ".join(c["name"] for c in checks if c.get("passed") is False),
                    **{k: v for k, v in horizon.items() if k not in ("year", "status")}))
    table = pl.from_dicts(rows, infer_schema_length=None)
    table.write_csv(output / "evaluated_horizon_criteria.csv")
    for directory in ('mechanism_controls', 'frozen_mechanism_controls'):
        history_path=output/directory/'food_scenario_history.parquet'
        if not history_path.exists():
            continue
        sources.append(history_path)
        history=pl.read_parquet(history_path)
        start=history.filter(pl.col('month')==0).select('scenario',pl.col('population').alias('starting_population'))
        growth=history.filter(pl.col('month').is_in([300,1200,2400])).join(start,on='scenario',validate='m:1').with_columns(
            (pl.col('month')/12).cast(pl.Int64).alias('year'),
            (pl.col('population')/pl.col('starting_population')).alias('population_ratio'),
            (pl.col('food_growth_cap_months')/pl.col('month')).alias('share_months_at_food_growth_cap'))
        growth=growth.with_columns((pl.col('population_ratio').pow(12/pl.col('month'))-1).alias('population_cagr'))
        growth.select('scenario','year','starting_population','population','population_ratio','population_cagr',
            'fill','food_growth_cap_months','share_months_at_food_growth_cap','net_annualized_growth',
            'doubling_time_years','doubling_time_defined').write_csv(output/f'{directory}_growth_summary.csv')
    report = dict(model_accepted=acceptance["model_accepted"], input_fingerprint=identity,
        groups=groups, evidence_summary_fingerprint=fingerprint([__file__, *sources], {}))
    (output / "evaluated_criteria_register.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Evaluated acceptance criteria", "", "Statuses below describe the actual evidence groups; survival screens alone do not certify historical geography.", "",
             "| Requirement | Status | Remaining coverage |", "|---|---|---|"]
    for group in groups:
        lines.append(f"| {group['requirement']} | {group['status']} | {'; '.join(group['missing_cases'])} |")
    lines += ["", "The companion `evaluated_horizon_criteria.csv` evaluates each horizon from its own checks. Diagnostic-only population tables must not be read as healthy-control passes.", ""]
    (output / "evaluated_criteria_register.md").write_text("\n".join(lines))
    print(table.group_by("requirement", "horizon_status").len().sort("requirement", "horizon_status"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
