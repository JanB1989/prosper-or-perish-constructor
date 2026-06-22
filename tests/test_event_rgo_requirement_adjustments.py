import re
from pathlib import Path

from eu5gameparser.load_order import LoadOrderConfig


ROOT = Path(__file__).resolve().parents[1]
MOD_ROOT = ROOT / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
EVENT_ROOT = MOD_ROOT / "in_game" / "events"

OVERRIDDEN_EVENT_FILES = (
    Path("DHE") / "flavor_HAB.txt",
    Path("DHE") / "flavor_OMA.txt",
    Path("DHE") / "flavor_dan.txt",
    Path("DHE") / "flavor_por.txt",
    Path("DHE") / "flavor_SWE.txt",
    Path("colonization") / "conquest_of_paradise.txt",
    Path("economy") / "prices.txt",
    Path("missionevents") / "generic_mission_events.txt",
)

OLD_WORKER_GATES = (
    "rgo_workers >= 6",
    "rgo_workers >= 5",
    "rgo_workers >= 3",
    "rgo_workers >= 2",
    "rgo_workers > 2",
    "rgo_workers > 1",
)
ACTIVE_WORKER_GATE_RE = re.compile(r"\brgo_workers\s*(?:>=|>|<=|<|=)\s*-?\d+")


def test_event_rgo_adjustments_override_vanilla_files_by_exact_path() -> None:
    assert not (EVENT_ROOT / "pp_rgo_requirement_event_adjustments.txt").exists()

    for relative_path in OVERRIDDEN_EVENT_FILES:
        assert (EVENT_ROOT / relative_path).is_file()


def test_event_rgo_adjustments_cover_all_active_non_debug_vanilla_worker_gates() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_event_root = load_order.vanilla_root / "game" / "in_game" / "events"
    active_gate_paths: set[Path] = set()

    for path in sorted(vanilla_event_root.rglob("*.txt")):
        relative_path = path.relative_to(vanilla_event_root)
        if relative_path.parts[0] == "debug":
            continue
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            content = line.split("#", 1)[0]
            if ACTIVE_WORKER_GATE_RE.search(content):
                active_gate_paths.add(relative_path)

    assert active_gate_paths == set(OVERRIDDEN_EVENT_FILES)


def test_event_rgo_adjustments_reduce_worker_gates_to_zero() -> None:
    combined_text = "\n".join(
        (EVENT_ROOT / relative_path).read_text(encoding="utf-8-sig")
        for relative_path in OVERRIDDEN_EVENT_FILES
    )

    assert combined_text.count("rgo_workers >= 0") == 12
    for old_gate in OLD_WORKER_GATES:
        assert old_gate not in combined_text
    assert "TRY_REPLACE:" not in combined_text
    assert "goods_output" not in combined_text
    assert "custom_tooltip = pp_" not in combined_text


def test_event_rgo_adjustments_keep_vanilla_good_checks() -> None:
    combined_text = "\n".join(
        (EVENT_ROOT / relative_path).read_text(encoding="utf-8-sig")
        for relative_path in OVERRIDDEN_EVENT_FILES
    )

    for expected in (
        "raw_material = goods:silver",
        "raw_material = goods:incense",
        "raw_material = goods:sugar",
        "raw_material = goods:cotton",
        "raw_material = goods:tobacco",
        "raw_material = goods:elephants",
    ):
        assert expected in combined_text


def test_event_rgo_adjustments_only_change_worker_thresholds() -> None:
    load_order = LoadOrderConfig.load(ROOT / "constructor.load_order.toml")
    vanilla_event_root = load_order.vanilla_root / "game" / "in_game" / "events"

    for relative_path in OVERRIDDEN_EVENT_FILES:
        vanilla_text = (vanilla_event_root / relative_path).read_text(encoding="utf-8-sig")
        expected = vanilla_text
        for old_gate in OLD_WORKER_GATES:
            expected = expected.replace(old_gate, "rgo_workers >= 0")

        assert (EVENT_ROOT / relative_path).read_text(encoding="utf-8-sig") == expected
