# Vulnerabilities in Czech law

[Čeština](README.md) · **English**

<picture>
<source media="(prefers-color-scheme: dark)" srcset="img/flags-by-category-dark.svg">
<img alt="33,557 flags in eight categories: lapsed time limits 29,582, same-day conflicts 878, empty periods 386, stale amounts 213, references to deleted provisions 397, duplicate numbering 1,961, dead currencies 137, publisher notes 3, each split into flags in law texts and in other texts" src="img/flags-by-category.svg" width="880">
</picture>

The vulnerability detectors from [lexifina/global-law](https://github.com/lexifina/global-law/tree/main/vulnerabilities) look for mechanical mistakes in legislation: a rule applying "until" a date that has passed, a time limit extended only after it had run out, two amendments to the same act on the same day, a reference to a section that no longer exists. global-law's published list (9 November 2026) covered Czechia from an earlier, smaller copy of this repository, so this is a run over this repository only, as it stood at commit [`aa02aa0`](https://github.com/lexifina/czechia-law/commit/aa02aa05dc66bdff595c04995523e3955feed005) on 15 November 2026, with the Úřední list, local ordinances, treaties, EU law, bills and case law it now holds.

**In short:** the detectors raised 33,557 flags. A language model reviewed 212 of the strongest, arguing each one for and against; 61 survived. Checked by hand in this repository, four look like real mistakes in Czech law. Act No. 73/2025 Coll. repealed §§ 56 to 56b of the Advocacy Act and moved their content to §§ 52e to 52n, but seven provisions still cite § 56 or § 56a (found by the first review of this repository and still flagged; this review drew other flags of the same score). Three extensions came only after the period they extended had ended: Act No. 19/2023 Coll. extended a transitional deadline of 31 December 2022 from 24 January 2023, so for 23 days the rule had lapsed; Decree No. 343/2001 Coll. extended feed additives permitted until 30 September 2001 from 4 October 2001 (three days, 11 flags); and Act No. 39/2004 Coll. moved the end of 2003, the latest date to which the Securities Commission could extend an investment fund's conversion, to the end of 2004 from 5 February 2004 (35 days). Of the other 48, 30 come from how this repository is laid out (one file per act) or how its record credits changes, 6 are lawful, 3 are spent rules, and 9 point to another act's sections. Later, this will be formalised in Lean, similar to our work on [the US tax code](https://lexifina.com/blog/formalizing-the-us-tax-code) and [US case law](https://lexifina.com/blog/formalizing-all-us-case-law-in-lean).

A flag is a prompt to look, not legal advice, and nothing here has been tested in court.

## Flags by category

| Category | What it looks for | Flags | In law texts | Reviewed | Survived review |
| --- | --- | ---: | ---: | ---: | ---: |
| Lapsed time limits | Text still applying a rule "until" a date that has passed | 29,582 | 21,709 | 52 | 0 |
| Same-day conflicts | Two acts changing the same act on the same day | 878 | 878 | 40 | 3 |
| Empty periods | A time limit extended by an act that took effect after it had run out | 386 | 386 | 40 | 28 |
| Stale amounts | An amount changed in one place but still standing elsewhere | 213 | 213 | 40 | 18 |
| References to deleted provisions | A provision citing a section that no longer exists | 397 | 397 | 40 | 12 |
| Duplicate numbering | Two units with the same number in one act | 1,961 | 273 | 0 | 0 |
| Dead currencies | Amounts in currencies no longer in use | 137 | 50 | 0 | 0 |
| Publisher notes | Notes that an amendment could not be carried out | 3 | 3 | 0 | 0 |

"In law texts" counts the Sbírka zákonů and the Úřední list, treaties, local ordinances, EU acts, regulators' measures and collective agreements. The other flags are in bills and government drafts, court decisions, government resolutions, ministry bulletins and guidance, which this repository also holds and labels as not law. The search for lapsed time limits now also reads dates written with spaces ("31. 12. 2020") and the end of a year ("do konce roku 2020"); in law texts it reads 27,157 such phrases with a past date and still leaves out 1,695 that give only a month or a year: "do roku 2012" or a bare year (1,113, some of them amounts such as "do 2000 kg"), "do června 2020" (331), "do konce června 2020" (220), "do konce kalendářního roku" and the like (28), and 3 others. The search for repeal gaps and retroactive dates found nothing to flag: an act is one file here, so a section removed and later restored leaves no deleted file to find, and the commits carry no publication date to compare with.

*Edge cases: the 61 flags that survived the review, grouped by what they turned out to be, the two from the first review, and what the other flags are, in [EDGE-CASES.en.md](EDGE-CASES.en.md).*

## Problems found in this repository

- **One file per act** puts a whole act in front of detectors written for one file per provision: an amount quoted in an amending act's "replace X with Y" counts as the old amount "still standing", and two dates in unrelated sentences of one act read as a time limit and its extension (28 of the 61 survivors, in [Edge cases](EDGE-CASES.en.md)).
- **Changes credited to no act:** where e-Sbírka's links do not name the amending act, a change is committed under e-Sbírka on the date of e-Sbírka's version, and the record does not show when the text was changed (Government Order No. 206/1947 Coll. and Notice No. 471/1947 of the Úřední list in [Edge cases](EDGE-CASES.en.md)).
- **Metadata at the top of local ordinances and bills** (`sppsu_id`, `text_url`, `soubor`, `soubor_sha256`) is part of each file, so tools that scan the text read it too: 3 "Belgian franc" flags are the letters "bef" ending a file checksum, and 6 "Deutsche Mark" flags are the letters "DM" in an attachment's file name.

## Files

| File | What it holds |
| --- | --- |
| [data/flags.csv](data/flags.csv) | Every flag, one row per act and issue |
| [data/reviewed.csv](data/reviewed.csv) | The 212 flags the model reviewed, with its verdict and reason |
| [data/by_category.csv](data/by_category.csv) | The counts in the table above |
| [tools/](tools/) | The scripts that made this run |

Columns: `category` and `category_cs` (the category in English and Czech), `detector`, `kind` (`law` or `other`), `path` (the file in this repository), `date` (the date the flag turns on), `reference` (the act or line involved), `summary`, `score` (the detector's ranking, 0 to 1), `review` (`artefact`, `lawful` or `candidate_defect`), `survives_rebuttal`, `review_note` (the model's reason, in English), `url` (the act at the commit that was read, or, for an act repealed since, at the last commit that held it).

## How it was made

- **Detectors:** global-law's [vulnerabilities/scripts](https://github.com/lexifina/global-law/tree/main/vulnerabilities/scripts), run on this repository at commit `aa02aa0`. global-law replays this repository only up to an earlier commit, so the history table the detectors read was built from this repository's own commits (the author, the act that made each change, and the `In-force` and `Kind` trailers). The detectors were then run again with fixes that read dates written with spaces and the end of a year, treat "nejpozději do" as a deadline, read the Czech "a" between section numbers as "and" rather than as a range, and match fewer false currencies.
- **Model review:** gpt-5.4-mini, the 40 strongest flags per category, and for lapsed time limits also the 40 strongest in law texts (52 in all); one pass says whether a flag is real, a second argues that it is not. Empty periods use global-law's own review for that category, on the 25 flags whose old and new date are in one sentence and the 15 shortest gaps, followed by the same second pass. After the fixes, lapsed time limits, references to deleted provisions and empty periods were reviewed afresh; flags that tie on score are now taken in a fixed order, so the reviewed set differs from the first run's. Where a flag was reviewed twice, the later review is kept. global-law's own list used a different model.
- **Hand check:** every case that survived was read in this repository's history and texts, against the amending act as promulgated. Read again, the feed-additive rows of Decree No. 451/2000 Coll., which the first check had put down to unrelated dates, turned out to be one real gap. The open cases still need the Sbírka zákonů itself and any amendment not yet in force.

To report a correction, open an issue with the provision and an official source.

## Licence

The lists and notes are Lexifina's, dedicated to the public domain under CC0 1.0, like the rest of this repository's own contributions. Quoted law text is as e-Sbírka publishes it; see [LICENSE](../LICENSE).
