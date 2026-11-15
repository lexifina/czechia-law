# Tools

The scripts behind this Czechia-only run of global-law's vulnerability detectors. They run inside a copy of
[global-law/vulnerabilities/scripts](https://github.com/lexifina/global-law/tree/main/vulnerabilities/scripts) (Python 3.11+,
`pip install duckdb pyarrow`), with a bare clone of this repository at `sources/corpus/czechia-law.git`, a blobless bare
clone of global-law at `sources/global-law.git`, and a `pins.json` that names only czechia-law and its commit.

| Script | What it does |
| --- | --- |
| `run_czechia.sh` | Indexes the history and texts, adds Czechia's history rows, and runs the detectors that apply to Czechia |
| `add_root_czechia.py` | Builds Czechia's history rows from this repository's own commits (global-law replays it only up to an earlier commit), so the history detectors read every change |
| `run_triage.sh` | The model review: the 40 strongest flags per category, the 40 strongest lapsed time limits in law texts, and the empty periods |
| `late_ext_select.py` | Chooses the 40 empty periods for global-law's review of that category |
| `late_ext_rebut.py` | Adds the second, arguing-against pass to the empty-period review, as `triage.py` does for the other categories |
| `build_czechia_vulns.py` | Builds `data/flags.csv`, `data/reviewed.csv` and `data/by_category.csv` from the findings and the model review |
| `flags_chart.py` | Draws the chart at the top of the READMEs, in Czech and English, light and dark |

The model review needs `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_AUTH` set for an OpenAI-compatible Responses API.

Two changes to global-law's scripts were needed for a repository that keeps one file per act and now holds about 100,000 files:

- `ingest/refscan.py --fileact` looked up each file in a list of removed sections; it now uses a set, with the same output (the scan took 136 seconds here; with the list, the lookup grows with the number of files times the number of removed sections).
- `detectors/ref_detectors.py` reads `index/refs/*.parquet`, which the one-file-per-act scan never fills, so `run_czechia.sh` writes an empty table there; the per-folder `ingest/refscan.py` is not run.
