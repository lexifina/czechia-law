# Practical tables (derived, not law)

Tables computed by script from the acts in this repository. Every row names the act, the provision, the file
(`path`), the commit of that file it was read from (`commit`) and the day that version took effect
(`version_in_force_from`), and quotes the provision (`quoted_text`). A script checks that every `quoted_text` is a
substring of that file at that commit (Markdown escapes removed); the counts are in the lane's records. The binding
text is the act itself; check it before relying on a row.

| Table | What it holds | Read from |
| --- | --- | --- |
| [`minimum-wage.csv`](minimum-wage.csv) | Minimum wage (hourly, monthly) and the lowest levels of guaranteed wage, by period (`valid_from`, `valid_to` exclusive), 1991-2027 | every version of nařízení vlády 99/1991, 53/1992, 303/1995 and 567/2006 Sb.; from 2025 the MPSV sdělení in the Sbírka zákonů announcing the amounts (zákoník práce § 111 odst. 7, § 112 odst. 4) |
| [`court-municipalities.csv`](court-municipalities.csv) | Which district court (okresní soud; obvodní soud in Prague; Městský soud v Brně), regional court and high court covers each municipality, by period (6,300 rows; one row per municipality and court set, `valid_to` exclusive) | zákon 6/2002 Sb., přílohy č. 1-4 and § 9 odst. 2, every version (e-Sbírka's later corrections to old versions not applied); municipalities as the annex names them (no municipality codes) |
| [`court-fees.csv`](court-fees.csv) | Court fees: each fee of the sazebník (položka, bod, písmeno), its text, the amount in Kč and/or the percentage, by period, 1992- (210 rows, 91 in force) | zákon 549/1991 Sb., příloha (sazebník poplatků), every version |
| [`procedural-deadlines.csv`](procedural-deadlines.csv) | Time limits for remedies and filings (odvolání, dovolání, kasační stížnost, odpor, rozklad, žaloba, námitky ...): the period and where it runs from, as in force in the current version (147 rows) | občanský soudní řád, zákon o zvláštních řízeních soudních, trestní řád, soudní řád správní, správní řád, daňový řád; rows are every sentence that names a remedy and a time limit, selected mechanically: read the quoted sentence |
| [`default-interest.csv`](default-interest.csv) | Statutory default interest (úroky z prodlení) by the period in which the delay begins, 1994-2026 | nařízení vlády 142/1994 Sb. (twice the ČNB discount rate, later repo rate + points) and 351/2013 Sb. (repo rate + 8 points), each rule as in force in its version; the ČNB rates from cnb.cz (`rate_source`: URL, retrieval date, sha256) |

Columns of `minimum-wage.csv`: `valid_from`, `valid_to`, `kind` (minimum wage / guaranteed wage), `scope`, `group`
(work group of the guaranteed wage), `weekly_hours`, `hourly`, `monthly`, `percent_of_general`, `currency`, `act`,
`provision`, `path`, `version_in_force_from`, `commit`, `quoted_text`, `source`.

Columns of `default-interest.csv`: `period_from`, `period_to`, `period_meaning`, `default_interest_percent`,
`reference_rate` (which ČNB rate), `reference_date`, `reference_rate_percent`, `multiplier`, `margin_points`, `act`,
`provision`, `path`, `version_in_force_from`, `commit`, `rule_from`, `rule_to` (the days the rule applied),
`quoted_text`, `rate_source`.

Columns of the other tables follow the same pattern: the values, `valid_from`/`valid_to`, `act`, `provision`, `path`,
`version_in_force_from`, `commit`, `quoted_text` (parts joined by ` … ` where the quote spans two places).
