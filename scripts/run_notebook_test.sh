#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
LOG="artifacts/notebook_kernel_test.log"
mkdir -p artifacts
{
  echo "=== venv python ==="
  .venv/bin/python --version
  echo "=== imports ==="
  uv run python -c 'import ipykernel, eu5gameparser; print("ipykernel", ipykernel.__version__)'
  echo "=== kernelspec list ==="
  uv run python -m jupyter kernelspec list
  echo "=== execute setup cell ==="
  uv run python - <<'PY'
import importlib
from eu5gameparser.savegame import notebook_workbench as wb
wb = importlib.reload(wb)

DATA_ROOT = None
LOAD_ORDER_PATH = None
PLAYTHROUGH = None
START_DATE = None
END_DATE = None
SNAPSHOT_DATE = None
GOOD_SEARCH = "victuals"
MARKET_SEARCH = None
BUILDING_SEARCH = "cookery"
PM_DRILLDOWN_SEARCH = None
COUNTRY_SEARCH = "england"
GROUP_BY = "super_region"
BUILDING_SCOPE = "super_region"
FLOW_GROUP_BY = ("flow_table", "market")
CONSUMPTION_GROUP_BY = "bucket"
IMBALANCE_SORT = "mean_flow"
AGG = "sum"
TOP_N = 6
BUCKET_YEARS = 25
START_YEAR = 1337
POPULATION_METRIC = "total_population"
FOOD_RANK_BY = "food_fill_ratio"
BUILDING_METRIC = "level"

workbench = wb.open_workbench(wb.WorkbenchConfig.from_mapping(globals()))
print("workbench_ok", len(workbench.snapshots), "snapshots")
PY
  echo "=== nbconvert execute (first pass) ==="
  uv run jupyter nbconvert \
    --to notebook \
    --execute graphs/savegame_notebooks/savegame_analysis_workbench.ipynb \
    --output artifacts/savegame_analysis_workbench.executed.ipynb \
    --ExecutePreprocessor.kernel_name=prosper-or-perish-constructor \
    --ExecutePreprocessor.timeout=600
  echo "=== SUCCESS ==="
} >"$LOG" 2>&1
