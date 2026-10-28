# Czech law, change by change

Every act of legislation in the Czech **Sbírka zákonů** (Collection of Laws) that e-Sbírka publishes in consolidated
versions, as one git repository: 18,573 acts (5,114 zákony, 122 ústavní
zákony, 3,874 nařízení, 9,209 vyhlášky, 100
decrees, 154 Senate statutory measures, and the Charter of Fundamental Rights and Freedoms). Each
amending act is one commit per day it took effect, credited to that act and dated that day at noon in Prague. The text
is e-Sbírka's own, from its open datasets of 2026-10-28.

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
| Laws taking effect after 2026-10-28 | `git log --oneline main..future -n 5` |

## The dates, and which one we use

A Czech act has the day it was passed, the day it was promulgated in the Collection (which makes it *platný*, valid)
and the day it takes effect (*účinnost*). **Commits are dated the day the version took effect**: e-Sbírka's
`znění-datum-účinnosti-od`, at noon in Prague (CET, CEST in summer time), and every law commit carries that day as
`In-force:`. Where e-Sbírka publishes a version from the day an act was promulgated, before it takes effect, it marks
each fragment that is not yet in force with its later date; those lines end in `*(účinnost od YYYY-MM-DD)*`, and the
mark goes when the fragment takes effect. Git cannot store dates before 1970, so the 4,889 commits before
1970 are dated 1970-01-01T00:00:01Z onwards, one second apart; their `In-force:` is the real day. Use
`tools/czlaw.py` (which reads `In-force:`), not `git log --before`, for dates. Versions taking effect after 2026-10-28
are on the `future` branch, which starts at `main`'s head; `main` holds only law in force on or before 2026-10-28.
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

So far: 32,528 commits are credited to an act and 1,251 to
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
  (104), withdrawn or pending; dates of 3000-01-xx, which e-Sbírka uses as placeholders (11).
- Which of several acts made a change, where e-Sbírka's links do not say (above): about 5,951
  of the 36,573 changes.
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
- **Znění účinná až po 2026-10-28** jsou ve větvi `future`.
- Text pochází z otevřených dat e-Sbírky (Ministerstvo vnitra ČR); právně závazné je znění vyhlášené ve Sbírce zákonů.
