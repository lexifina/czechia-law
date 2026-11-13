# Which act made the changes credited to e-Sbírka

5,951 of the 36,573 changes in this history (one act's file in one commit; 5,754 on `main`, 197 only on `future`) are
committed under `e-Sbírka` (`publisher@esbirka.invalid`), in commits labelled "bez odkazu na novelu", because
e-Sbírka's consolidation links do not say which act made them (README, "What author means"). The history is
append-only, so those commits stay as they are. This folder resolves them from the amending acts' own text:
[`credits.csv`](credits.csv) names, for each changed provision, the act whose amendment point made the change, with
the evidence and a confidence class. `tools/czlaw.py log` and `tools/czlaw.py blame` show that act instead of
`e-Sbírka`, labelled "resolved by data/credits" with its confidence; `git log` and `git blame` still show e-Sbírka.

## credits.csv

One row per changed provision of each of the 5,951 changes (54,808 rows), UTF-8, comma-separated:

| Column | Meaning |
| --- | --- |
| commit | the e-Sbírka commit |
| path | the act's file, `sb/<year>/<number>.md` |
| provision | the provision the commit changed, as its message names it (`§ 3 odst. 2`, `čl. 7`, `pozn. 4`, `část 2`); where the message cut the list at 40, the rest is read from the diff |
| in_force | the day the change took effect (the commit's `In-force:`) |
| act | the act that made the change; for `ambiguous`, every candidate, separated by ` \| ` |
| act_eli | its ELI at e-Sbírka, likewise |
| evidence | the amending act's point (part, article and point by e-Sbírka's fragment numbering, and its text), the act it targets as its intro names it, how its in-force day was found, how the point names the provision, and how many of its quoted words are in the commit's diff |
| confidence | `high`, `medium`, `low`, `ambiguous` or `unresolved` (below) |

## How a change is resolved

Only rules and string matching; no model reads or decides anything.

1. **The amending acts' text.** Every act's promulgated text (e-Sbírka's open data of 2026-11-13: the version
   `0000-00-00` of each act in dataset 003, its fragment texts in 004) is split into blocks: an intro naming the act
   it amends with an amending verb ("Zákon č. 61/2000 Sb., ... se mění takto:", "V zákoně č. X/Y Sb. ... se ...",
   "V § 5 zákona č. X/Y Sb. se ...", "Zrušuje se ustanovení § 5 ... č. X/Y Sb.") and the points that follow it in the
   same article. Each point keeps the provisions it names, the words it quotes (replaced or removed, inserted) and the
   text it inserts. 31,364 blocks in 46,180 acts.
2. **The day.** A point counts only if it takes effect on the change's day: its own day where e-Sbírka records one
   for the fragment (*odlišná účinnost*, which covers delayed points), else the day the act's commencement
   provisions give for its article or point ("čl. I bodu 5 ... nabývá účinnosti dnem ..."), else the act's in-force
   day. A point of an act with several commencement days that cannot be pinned to the point is only "possible".
3. **The provision.** The point must name the changed provision (§, čl., příloha, poznámka pod čarou, část, hlava,
   díl, oddíl, with the odstavec where both give one), or the whole text ("v celém textu").
4. **The words.** Words a point inserts must be among the commit's added lines, words it replaces or removes among the
   removed lines.
5. An act's own provisions with a later day of effect (its text in e-Sbírka carries that *odlišná účinnost*) resolve
   to the act itself.

| Confidence | Meaning |
| --- | --- |
| high | one act: a point in force that day names the provision (to the odstavec where the change has one) and its quoted words, if it quotes any, are in the diff |
| medium | one act: a point in force that day names the provision at § level only, or names it but its quoted words are not found; or a point for the whole text whose words are found |
| low | one act amends this act with effect that day, but none of its points names the provision (a whole part or division replaced or repealed, renumbering), or its day is only possible |
| ambiguous | several acts tie at the best level; all are listed |
| unresolved | no act in e-Sbírka's texts amends this act with effect that day |

## Results (2026-11-13)

| Of the 5,951 changes | Count | Share |
| --- | ---: | ---: |
| every provision resolved, worst class high | 2,630 | 44.2% |
| every provision resolved, worst class medium | 442 | 7.4% |
| every provision resolved, worst class low | 1,454 | 24.4% |
| some provisions resolved, others not | 217 | 3.6% |
| ambiguous (several candidate acts) | 114 | 1.9% |
| unresolved | 1,094 | 18.4% |

By provision (54,808 rows): high 20,390, medium 4,656, low 11,052, ambiguous 1,828, unresolved 16,882.

A random sample of 30 resolved provisions (10 per class), each checked by reading the amending point and the
commit's diff: high 10 of 10 right; medium 9 right, 1 not confirmed (a point inserting a heading after the §);
low 7 right, 1 right act but a different point of it than the one cited, 2 not confirmed (whole parts inserted).
None was found to name the wrong act.

Unresolved changes are mostly old (before 1990) versions, consolidations whose text e-Sbírka changed without an
amending act in its data (corrections, renumbering, republished full texts), and amending acts whose points the
rules above do not parse.

## Re-running

The code is in [`code/`](code): `ingest_pv.py` (promulgated texts from datasets 003/004 into SQLite), `events.py` (the
e-Sbírka commits from git), `blocks.py` (the amendment points), `resolve.py` (writes `credits.csv`). After new
commits are appended, or with newer datasets:

```
python -X utf8 data/credits/code/events.py --repo . --out WORK/events.jsonl
python -X utf8 data/credits/code/ingest_pv.py --src DATASETS --db WORK/db        # only for new datasets
python -X utf8 data/credits/code/blocks.py --db WORK/db                          # only for new datasets
python -X utf8 data/credits/code/resolve.py --events WORK/events.jsonl --db WORK/db --out WORK/out
```

`WORK/db` also needs `meta.sqlite` (acts, versions, links) from `tools/build/ingest.py --stage meta`. Then copy
`WORK/out/credits.csv` here. The same data gives the same file.
