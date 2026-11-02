from pathlib import Path

import polars as pl

from prosper_or_perish_constructor import run_report_budget as rb
from prosper_or_perish_constructor.run_report_budget_page import budget_page_html

PLAYTHROUGH = "run"


def _write(root: Path, table: str, snapshot: str, frame: pl.DataFrame) -> None:
    folder = root / "tables" / table / f"playthrough_id={PLAYTHROUGH}"
    folder.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(folder / f"{snapshot}.parquet")


def _estate(country: int, kind: str, **values: float) -> dict[str, object]:
    return {"country_id": country, "estate_type": kind, **{f: values.get(f, 0.0) for f in rb.ESTATE_FIELDS}}


def _dataset(root: Path) -> Path:
    """Country 1 holds locations 10 (a mill) and 11 (only its RGO); country 2 owns location 12 (no tax yet) and trades; country 3 is dead."""
    for snapshot, gold in (("old", 100.0), ("new", 160.0)):
        _write(root, "country_ai", snapshot, pl.DataFrame({
            "country_id": [1, 2, 3], "gold": [gold, 5.0, 900.0], "income": [80.0, 6.0, 70.0], "expense": [50.0, 4.0, 1.0], "total_debt": [7.0, 0.0, 0.0],
            "last_months_tax_income": [50.0, 0.0, 60.0], "monthly_trade_balance": [10.0, 4.0, 0.0], "last_months_tariff_income": [2.0, 0.0, 0.0],
            "last_months_foreign_building_income": [3.0, 0.0, 0.0]}))
    _write(root, "country_budget", "new", pl.DataFrame({
        "country_id": [1, 2], **{f"spent_{s}": [0.0, 0.0] for s in rb.SPENT if s not in ("upkeep", "army")},
        "spent_upkeep": [30.0, 1.0], "spent_army": [10.0, 1.0], "last_months_mercenary_maintenance": [5.0, 0.0]}))
    _write(root, "estate_ledger", "new", pl.DataFrame([
        _estate(1, "nobles_estate", gold=500.0, taxable_income=60.0, uncontrolled_income=20.0, trade_income=6.0, paid_taxes=30.0, pop_expense=40.0, balance=16.0),
        _estate(1, "peasants_estate", gold=1.0, taxable_income=40.0, paid_taxes=20.0, pop_expense=50.0, balance=-30.0),
        _estate(3, "nobles_estate", gold=5000.0, taxable_income=99.0, paid_taxes=33.0),
    ]))
    _write(root, "locations", "new", pl.DataFrame({
        "location_id": [10, 11, 12], "owner_country_id": [1, 1, 2], "tax": [50.0, 30.0, 0.0], "possible_tax": [60.0, 40.0, 0.0], "raw_material": ["wool", "iron", None],
        "total_population": [20.0, 10.0, 1.0], "macro_region": ["europe"] * 3, "super_region": ["europe"] * 3, "market_id": [1, 1, 1]}))
    _write(root, "location_estate_tax", "new", pl.DataFrame({
        "location_id": [10, 10, 11], "estate": ["nobles_estate", "peasants_estate", "peasants_estate"], "tax": [30.0, 20.0, 30.0]}))
    _write(root, "buildings", "new", pl.DataFrame({
        "building_id": [100, 101], "building_type": ["mill", "inn"], "location_id": [10, 10], "last_months_profit": [40.0, 10.0]}))
    _write(root, "production_method_good_flows", "new", pl.DataFrame({
        "building_id": [100, 100, 100, 101], "market_id": [1, 1, 1, 1], "good_id": ["cloth", "tools", "local_food", "logistics"],
        "direction": ["output"] * 4, "nominal_amount": [3.0, 1.0, 50.0, 2.0]}))
    _write(root, "market_goods", "new", pl.DataFrame({
        "market_id": [1, 1, 1, 1, 2], "good_id": ["cloth", "tools", "local_food", "logistics", "cloth"],
        "price": [1.0, 1.0, 0.1, 1.0, 3.0], "stockpile": [10.0, 0.0, 99.0, 99.0, 0.0]}))
    _write(root, "markets", "new", pl.DataFrame({"market_id": [1, 2], "center_location_id": [10, 10]}))
    _write(root, "trades", "new", pl.DataFrame({
        "good_id": ["cloth"], "size": [2.0], "from_market": [1], "to_market": [2], "country_id": [1], "happened": ["yes"]}))
    _write(root, "countries", "new", pl.DataFrame({"country_id": [1, 2], "country_tag": ["AAA", "BBB"], "country_name": ["A", "B"], "capital": [10, None]}))
    _write(root, "building_investment", "new", pl.DataFrame({"location_id": [10], "investment": [900.0]}))
    return root


def test_money_adds_up_per_country(tmp_path: Path) -> None:
    flows = rb.save_budget(_dataset(tmp_path), PLAYTHROUGH, "new", "old", 60)
    a = flows["country"].filter(pl.col("country_id") == 1).row(0, named=True)
    # income: named lines + the rest; spending: lines + mercenaries + the rest of the expense
    assert a["rest"] == 80.0 - 50.0 - 10.0 - 2.0 - 3.0
    assert a["other_budget"] == 50.0 - 30.0 - 10.0 - 5.0
    # the treasury grew by 60 gold in 60 months: of the 30 earned above the budget, 29 left it off the budget
    assert a["treasury"] == 1.0
    assert a["off_budget"] == 29.0
    assert a["capital"] == 900.0 and a["population"] == 30.0 and a["region"] is not None
    assert flows["stock"]["value"].sum() == 10.0  # no bookkeeping goods in the stock
    assert 3 not in flows["country"]["country_id"].to_list() and 3 not in flows["estates"]["country_id"].to_list()  # dead


def test_sources_close_on_the_ledger_and_the_state_tax(tmp_path: Path) -> None:
    flows = rb.save_budget(_dataset(tmp_path), PLAYTHROUGH, "new")
    sources = flows["sources"]
    assert abs(sources["tax_base"].sum() - (60.0 + 20.0 + 40.0)) < 1e-9  # scaled to taxable + uncontrolled income
    assert abs(sources["state_tax"].sum() - 50.0) < 1e-9  # what the estates paid
    by = {(g, b): v for g, b, v in sources.select("good_id", "building_type", "tax_base").iter_rows()}
    factor = 120.0 / 100.0
    # the mill's profit by the value of its real goods, not its Province Food; the inn has no good; RGOs take the rest
    assert abs(by[("cloth", "mill")] - 30.0 * factor) < 1e-9
    assert abs(by[("tools", "mill")] - 10.0 * factor) < 1e-9
    assert abs(by[(None, "inn")] - 10.0 * factor) < 1e-9
    assert abs(by[("wool", rb.RGO)] - 10.0 * factor) < 1e-9
    assert abs(by[("iron", rb.RGO)] - 40.0 * factor) < 1e-9


def test_profit_above_the_tax_base_shrinks_to_it() -> None:
    buildings = pl.DataFrame({"building_id": [1], "building_type": ["mill"], "location_id": [5], "last_months_profit": [30.0]})
    shares = pl.DataFrame({"building_id": [1], "good_id": ["cloth"], "share": [1.0]})
    locations = pl.DataFrame({"location_id": [5], "owner_country_id": [7], "tax": [10.0], "possible_tax": [20.0], "raw_material": ["iron"]})
    estate_tax = pl.DataFrame({"location_id": [5], "estate": ["nobles_estate"], "tax": [10.0]})
    estates = pl.DataFrame({"country_id": [7], "estate_type": ["nobles_estate"], "paid_taxes": [4.0], "taxable_income": [20.0], "uncontrolled_income": [0.0]})
    out = rb.tax_sources(buildings, shares, locations, estate_tax, estates)
    assert out.height == 1
    assert out["good_id"][0] == "cloth" and abs(out["tax_base"][0] - 20.0) < 1e-9 and abs(out["state_tax"][0] - 4.0) < 1e-9


def test_trade_spreads_the_booked_income_over_the_routes(tmp_path: Path) -> None:
    flows = rb.save_budget(_dataset(tmp_path), PLAYTHROUGH, "new")
    trade = {(c, g): v for c, g, v in flows["trade"].iter_rows()}
    assert abs(trade[(1, "cloth")] - (10.0 + 6.0)) < 1e-9  # the country's and its estates' trade income
    assert trade[(2, None)] == 4.0  # booked, but no route to spread it over


def test_a_save_without_the_estate_ledger_has_no_budget(tmp_path: Path) -> None:
    assert rb.save_budget(_dataset(tmp_path), PLAYTHROUGH, "old") is None


def test_budget_page_reads_its_data_files() -> None:
    page = budget_page_html("Run", (1337, 1837))
    assert "loadData('budget/index.js')" in page and "loadData('budget/summary.js')" in page
    assert "goods.html#g=" in page
