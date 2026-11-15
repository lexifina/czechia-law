#!/usr/bin/env bash
# Czechia-only run of global-law's vulnerability detectors (no sync: pins.json is written by hand for czechia-law).
cd "$(dirname "$0")"
export LE_WORKERS=6 LE_GREP_THREADS=6 PYTHONIOENCODING=utf-8 LE_PRIORITY=idle
P="C:/Python314/python.exe -X utf8"
set -x
$P ingest/extract.py && $P ingest/trailers.py
$P add_root_czechia.py
$P ingest/textscan.py && $P ingest/refscan.py --fileact czechia-law   # one file per act: the per-folder refscan does not apply
mkdir -p index/refs; $P -c "import duckdb; duckdb.sql(\"copy (select * from 'index/refs_fileact/czechia-law.parquet' limit 0) to 'index/refs/_none.parquet' (format parquet)\")"   # ref_detectors reads refs/*.parquet, which Czechia never fills
$P ingest/headings.py
$P detectors/trailer_only.py run; $P detectors/rank.py run; $P detectors/text_detectors.py run
$P detectors/ref_detectors.py run; $P detectors/placeholder_ref.py run; $P detectors/late_extension.py run
$P detectors/dead_fine.py run; $P detectors/notes_scan.py run
$P detectors/currency_scan.py run; $P detectors/dup_labels.py run
$P release/build_release.py out
echo DONE
