# How this repository was made

Everything needed to rebuild it, byte for byte, from e-Sbírka's open data.

## Sources

e-Sbírka's open datasets, https://opendata.eselpoint.cz/datove-sady-esbirka (Ministerstvo vnitra ČR; refreshed
daily), downloaded once on 2026-10-28 with `curl -C -` (resumable), 4 at a time, User-Agent
`Lexifina-czechia-law/1.0 (czechia-law@lexifina.com)`. 45 files, 2.3 GB; one request each, plus one HEAD each for the
headers. opendata.eselpoint.cz serves no robots.txt (404). The terms of use were read first, from the National Open
Data Catalogue's SPARQL endpoint (https://data.gov.cz/sparql): see [`LICENSE`](LICENSE). The build reads six files:

| File | Bytes | sha256 | Last-Modified |
| --- | --- | --- | --- |
| `001PravniAktZneni.json.gz` | 178053461 | `9f10e4587a041ff291d38dffc2295e8700bbbcb7e25a203b1eb4f16ca1d910ed` | Wed, 28 Oct 2026 02:30:00 GMT |
| `002PravniAkt.json.gz` | 5421404 | `c3b0b5071e43c01b42966e19624ae8e40d3aa527cd931f7640808e90ae4750c3` | Wed, 28 Oct 2026 01:57:52 GMT |
| `003PravniAktZneniFragment.json.gz` | 1246083285 | `03722fbe7e38a6d44afedf577d5f7ce9413da12b104f3b95292f662aa533a309` | Wed, 28 Oct 2026 04:02:11 GMT |
| `004PravniAktFragment.json.gz` | 531633370 | `d5aa295116d9dfdd28a9859f405c84d48cd15189d8ec7cfac5eba546b3ca2a74` | Wed, 28 Oct 2026 01:45:24 GMT |
| `006PravniAktMetadata.json.gz` | 6253458 | `b8571422448ab3727c25ccdda0faadd947c59a189184750685eb1d76eb973042` | Wed, 28 Oct 2026 03:21:57 GMT |
| `007PravniAktKonsolidacniVazba.json.gz` | 19957583 | `ab8a079478f9123c014e9004bfc1107dae3c104821a5a1f6e147d25eb967f4a5` | Wed, 28 Oct 2026 02:03:01 GMT |

The other 39 files (code lists, CzechVOC, references) were downloaded and hashed but are not read.

## Commands

```
# 1. download (scripts/czechia-law/fetch.sh in the Lexifina monorepo), then check sizes against Content-Length
bash fetch.sh 001PravniAktZneni.json.gz ... 045CiselnikSablonaObsahu.json.gz
sha256sum *.json.gz; gzip -t *.json.gz
# 2. decompress once, so workers can parse byte ranges in parallel
for f in 001PravniAktZneni 002PravniAkt 003PravniAktZneniFragment 004PravniAktFragment 006PravniAktMetadata 007PravniAktKonsolidacniVazba; do zcat raw/$f.json.gz > json/$f.json; done
# 3. load into SQLite (meta.sqlite; vf_0..9.sqlite version fragments; fr.sqlite fragment texts)
python -I -X utf8 tools/build/ingest.py --data DATA --workers 10
python -c "merge fr_*.sqlite into fr.sqlite"          # see scripts/czechia-law/PROGRESS.md
# 4. build, check, test, rebuild
python -I -X utf8 tools/build/build.py --data DATA --repo czechia-law --docs-date 2026-10-28 --workers 10 --docs-gen
python -I -X utf8 tools/build/check_repo.py --data DATA --repo czechia-law --docs-date 2026-10-28 --record verification.json
python -X utf8 tools/test_repo.py --repo czechia-law --record
python scripts/test_corpus.py czechia-law tools/czlaw.py; python scripts/test_noon.py czechia-law
```

Software: Python 3.12.10 (standard library; `ijson` was measured and not used), git version 2.46.0.windows.1, Windows 11, gzip/zcat from Git
for Windows. 10 worker processes.

## Build scripts (git blob ids of the copies in `tools/build/`)

| File | Blob |
| --- | --- |
| `tools/build/build.py` | `7fb30ef399653c85b6482e3f0107d69d8ad4c403` |
| `tools/build/check_repo.py` | `464ea31d0165dc86f487b63878af97b1c6887a57` |
| `tools/build/esbirka_stream.py` | `1f144fd5789bffaf86b023386394a104959a2eee` |
| `tools/build/ingest.py` | `c8bcc98dd6ab3e55e3098b5f805766deb8cc17fc` |
| `tools/build/release.py` | `4267a5b04c950667cd4bf91cae5f5572214c6ee0` |
| `tools/build/render.py` | `1eed7d9c37cfc7500936077061aad19dbaa517c5` |
| `tools/build/test_repo.py` | `df52e321c2399fdb1073cc6f1c51f421e23b0191` |

## This build

- 18,573 acts, 52,732 consolidated versions, 33,780 commits
  (33,640 law commits on `main`, 139 on `future`), 242 tags.
- History from 1918-10-28; `main` records law in force to 2026-10-26.
- 4,889 commits are dated before 1970 and clamped (above).
- Credited: 18,115 changes to amending acts, 12,507 to the act
  itself (first versions excluded), 5,951 to `e-Sbírka`; 9,641
  acts end; 64 versions changed nothing.
- Time on the build machine (24 threads, shared with other jobs): about 4 min to decompress, 3 min to load SQLite,
  3.5 min to render and write the history, 6 min to check. (Not measured into this file, so rebuilds stay identical.)

## Checks

- check_repo.py: {"acts": 18573, "ends_checked": 9641, "ends_wrong": 0, "fidelity_mismatch": 0, "future_commits": 139, "main_commits_with_in_force": 33640, "versions_checked": 52732, "versions_differ": 0, "versions_without_file": 0}
- test_repo.py: 7/7 passed
- Determinism: two independent builds from the same data gave the same hashes for law-head (138211d2e4079c99482dc7c360f02a5356a39fd5), future (740d6ca9d36d9f7b7858738488ab1b6f5750521d), main and all 242 tags; the law history does not depend on this file. The final build was rebuilt once more and its main compared hash for hash before it was pushed

## Decisions made by hand

- Scope: the Sbírka zákonů (collection `sb`), acts typed PRAVPRED (legislation), plus the Charter, 2/1993 Sb., which
  e-Sbírka types as an usnesení. Versions: `KONSOL`, `PUBLIKOV`, not `nikdy-nebyl-účinný`, dated before 2100.
- How changes are credited, and the `e-Sbírka` label: README, "What author means".
- Provision units for crediting: a § or Čl., or one of its odstavce; annexes; footnotes; headings.
- Summer time rules for Prague hard-coded from tzdata (none 1970-1978; from the first Sunday of April in 1979-1980,
  from the last Sunday of March since 1981; until the last Sunday of September to 1995, of October since 1996).

## What an AI did

This repository and its build were made by Claude Code with Claude Opus 5.5 (`claude-opus-5-5`), working for Lexifina:
it read the terms, wrote the scripts, ran them and wrote this documentation. No AI wrote or changed any legal text, and
no model runs at build time: every line of law is e-Sbírka's, reduced from HTML to text by `render.py`. The commit
messages are assembled by code from e-Sbírka's data.
