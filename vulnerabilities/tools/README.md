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
| `patch_detectors.py` | Fixes blind spots found in runs on several country repositories in the copy of global-law's scripts (`python -X utf8 patch_detectors.py <scripts dir>`; a fix already in place is skipped) |
| `redo.py` | Runs `patch_detectors.py`, then again only the scans and detectors the fixes change, the model review of lapsed time limits, references to deleted provisions and empty periods, and the build (`python -X utf8 redo.py <run folder> --fileact`; `EMBED_FONTS` names the script that embeds the chart's fonts) |
| `late_ext_check.py` | Hand-check helper: for each empty period that survived the review, the lines of the extending commit's diff that hold the old or the new date, in Czech and numeric forms |
| `measure_missed.py` | Counts the places where "do" is followed by a past date, month or year, which of them the time-limit search reads, and the forms of those it misses (the numbers in the READMEs) |

The model review needs `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_AUTH` set for an OpenAI-compatible Responses API.

Two changes to global-law's scripts were needed for a repository that keeps one file per act and now holds about 100,000 files:

- `ingest/refscan.py --fileact` looked up each file in a list of removed sections; it now uses a set, with the same output (the scan took 136 seconds here; with the list, the lookup grows with the number of files times the number of removed sections).
- `detectors/ref_detectors.py` reads `index/refs/*.parquet`, which the one-file-per-act scan never fills, so `run_czechia.sh` writes an empty table there; the per-folder `ingest/refscan.py` is not run.

The run was then repeated with `redo.py --fileact`. Of `patch_detectors.py`'s fixes, these change this repository's flags:

- Lapsed time limits also read numeric dates written with spaces ("31. 12. 2020") and the end of a year ("do konce roku
  2020"): 21,380 flags became 29,582. "nejpozději do" now counts as a deadline, which the empty-period detector leaves
  out: empty periods went from 352 to 386 (the new date forms add some; two the first run had, 227/2009 Sb. and a 1946
  notice in the Úřední list, are deadlines and left out).
- References read the Czech "a" between section numbers as "and" ("§ 1817 a 1826a", "§ 7 a § 11"), not as a range:
  references to deleted provisions went from 494 to 397.
- Currencies: "DM" counts only in capitals and as a word or after a decimal amount, and "franco", "lire" and "marco" only
  as whole words: dead currencies went from 594 to 137. The Belgian franc added in the same round brings 4 false matches
  here ("bef" ending a checksum or inside a link).
- Ties on score are broken by a hash of the row, so the 40 "strongest" flags of a category are the same in every run. They
  were drawn afresh for the three categories above and reviewed again; `build_czechia_vulns.py` now also links a
  retroactive-date flag to the commit that made the act's version on that day (none was flagged here). The other
  categories, and their reviews, did not change.
