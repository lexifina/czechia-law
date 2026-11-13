# Legislative history data: Chamber prints, their steps and votes

**Not law.** These tables record how bills and other prints moved through the Parliament of the Czech Republic and how
the Chamber of Deputies voted. The law is the act a bill became, in `sb/<year>/<number>.md`.

Source: the open data of the Chamber of Deputies (Poslanecká sněmovna Parlamentu České republiky),
<https://www.psp.cz/sqw/hp.sqw?k=1300>, as published on 2026-11-13: `tisky.zip`, `sbirka.zip`, `se_tisk.zip`,
`schuze.zip`, `poslanci.zip` and `hl-1993ps.zip` … `hl-2025ps.zip`. Values are copied as published; dates are
written YYYY-MM-DD (psp.cz's placeholder day 1900-01-01 is left empty). Terms are named by the year they began: 1993
is the 1st term (1993-1996), 2025 the 10th (since 2025).

| File | Rows | What |
| --- | ---: | --- |
| `bills.csv` | 11,332 | every Chamber print since 1993 (bills, treaties, budgets, reports, interpellations), one row each |
| `bill-stages.csv` | 77,334 | every recorded step of those prints (psp.cz `hist`) |
| `senate-prints.csv` | 5,415 | every Senate print since 1996 (psp.cz's copy of the Senate database), linked to Chamber prints |
| `votes/<term>.csv` | 83,524 | every recorded vote of the Chamber, one row per vote |
| `votes/<term>-poslanci.csv` | 16,690,400 individual votes | how each MP voted in each vote: one row per vote, one column per MP (`mp_id`) |
| `votes/poslanci.csv` | 2,157 | the MPs of each term: `mp_id` (column of the vote files), name, list elected for, region |

## bills.csv

`term`, `term_no`, `print` (the print number, `/n` for a reworked version, `-E` for EU documents), `psp_id`, `kind`
(the print's kind as psp.cz names it), `initiator_type` and `initiator` (vláda, poslanec, skupina poslanců, Senát,
zastupitelstvo kraje, or the body that submitted it), `presented_by` (psp.cz's own field: the minister presenting a
government bill, or the first sponsors), `title`, `full_title`, `submitted`, `distributed` (to MPs), `eu`,
`follow_up_prints` (opinions, committee resolutions, amendments: prints `n/1`, `n/2`, …), `steps`, `last_step_date`,
`last_step`, `state`, `state_note`, `senate_prints` (Senate term/print), `became` (the Sbírka item(s) it became, e.g.
`89/2012 Sb.`), `became_kind`, `became_published` (the day of the Sbírka issue), `czechia_law` (the act's file in this
repository; an act no longer in force keeps its history under that path), `eli` (e-Sbírka), `veklep` (the
government's material in eKLEP/ODok), `psp_url` (the print's history on psp.cz), `folder` (where the print's
documents are, `navrhy/snemovna/<term>/<print>/`).

`became` joins psp.cz's Sbírka links (`sbirka.unl`) and the steps of the print's history that record publication in
the Sbírka. Prints that became law but have no `czechia_law` path are acts e-Sbírka does not consolidate (for example
sdělení) or acts not yet appended here.

## bill-stages.csv

`term`, `print`, `psp_id`, `step_id`, `date`, `stage` (the state the step leads to: 1. čtení, 2. čtení, 3. čtení,
Senát, Prezident, KONEC …), `action` (předložen, přikázán, schválen, zamítnut, vrácen, podepsal, odeslán …),
`meeting`, `resolution` (number of the Chamber's resolution), `vote_id` (a row of `votes/<term>.csv`), `note`.

## votes

`votes/<term>.csv`: `vote_id`, `term`, `meeting`, `number`, `agenda_item`, `date`, `time`, `print` (term/print the
vote concerns, from the print's history or the meeting's agenda), `psp_print_id`, `result` (A přijato, R zamítnuto,
X/Q výsledek neznámý, K nedosaženo kvóra), `yes`, `no`, `abstained`, `not_voting`, `present`, `quorum`, `mode` (N
normal, R by hand: individual votes not known, E technical fault), `void` (1: declared void, zmatečné), `title`,
`short_title`, `psp_url`.

`votes/<term>-poslanci.csv`: each cell is the MP's vote as psp.cz publishes it: A ano, B or N ne, C zdržel se, F
nehlasoval (present, pressed nothing), @ nepřihlášen, M omluven, W before taking the oath, K zdržel se/nehlasoval;
empty: not an MP at that vote. psp.cz shows an MP who was absent but excused (its `omluvy` table) as M; the cell keeps
the recorded @.

## How it is checked

`navrhy/data` is rebuilt from the zips by the lane's `build_data.py`; `verify_data.py` reads the zips' files again,
independently, and compares every print's number and titles, every vote's date, time, counts, result and titles, and
every individual vote (16,796,609 values checked, 0 mismatched on 2026-11-13).
