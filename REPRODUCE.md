# How this repository was made

Everything needed to rebuild it, byte for byte, from e-Sbírka's open data.

## Sources

e-Sbírka's open datasets, https://opendata.eselpoint.cz/datove-sady-esbirka (Ministerstvo vnitra ČR; refreshed
daily), downloaded on 2026-10-28: 45 files, 2.3 GB. opendata.eselpoint.cz serves no robots.txt (404). The terms of
use were read first, from the National Open Data Catalogue's SPARQL endpoint (https://data.gov.cz/sparql): see
[`LICENSE`](LICENSE). The build reads six files:

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
# 1. download the datasets from https://opendata.eselpoint.cz/datove-sady-esbirka, then check sizes against Content-Length
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

## Appended on 2026-11-02

`main` only grows: nothing above was rebuilt or rewritten. This part was appended on top of the documentation commit
of 2026-10-28.

**Data.** The six datasets the build reads, as e-Sbírka published them on 2026-11-02 (Last-Modified Mon, 02 Nov 2026):

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `001PravniAktZneni.json.gz` | 178,037,865 | `cec482810953afeaf4446236822f8ceb25a58da2f9b180966c5c69a5b5e4e191` |
| `002PravniAkt.json.gz` | 5,422,774 | `2f60610175d0e1c29132269164e1ad34c6474be94d68734f0d0eb6322a9da813` |
| `003PravniAktZneniFragment.json.gz` | 1,253,388,347 | `b3a6619161fd514e732de1d9a6b17efef77a42690f97b6b7ede5895362e3e073` |
| `004PravniAktFragment.json.gz` | 531,639,276 | `e0358723bb545e8c3337a8d1cee908dfc0d8aa2b73d80e1f148421962b023c8e` |
| `006PravniAktMetadata.json.gz` | 6,266,982 | `5c2e37007d049802a2c09f1d97fb29da245a89e0af629e801ce0f19e1b30c4df` |
| `007PravniAktKonsolidacniVazba.json.gz` | 19,970,836 | `84cf79961ebb4c7e844b39148d46842336ea0384bf9b95103ebe80fe77127754` |

**Method.** The unchanged `tools/build/` scripts (steps 2–4 above, `--docs-date 2026-11-02`, no documentation
commit) made a full build from these files: 18,576 acts, 52,741 consolidated versions, law in force to 2026-11-01.
Every act's history up to 2026-10-26, the last day of the history published on 2026-10-28, was compared, day by day,
with `law-head` (138211d2e4079c99482dc7c360f02a5356a39fd5):

- **37 acts read differently on days already published** (16 of them on 2026-10-26 itself), because e-Sbírka now
  publishes different consolidated texts for them (for example, fragments marked as taking effect in 2027 or 2028 removed from the versions in force, and
  formula tables in sb/2015/408 republished in a different markup). Each is corrected by an appended commit by
  `e-Sbírka <publisher@esbirka.invalid>`, one for every day the published text and the new text first differ:
  106 commits with `Kind: correction`, `In-force:` and `Corrected:` (the first day corrected), `Corrects: <act>
  <from>..<to>` (open-ended when it runs on), `Supersedes:` (the published commit that day's text came from) and
  `Reason:`. Where only earlier days of an act were corrected, one more commit of the same kind restates the text
  in force from the act's last day of change (unchanged), so that its file at the tip is its current text again
  (21 commits; 127 in all). With them, every act reads as in the new build on every day to 2026-10-26.
- **10 law commits** in force from 2026-10-30 to 2026-11-01 were then appended: nine credited to 183, 199, 200, 203,
  206, 207 and 208/2026 Sb. (206, 207 and 208/2026 Sb. are new acts) and one by `e-Sbírka` recording seven repeals.
  They are the new build's own commits, with the same messages, authors and author dates, and their `sb/` tree.

Committer dates continue from the commit before, one second apart, so committer dates never go backwards. The
`future` branch is left as it was published on 2026-10-28 (branches here only move forward); `law-head` moves to the
last appended law commit.

**Readers.** `tools/czlaw.py` and `tools/build/check_repo.py` now leave correction commits out of the `In-force:`
order and, for an act a correction touches, read the act's own history: the commit with the greatest `In-force:` day
on or before the day asked (a correction only within the days it names), a later commit winning a tie. New git blob
ids: `tools/czlaw.py` `d84ce6391ea90f5a1f9b2dd81eb4c8f77bb5f500`, `tools/build/check_repo.py`
`c3567b9d5f03a3209d485aceb4beb82bd3ab5e85`. `tools/test_repo.py` (and its copy in `tools/build/`, `c83d38df05b7c7b6a1da85903fec8d315127f75c`)
now accepts one documentation commit per append (by Lexifina, touching no law file) and checks `main` against the
last append day and `future` against the day it was made. The other scripts are unchanged.

**Check.** `check_repo.py` against the datasets of 2026-11-02 (versions after 2026-11-02 read from that build's own
`future` branch, which has the same texts): `{"acts": 18576, "correction_commits": 127, "ends_checked": 9642, "ends_wrong": 0, "fidelity_mismatch": 0, "future_commits": 95, "main_commits_with_in_force": 33650, "versions_checked": 52741, "versions_differ": 0, "versions_without_file": 0}`

`tools/test_repo.py`: 7/7 passed.

## Appended on 2026-11-08

`main` only grows: nothing above was rebuilt or rewritten. This part was appended on top of the documentation commits
of 2026-11-02, 2026-11-04 and 2026-11-06.

**Data.** The six datasets the build reads, as e-Sbírka published them on 2026-11-08 (Last-Modified Sun, 08 Nov 2026):

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `001PravniAktZneni.json.gz` | 178,314,695 | `bb485533eecb811a84ea46949becc432b099704f05d78c5a140aff2afef3b44b` |
| `002PravniAkt.json.gz` | 5,425,514 | `da0c87c2daed581633829350821c10ca709ed145ec1f4828559da01f1ef3cd34` |
| `003PravniAktZneniFragment.json.gz` | 1,249,059,397 | `ac07eb27ded56b0d1907cf388f8ba364deb1411a057e2d9ca6628cd62b919266` |
| `004PravniAktFragment.json.gz` | 531,954,769 | `c2dcc041425f8409910937d75e2b77ff10b0b045ec208a845a46b11643ace130` |
| `006PravniAktMetadata.json.gz` | 5,899,180 | `3404bbf2245b447e1e0318d4c1d0dcf4003154cf3df242039f0ce8a47606f935` |
| `007PravniAktKonsolidacniVazba.json.gz` | 20,046,936 | `21c599e7bf79f6399b28ee37b8d49c1dff4f70371cb5d23b3455c3e746eaf4ae` |

**Method.** As for 2026-11-02: the unchanged `tools/build/` scripts made a full build from these files
(`--docs-date 2026-11-08`): 18,582 acts, 52,799 consolidated versions. Every act's whole
history up to 2026-11-01 (the published `record_to`) was compared, day by day, with the published `law-head`, reading
the published corrections over their `Corrects:` ranges. Where e-Sbírka's text differs on a published day, a
`Kind: correction` commit by e-Sbírka sets the act's file to its current text for those days (82 commits,
including restatements of the current text after corrections to earlier days). Then the build's law commits after
2026-11-01 up to 2026-11-08 were appended (5 commits), same messages and authors as the build.

**Check.** `tools/build/check_repo.py` on the appended history against the 2026-11-08 data: `check_repo exit 0, 0 versions differ {"versions_checked":52799,"versions_differ":0,"versions_without_file":0,"ends_checked":9653,"ends_wrong":0,"fidelity_mismatch":0,"acts":18582,"seconds":1624,"main_commits_with_in_force":33655,"correction_commits":209,"future_commits":105}`.
