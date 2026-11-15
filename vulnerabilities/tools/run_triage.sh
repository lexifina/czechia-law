#!/usr/bin/env bash
# The model review of the Czechia-only run (gpt-5.4-mini through an OpenAI-compatible Responses API; see llm_env.sh).
cd "$(dirname "$0")"
source ./llm_env.sh
export PYTHONIOENCODING=utf-8
P="C:/Python314/python.exe -X utf8"
$P triage/triage.py run --per 40 --workers 12                              # 40 strongest per category
mkdir -p findings/runlaw && $P -c "import duckdb; duckdb.sql(\"copy (select * from 'findings/run/ranked_lapsed_limit.parquet' where not regexp_matches(path, '^(navrhy|caselaw|usneseni-vlady|vestnik|metodika|data|tools)/')) to 'findings/runlaw/ranked_lapsed_limit.parquet' (format parquet)\")"
$P triage/triage.py runlaw --per 40 --workers 12 --dets lapsed_limit       # lapsed limits: 40 strongest in law texts
$P ../../../late_ext_select.py && $P triage/late_ext_triage.py run         # empty periods: global-law's own review
$P ../../../late_ext_rebut.py                                              # ... and the same rebuttal step
echo TRIAGE DONE
