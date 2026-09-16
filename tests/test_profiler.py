import csv
import json
from pathlib import Path

import pytest

from prosper_or_perish_constructor import cli, profiler


HEADER = ["File Location", "Bottleneck Time", "Call Count", "Max Time", "Min Time",
          "Self Time", "Total Time", "Average Time (Inclusive)", "Average Time (Exclusive)"]


def dump(path: Path, rows, delimiter=";"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def row(label, self_time=2, total=5, calls=10):
    return [label, 1, calls, .7, .01, self_time, total, 0, 0]


def test_separate_views_duplicate_aggregation_and_rounded_averages(tmp_path):
    dump(tmp_path / "profiling.csv", [row("trigger @ common/a.txt:2", 9)])
    second = row("trigger @ common/a.txt:2", 3, 8, 20)
    second[3:5] = [1.2, .005]
    dump(tmp_path / "profiling_roots.csv", [row("trigger @ common/a.txt:2"), second])
    capture = profiler.read_capture(tmp_path)
    assert capture["datasets"]["summary"]["self_sum"] == 9
    detail = capture["datasets"]["detail"]
    assert detail["duplicates"] == 1
    assert detail["self_sum"] == 5
    node = detail["nodes"][0]
    assert (node["calls"], node["total"], node["rows"], node["max"], node["min"]) == (30, 13, 2, 1.2, .005)


@pytest.mark.parametrize("delimiter", [";", ",", "\t"])
def test_bom_delimiters_and_unknown_labels(tmp_path, delimiter):
    capture = profiler.read_csv(dump(tmp_path / "input.csv", [row("unknown profiler label")], delimiter))
    assert capture["nodes"][0]["file"] == "<unknown>"


@pytest.mark.parametrize("bad", ["NaN", "inf", "-1", "not a number"])
def test_bad_metrics_fail_with_line_number(tmp_path, bad):
    invalid = row("trigger @ a.txt:1")
    invalid[5] = bad
    with pytest.raises(ValueError, match="input.csv:2"):
        profiler.read_csv(dump(tmp_path / "input.csv", [invalid]))


def test_large_integer_counts_preserved(tmp_path):
    count = 2**54 + 3
    data = profiler.read_csv(dump(tmp_path / "input.csv", [row("trigger @ a.txt:1", calls=count)]))
    assert data["nodes"][0]["calls"] == count


def test_missing_and_empty_input_are_actionable(tmp_path):
    with pytest.raises(ValueError, match="No profiling"):
        profiler.read_capture(tmp_path)
    path = tmp_path / "bad.csv"
    path.write_text("name;duration\nx;1\n")
    with pytest.raises(ValueError, match="missing columns"):
        profiler.read_csv(path)
    with pytest.raises(ValueError, match="no measurement rows"):
        profiler.read_csv(dump(path, []))


def test_inferred_ancestry_and_cross_file_reference(tmp_path):
    root = tmp_path / "game"
    file = "common/scripted_triggers/demo.txt"
    other = "common/scripted_triggers/other.txt"
    (root / "common/scripted_triggers").mkdir(parents=True)
    (root / file).write_text('outer = {\n  AND = {\n    inner = yes\n  }\n}\n')
    (root / other).write_text('inner = {\n  always = yes\n}\n')
    dataset = profiler.read_csv(dump(tmp_path / "profiling_roots.csv", [
        row(f"trigger @ {file}:2"), row(f"trigger @ {file}:3"), row(f"trigger @ {other}:2")]))
    sources, warnings = profiler.build_source_index({file, other}, [("example_mod", root)])
    assert not warnings
    profiler.enrich_dataset(dataset, sources)
    assert (0, 1, "contains") in dataset["edges"]
    target = next(i for i, n in enumerate(dataset["nodes"]) if not n["measured"] and n["symbol"] == "inner")
    assert (1, target, "reference") in dataset["edges"]
    assert (target, 2, "contains") in dataset["edges"]
    assert dataset["nodes"][1]["symbol"] == "outer"
    assert dataset["nodes"][1]["origin"] == "example_mod"
    assert dataset["self_sum"] == 6  # definition anchors do not contribute


def test_ambiguous_line_does_not_invent_parent_edge(tmp_path):
    file = "common/test.txt"
    (tmp_path / "common").mkdir()
    (tmp_path / file).write_text('root = { AND = { always = yes } }\n')
    sources, _ = profiler.build_source_index({file}, [("test", tmp_path)])
    dataset = profiler.read_csv(dump(tmp_path / "input.csv", [row(f"trigger @ {file}:1")]))
    profiler.enrich_dataset(dataset, sources)
    assert dataset["edges"] == []
    assert dataset["ambiguous_source_rows"] == 1


def test_shared_location_has_separate_measurements_and_source_parent(tmp_path):
    file = "a.txt"
    (tmp_path / file).write_text('root = {\n  limit = {\n    count > 1\n  }\n}\n')
    sources, _ = profiler.build_source_index({file}, [("test", tmp_path)])
    dataset = profiler.read_csv(dump(tmp_path / "input.csv", [
        row(f"trigger @ {file}:2"), row(f"trigger @ {file}:3"), row(f"script_value @ {file}:3")]))
    profiler.enrich_dataset(dataset, sources)
    anchor = next(i for i, n in enumerate(dataset["nodes"]) if n["line"] == 3 and not n["measured"])
    assert (0, anchor, "contains") in dataset["edges"]
    assert (anchor, 1, "measurement") in dataset["edges"]
    assert (anchor, 2, "measurement") in dataset["edges"]
    assert dataset["self_sum"] == 6


def test_local_declarations_and_arithmetic_preserve_lines_and_strings(tmp_path):
    text = ('# scripted_effect comment = {\n'
            'name = "scripted_trigger quoted = { @[ untouched ]"\n'
            '@width = @[ ( 1 + 2 ) / 3 ]\n'
            'scripted_trigger local_check = {\n'
            '  always = yes\n}\n'
            'event = {\n  trigger = {\n    local_check = yes\n  }\n}\n')
    masked, declarations = profiler.prepare_source(text)
    assert declarations == [4]
    assert len(masked) == len(text)
    assert masked.splitlines()[:2] == text.splitlines()[:2]
    (tmp_path / "events.txt").write_text(text)
    sources, warnings = profiler.build_source_index({"events.txt"}, [("test", tmp_path)])
    assert not warnings
    dataset = profiler.read_csv(dump(tmp_path / "input.csv", [row("trigger @ events.txt:9"), row("trigger @ events.txt:5")]))
    profiler.enrich_dataset(dataset, sources)
    target = next(i for i, n in enumerate(dataset["nodes"]) if n["line"] == 4)
    assert (0, target, "reference") in dataset["edges"]


def test_parse_failure_keeps_measurements_and_source(tmp_path):
    (tmp_path / "broken.txt").write_text("root = {\n")
    sources, warnings = profiler.build_source_index({"broken.txt"}, [("test", tmp_path)])
    assert len(warnings) == 1
    assert sources["broken.txt"]["lines"] == ["root = {"]
    assert sources["broken.txt"]["entries"] == []


def test_roots_last_wins_and_paths_cannot_escape(tmp_path):
    vanilla, mod = tmp_path / "vanilla", tmp_path / "mod"
    for root in (vanilla, mod):
        (root / "in_game/common").mkdir(parents=True)
        (root / "in_game/common/a.txt").write_text("x = yes")
    roots = [("vanilla", vanilla), ("my_mod", mod)]
    assert profiler.resolve_source("common/a.txt", roots)[0] == "my_mod"
    for path in ("../mod/in_game/common/a.txt", str(mod / "in_game/common/a.txt"), "C:/secret.txt"):
        assert profiler.resolve_source(path, roots) is None


def test_performance_rows_and_malformed_sample(tmp_path):
    path = tmp_path / "performance_degradation.log"
    path.write_text('"Total Time",\t\t "Average Delta",\t\t "MaxDelta" ,"Memory Usage (MB)","Game Data"\n'
                    '10,0.025,0.1,1000,1337_01_01\ninvalid,0,0,1000,x\n')
    result = profiler.read_performance(path)
    assert result["rows"][0]["average_frame_seconds"] == .025
    assert result["rows"][0]["date"] == "1337_01_01"
    assert len(result["warnings"]) == 1


def test_empty_performance_log_is_reported(tmp_path):
    path = tmp_path / "performance_degradation.log"
    path.touch()
    assert "no usable samples" in profiler.read_performance(path)["warnings"][0]


def test_default_logs_local_override_and_windows_paths(tmp_path):
    (tmp_path / "constructor.local.toml").write_text('[profiler]\nlogs_dir = "my-logs"\n')
    assert profiler.default_logs(tmp_path) == tmp_path / "my-logs"
    if profiler.os.name != "nt":
        assert profiler.host_path(r"C:\Users\Some Person\logs", tmp_path) == Path("/mnt/c/Users/Some Person/logs")


def test_cli_exports_offline_report_with_baseline(tmp_path):
    (tmp_path / "constructor.toml").write_text('name = "test"\n')
    capture = tmp_path / "capture"
    baseline = tmp_path / "baseline"
    dump(capture / "profiling.csv", [row("trigger @ common/a.txt:1", 4)])
    dump(baseline / "profiling.csv", [row("trigger @ common/a.txt:1", 2)])
    assert cli.main(["--repo", str(tmp_path), "profiler", str(capture), "--baseline", str(baseline),
                     "--label", "</script><script>evil()</script>"]) == 0
    output = next((tmp_path / "graphs/profiler").iterdir())
    payload = json.loads((output / "profile.json").read_text())
    assert payload["datasets"]["summary"]["self_sum"] == 4
    assert payload["baseline"]["datasets"]["summary"]["self_sum"] == 2
    html = (output / "index.html").read_text()
    assert "evil()" not in html
    assert "__PROFILE_GZIP_BASE64__" not in html
    with (output / "hotspots_summary.csv").open() as stream:
        record = next(csv.DictReader(stream))
    assert float(record["self_per_call"]) == .4
    assert payload["datasets"]["summary"]["edges"] == []
    assert (output / "inputs/profiling.csv").read_bytes() == (capture / "profiling.csv").read_bytes()
    assert (output / "baseline_inputs/profiling.csv").read_bytes() == (baseline / "profiling.csv").read_bytes()


def test_cli_rejects_extra_args_and_implicit_source_profile(tmp_path):
    (tmp_path / "constructor.toml").write_text('name = "test"\n')
    with pytest.raises(SystemExit, match="unrecognized arguments"):
        cli.main(["--repo", str(tmp_path), "profiler", "--typo"])
    with pytest.raises(SystemExit, match="requires an explicit --profile"):
        cli.main(["--repo", str(tmp_path), "profiler", "--load-order", "x.toml"])


def test_repeated_cli_runs_preserve_reports_and_accept_report_as_baseline(tmp_path):
    (tmp_path / "constructor.toml").write_text('name = "test"\n')
    capture = tmp_path / "capture"
    summary = dump(capture / "profiling.csv", [row("trigger @ a.txt:1")])
    dump(capture / "profiling_roots.csv", [row("trigger @ a.txt:2")])
    assert cli.main(["--repo", str(tmp_path), "profiler", str(capture)]) == 0
    first = next((tmp_path / "graphs/profiler").iterdir())
    original = (first / "profile.json").read_bytes()
    assert cli.main(["--repo", str(tmp_path), "profiler", str(summary), "--baseline", str(first)]) == 0
    outputs = list((tmp_path / "graphs/profiler").iterdir())
    assert len(outputs) == 2
    second = next(path for path in outputs if path != first)
    assert (first / "profile.json").read_bytes() == original
    assert (first / "inputs/profiling_roots.csv").is_file()
    assert not (second / "inputs/profiling_roots.csv").exists()
    assert json.loads((second / "profile.json").read_text())["baseline"]["datasets"]["detail"]["raw_rows"] == 1


def test_timestamp_directory_collisions_are_safe(tmp_path, monkeypatch):
    actual_datetime = profiler.datetime

    class Clock:
        @staticmethod
        def now(zone):
            return actual_datetime(2026, 9, 16, 12, 30, tzinfo=zone)

    monkeypatch.setattr(profiler, "datetime", Clock)
    first = profiler.new_report_directory(tmp_path, "../../mod: run")
    second = profiler.new_report_directory(tmp_path, "../../mod: run")
    assert first.name == "mod-run-20260916T123000.000000Z"
    assert second.name == first.name + "-1"
    assert first.parent == tmp_path
