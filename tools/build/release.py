"""The documentation commit's files, generated at build time: README.md, LICENSE, REPRODUCE.md, corpus.json and tools/.

build.py calls documents(summary, ...) when every main commit has been written, so the counts are the build's own.
Results of the last check and test runs are read from verification.json next to this script (check_repo.py --record
and test_repo.py --record write it); a rebuild after those runs carries them.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict

HERE = Path(__file__).resolve().parent
TOOLS = ["esbirka_stream.py", "ingest.py", "render.py", "build.py", "release.py", "check_repo.py", "test_repo.py"]
LISTINA_40_6 = ("Trestnost činu se posuzuje a trest se ukládá podle zákona účinného v době, kdy byl čin spáchán. "
                "Pozdějšího zákona se použije, jestliže je to pro pachatele příznivější.")


def git_blob(b: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def corpus(summary: dict, docs_date: str) -> dict:
    return {
        "corpus": "cz/national/acts",
        "name": "Czech law: the Sbírka zákonů (Collection of Laws), every act of legislation with consolidated versions, from e-Sbírka's open data",
        "label": "Czechia",
        "language": "cs",
        "acts": summary["acts"],
        "act_types": summary["act_types"],
        "history_from": summary["first_day"],
        "record_to": summary["last_main_day"],
        "record_note": f"every consolidated version checked against e-Sbírka's open datasets as published on {docs_date} (Last-Modified)",
        "built": docs_date,
        "dates": {"commit": "in-force", "other_trailers": [],
                  "time": "12:00 Europe/Prague (UTC+1, UTC+2 in summer time); before 1970 git cannot store the date, so commits are dated 1970-01-01T00:00:01Z onwards, one second apart, and In-force: holds the day"},
        "in_force_trailer": "In-force",
        "has_future_branch": bool(summary["future"]),
        "future_branch": "future" if summary["future"] else None,
        "scope": {
            "trailer": "Applies",
            "when_absent": "this corpus records no scope notes (no commit carries Applies:); the absence is not a statement that the change reaches every case",
            "default_reach": {
                "rule": "no genuine retroactivity",
                "meaning": "an act applies from the day it takes effect (účinnost) and does not attach new legal consequences to facts completed before then; the prohibition follows from the rule of law (legal certainty and legitimate expectations) and admits genuine retroactivity only exceptionally; in criminal law a later act applies only where it is more favourable to the offender",
                "authority": f"Listina základních práv a svobod čl. 40 odst. 6 (\"{LISTINA_40_6}\"); Ústava České republiky čl. 1 odst. 1 (demokratický právní stát), from which the Constitutional Court derives the principle of legal certainty",
                "decided_here": False,
            },
        },
        "tool": "tools/czlaw.py",
        "citation": {"file": "sb/([0-9]{4})/([0-9a-z]+)\\.md", "cites": "{n}/[0-9]{4} Sb\\."},
    }


def documents(summary: dict, data: Path, docs_date: str) -> Dict[str, bytes]:
    ver = {}
    vp = HERE / "verification.json"
    if vp.exists():
        ver = json.loads(vp.read_text(encoding="utf-8"))
    sums = (data / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    used = ["001", "002", "003", "004", "006", "007"]
    files: Dict[str, bytes] = {}
    tool_hashes = {}
    for t in TOOLS:
        p = HERE / t
        if p.exists():
            b = p.read_bytes().replace(b"\r\n", b"\n")
            files[f"tools/build/{t}"] = b
            tool_hashes[t] = git_blob(b)
    files["tools/czlaw.py"] = (HERE / "docs" / "tools" / "czlaw.py").read_bytes().replace(b"\r\n", b"\n")
    files["tools/test_repo.py"] = (HERE / "test_repo.py").read_bytes().replace(b"\r\n", b"\n")
    files["corpus.json"] = (json.dumps(corpus(summary, docs_date), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    files["LICENSE"] = LICENSE.encode("utf-8")
    files["README.md"] = readme(summary, docs_date).encode("utf-8")
    files["REPRODUCE.md"] = reproduce(summary, docs_date, sums, used, tool_hashes, ver).encode("utf-8")
    return files


LICENSE = """Czech law in git (lexifina/czechia-law)

THE LAW
The texts are the consolidated versions of acts in the Sbírka zákonů (Collection of Laws of the Czech Republic) as
published by e-Sbírka, the electronic Collection of Laws and International Treaties run by the Ministry of the
Interior of the Czech Republic (Ministerstvo vnitra ČR), in its open datasets at
https://opendata.eselpoint.cz/datove-sady-esbirka (catalogued in the National Open Data Catalogue, data.gov.cz,
publisher IČO 00007064).

The terms of use (podmínky užití) of every distribution of those datasets, as recorded in the National Open Data
Catalogue on 2026-10-28, are, verbatim:

  Distribuce datové sady neobsahuje autorská díla
  "Součástí poskytované distribuce datové sady nejsou autorská díla ve smyslu § 2 zákona č. 121/2000 Sb., o právu
  autorském, o právech souvisejících s právem autorským a o změně některých zákonů (autorský zákon). Autorské právo
  tak nikterak nebrání libovolnému opětovnému užití obsahu poskytované distribuce datové sady."

  Distribuce datové sady není autorskoprávně chráněnou databází
  "Poskytovaná distriubuce datové sady není autorskoprávně chráněnou databází ve smyslu § 2 odst. 2 a 5 zákona
  č. 121/2000 Sb., o právu autorském, o právech souvisejících s právem autorským a o změně některých zákonů (autorský
  zákon). Strukturu poskytované distribuce datové sady (strukturu poskytované databáze) je tak možné bez dalšího
  převzít a opětovně užívat."

  Distribuce datové sady není chráněna zvláštním právem pořizovatele databáze
  "Poskytovaná distribuce datové sady není chráněna zvláštním právem pořizovatele databáze ve smyslu § 88
  a následujících zákona č. 121/2000 Sb., o právu autorském, o právech souvisejících s právem autorským a o změně
  některých zákonů (autorský zákon). Data poskytované distribuce datové sady je tak možné bez omezení vytěžovat,
  zužitkovat a opětovně užívat."

  Distribuce datové sady neobsahuje osobní údaje
  "Data poskytované distribuce datové sady nejsou osobními údaji ve smyslu zákona č. 101/2000 Sb., o ochraně osobních
  údajů a o změně některých zákonů a nařízení EU č. 2016/679 (Obecné nařízení o ochraně osobních údajů, tzv. GDPR).
  Právní úprava ochrany osobních údajů tak není překážkou pro následné užití této distribuce datové sady."

The catalogue matches these terms to CC0 (skos:narrowMatch
http://publications.europa.eu/resource/authority/licence/CC0). No attribution is required; we give it anyway:

  Source: e-Sbírka (Sbírka zákonů a mezinárodních smluv), Ministerstvo vnitra České republiky,
  https://www.e-sbirka.cz, open data https://opendata.eselpoint.cz/datove-sady-esbirka.

The legally binding text is the one promulgated in the Collection of Laws; consolidated versions are for information.

EVERYTHING ELSE
The history (commit messages, trailers, the arrangement of the files), README, REPRODUCE.md, corpus.json and the tools
are by Lexifina and dedicated to the public domain under CC0 1.0 Universal
(https://creativecommons.org/publicdomain/zero/1.0/).
"""


def readme(s: dict, docs_date: str) -> str:
    t = s["act_types"]
    return f"""# Czech law, change by change

Every act of legislation in the Czech **Sbírka zákonů** (Collection of Laws) that e-Sbírka publishes in consolidated
versions, as one git repository: {s['acts']:,} acts ({t.get('ZAKON', 0):,} zákony, {t.get('ZAKONUST', 0)} ústavní
zákony, {t.get('NARIZENI', 0):,} nařízení, {t.get('VYHLASKA', 0):,} vyhlášky, {t.get('DEKRET', 0) + t.get('DEKRETUST', 0)}
decrees, {t.get('OPATRSEN', 0)} Senate statutory measures, and the Charter of Fundamental Rights and Freedoms). Each
amending act is one commit per day it took effect, credited to that act and dated that day at noon in Prague. The text
is e-Sbírka's own, from its open datasets of {docs_date}.

The Constitution, 1/1993 Sb., is [`sb/1993/1.md`](sb/1993/1.md); the Charter (Listina), 2/1993 Sb., is
[`sb/1993/2.md`](sb/1993/2.md).

## The questions, as git commands

| Question | Command |
| --- | --- |
| What did the Constitution say on 7 March 2013? | `python tools/czlaw.py on 2013-03-07 sb/1993/1.md` |
| The Charter as in force on 1 January 2000 | `python tools/czlaw.py on 2000-01-01 sb/1993/2.md` |
| Which acts of 1993 were in force on 1 January 2000? | `python tools/czlaw.py on 2000-01-01 sb/1993` |
| Which act wrote each line of the Constitution? | `git blame sb/1993/1.md` |
| Every change to the Constitution, with the act and the day | `python tools/czlaw.py log sb/1993/1.md` |
| The same, with git only | `git log --format="%(trailers:key=In-force,valueonly,separator=) %an" -- sb/1993/1.md` |
| What one act changed, everywhere | `git log --format="%(trailers:key=In-force,valueonly,separator=) %s" --author="Zákon č. 89/2012 Sb."` |
| The words that changed in one commit | `git show --word-diff=plain --format=%s law-head~1` |
| A version of the Constitution by its day | `git show --stat sb/1993/1/2013-03-08` |
| Changes no single act explains | `git log --oneline --author="e-Sbírka" -n 5` |
| Acts repealed by one act | `git log --format=%B --author="Zákon č. 89/2012 Sb." --grep="^Repeals:"` |
| Laws taking effect after {docs_date} | `git log --oneline main..future -n 5` |

## The dates, and which one we use

A Czech act has the day it was passed, the day it was promulgated in the Collection (which makes it *platný*, valid)
and the day it takes effect (*účinnost*). **Commits are dated the day the version took effect**: e-Sbírka's
`znění-datum-účinnosti-od`, at noon in Prague (CET, CEST in summer time), and every law commit carries that day as
`In-force:`. Where e-Sbírka publishes a version from the day an act was promulgated, before it takes effect, it marks
each fragment that is not yet in force with its later date; those lines end in `*(účinnost od YYYY-MM-DD)*`, and the
mark goes when the fragment takes effect. Git cannot store dates before 1970, so the {s['clamped']:,} commits before
1970 are dated 1970-01-01T00:00:01Z onwards, one second apart; their `In-force:` is the real day. Use
`tools/czlaw.py` (which reads `In-force:`), not `git log --before`, for dates. Versions taking effect after {docs_date}
are on the `future` branch, which starts at `main`'s head; `main` holds only law in force on or before {docs_date}.
The branch `law-head` is the last law commit on `main`. Tags `sb/<year>/<number>/<day>` mark each version of the
constitutional acts.

`--author` is a regular expression; a citation's dots match any character, which is harmless here. In PowerShell write
`$r = git rev-list -1 main; git show "$($r):sb/1993/1.md"`, because PowerShell splits `$(...):path`. If the history is
ever rebuilt, existing clones need `git fetch --force --tags`.

## What "author" means

The author of a commit is the act that made the change, named as e-Sbírka names its kind and citation
(`Zákon č. 71/2012 Sb.`, `Nález Ústavního soudu č. 403/2002 Sb.`), with an address ending `@esbirka.invalid`, which
cannot exist; so `git blame` names the act. The committer is always `Lexifina`. e-Sbírka links each changed fragment of
a version to the fragment of the amending act that changed it (its consolidation links, *konsolidační vazby*). A change
to a provision (a § or article, or one of its paragraphs, an annex, a heading) is credited:

1. to the act whose links point into that provision in the new version, or into it in the old one;
2. if no link points into it, but the provision carried `účinnost od` that day: to the act that last changed it
   (`Evidence: delayed effect`);
3. if the version's links name one act only: to that act (`Evidence: version link`);
4. if the version has no links and begins on the act's own in-force day: to the act itself (`Evidence: act in-force date`);
5. otherwise to **`e-Sbírka`** (`publisher@esbirka.invalid`), in a commit labelled "bez odkazu na novelu", never to an
   act. Where links name several acts for one provision, all are listed in `Candidate:` trailers.

An act's first version is authored by the act itself. When an act's last version ends, its file is removed the next
day, by the act whose repeal link (ZRUSPRED) has that day (`Repeals:` trailer), or by `e-Sbírka` if none or several do.
After the last commit of each day, every act changed that day is exactly e-Sbírka's version for that day.

So far: {s['authored'].get('act', 0):,} commits are credited to an act and {s['authored'].get('publisher', 0):,} to
e-Sbírka (counts include the `future` branch).

## How it is checked

`tools/build/check_repo.py` renders every consolidated version of every act again from the datasets and compares it,
byte for byte, with the file in git on the day the version took effect, including versions that changed nothing and so
have no commit of their own; it checks that removed acts are absent from their end day; and it checks that the letters
and digits of every rendered version equal those of e-Sbírka's fragment texts, independently of the Markdown layout.
`tools/test_repo.py` checks that blame, the on-date tool, `log`, the tags and the commands above work. The results,
and a rebuild that gave the same hashes, are in [`REPRODUCE.md`](REPRODUCE.md).

## Files

Each act is one file, `sb/<year>/<number>.md`, at its ELI path (`https://www.e-sbirka.cz/eli/cz/sb/<year>/<number>`);
unnumbered acts of 1945-1960 keep e-Sbírka's numbers such as `n137`. The front matter holds facts that never change:
citation, title, kind, ELI. Then every fragment of the version in e-Sbírka's order: `##` lines are divisions (část,
hlava, díl, oddíl, annex headings), `###` lines are provisions (`§ 5`, `Čl. 1`), bold lines are headings, `|` lines
are table rows, and every other line is one fragment (an odstavec, písmeno, bod...) with its label as e-Sbírka prints
it. HTML is reduced to text: links and emphasis are dropped, `<sup>` and `<sub>` are kept, images become
`[obrázek ..., soubor N]` and MathML a one-line form. A line that would read as Markdown gets a backslash. Paths and
lines are LF; soft hyphens and invisible characters are removed.

## What it does not show

- Acts e-Sbírka publishes only as promulgated, without a consolidated version, and versions it marks as never in force
  ({s.get('never', 0)}), withdrawn or pending; dates of 3000-01-xx, which e-Sbírka uses as placeholders ({s.get('placeholder', 0)}).
- Which of several acts made a change, where e-Sbírka's links do not say (above): about {s['totals'].get('by_publisher', 0):,}
  of the {s['totals'].get('by_publisher', 0) + s['totals'].get('by_amending', 0) + s['totals'].get('by_act', 0):,} changes.
- International treaties (Sbírka mezinárodních smluv), Úřední list, and other acts that are not legislation
  (sdělení, usnesení), except the Charter.
- Anything e-Sbírka does not record: the history is as complete as its consolidation, which reaches back to 1918.
- e-Sbírka warns that until 15 January 2027 the identifiers of fragments may change. The text does not depend on them,
  but a rebuild from later data may credit some changes differently.

## How it is built

`tools/build/` holds the build: `ingest.py` loads the datasets into SQLite in parallel, `build.py` renders every
version and streams the history into `git fast-import`, `release.py` writes these files. The same data gives the same
hashes. Every step, the software, the dataset hashes and what an AI model did are in [`REPRODUCE.md`](REPRODUCE.md).
[`corpus.json`](corpus.json) describes the corpus for tools that read several of Lexifina's law repositories.

## Licence

e-Sbírka's open datasets contain no works protected by copyright, are not a protected database and carry no sui generis
database right (the terms of use recorded in the National Open Data Catalogue, data.gov.cz; matched to CC0). Source:
e-Sbírka, Ministerstvo vnitra České republiky, https://www.e-sbirka.cz. The legally binding text is the one promulgated
in the Collection of Laws. The history, messages and tools are CC0 1.0. See [`LICENSE`](LICENSE).

---

## Česky

Všechny právní předpisy Sbírky zákonů, které e-Sbírka publikuje v konsolidovaných zněních, jako repozitář git.

- **Každý commit je jeden novelizující předpis v den své účinnosti** (poledne v Praze), zapsaný jako autor
  (`Zákon č. 71/2012 Sb.`), takže `git blame` ukazuje, který předpis napsal který řádek. Předpis určují konsolidační
  vazby e-Sbírky.
- **Každý předpis je jeden soubor** `sb/<rok>/<číslo>.md`, každý fragment (odstavec, písmeno, bod) jeden řádek.
- **Změny, které vazby nevysvětlují**, nejsou připsány žádnému předpisu; commit je od `e-Sbírka`.
- **Znění účinná až po {docs_date}** jsou ve větvi `future`.
- Text pochází z otevřených dat e-Sbírky (Ministerstvo vnitra ČR); právně závazné je znění vyhlášené ve Sbírce zákonů.
"""


def reproduce(s: dict, docs_date: str, sums, used, tool_hashes, ver) -> str:
    rows = "\n".join(f"| `{l.split()[1]}` | {l.split()[2]} | `{l.split()[0]}` | {' '.join(l.split()[4:])} |"
                     for l in sums if l.split()[1][:3] in used)
    others = sum(1 for l in sums if l.split()[1][:3] not in used)
    th = "\n".join(f"| `tools/build/{k}` | `{v}` |" for k, v in sorted(tool_hashes.items()))
    chk = ver.get("check")
    tst = ver.get("smoke")
    det = ver.get("determinism")
    py = platform.python_version()
    gitv = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    return f"""# How this repository was made

Everything needed to rebuild it, byte for byte, from e-Sbírka's open data.

## Sources

e-Sbírka's open datasets, https://opendata.eselpoint.cz/datove-sady-esbirka (Ministerstvo vnitra ČR; refreshed
daily), downloaded once on 2026-10-28 with `curl -C -` (resumable), 4 at a time, User-Agent
`Lexifina-czechia-law/1.0 (czechia-law@lexifina.com)`. 45 files, 2.3 GB; one request each, plus one HEAD each for the
headers. opendata.eselpoint.cz serves no robots.txt (404). The terms of use were read first, from the National Open
Data Catalogue's SPARQL endpoint (https://data.gov.cz/sparql): see [`LICENSE`](LICENSE). The build reads six files:

| File | Bytes | sha256 | Last-Modified |
| --- | --- | --- | --- |
{rows}

The other {others} files (code lists, CzechVOC, references) were downloaded and hashed but are not read.

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
python -I -X utf8 tools/build/build.py --data DATA --repo czechia-law --docs-date {docs_date} --workers 10 --docs-gen
python -I -X utf8 tools/build/check_repo.py --data DATA --repo czechia-law --docs-date {docs_date} --record verification.json
python -X utf8 tools/test_repo.py --repo czechia-law --record
python scripts/test_corpus.py czechia-law tools/czlaw.py; python scripts/test_noon.py czechia-law
```

Software: Python {py} (standard library; `ijson` was measured and not used), {gitv}, Windows 11, gzip/zcat from Git
for Windows. 10 worker processes.

## Build scripts (git blob ids of the copies in `tools/build/`)

| File | Blob |
| --- | --- |
{th}

## This build

- {s['acts']:,} acts, {s['totals'].get('versions', 0):,} consolidated versions, {s['commits']:,} commits
  ({s.get('main_law_commits', 0):,} law commits on `main`, {s.get('future_commits', 0):,} on `future`), {s['tags']} tags.
- History from {s['first_day']}; `main` records law in force to {s['last_main_day']}.
- {s['clamped']:,} commits are dated before 1970 and clamped (above).
- Credited: {s['totals'].get('by_amending', 0):,} changes to amending acts, {s['totals'].get('by_act', 0):,} to the act
  itself (first versions excluded), {s['totals'].get('by_publisher', 0):,} to `e-Sbírka`; {s['totals'].get('ends', 0):,}
  acts end; {s['totals'].get('unchanged', 0)} versions changed nothing.
- Time on the build machine (24 threads, shared with other jobs): about 4 min to decompress, 3 min to load SQLite,
  3.5 min to render and write the history, 6 min to check. (Not measured into this file, so rebuilds stay identical.)

## Checks

{('- check_repo.py: ' + json.dumps(chk, ensure_ascii=False)) if chk else '- check_repo.py: not yet recorded for this build'}
{('- test_repo.py: ' + str(tst.get('passed')) + '/' + str(tst.get('total')) + ' passed') if tst else '- test_repo.py: not yet recorded'}
{('- Determinism: ' + det) if det else '- Determinism: not yet recorded'}

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
"""
