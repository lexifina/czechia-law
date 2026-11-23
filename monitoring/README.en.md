# Monitoring: what is read and what came of it

[Čeština](README.md)

How global-law monitors every country: [global-law monitoring/](https://github.com/lexifina/global-law/tree/main/monitoring). This page is the same for Czechia only: every time an official source is read, when, and what came of it (acts added, changed and removed). The machine-readable form is [data/checks/](../data/checks/) (JSON Lines, schema `lexifina-check/1`), in `git log` as `Kind: check` commits, and month by month in [checks/](checks/).

**Last check:** 2026-11-23 05:41 UTC, e-Sbírka open data (Ministry of the Interior): 12 addresses read; 0 added, 0 changed, 0 removed; no change; 11 not published, 0 of them with no reason.

## Sources

| Source | Folders | How often | Last successful check | Last result | State |
| --- | --- | --- | --- | --- | --- |
| [e-Sbírka open data (Ministry of the Interior)](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | `sb/` | daily | 2026-11-23 05:41 UTC | no change | watched |
| [e-Sbírka: international treaties and the Official Journal](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | `sbms/`, `ul/`, `sb/` | daily | 2026-11-23 06:55 UTC | no change | watched |
| [Collection of Legal Regulations of Local and Regional Authorities](https://sbirkapp.gov.cz) | `local/` | daily | 2026-11-22 20:04 UTC | changes published | watched: census once a week; regulations whose detail page has not been read yet are listed with no reason |
| [EU Publications Office (Cellar)](https://publications.europa.eu) | `eu/` | weekly | — | — | not watched yet |
| [Chamber of Deputies (open data and prints) and e-Legislativa](https://www.psp.cz) | `navrhy/`, `usneseni-vlady/` | weekly | 2026-11-23 07:03 UTC | no change | watched: ODOK materials and government resolutions are not read: odok.gov.cz's robots.txt disallows bots; e-Legislativa: dataset headers only |
| [Ministry of Finance, ERÚ, ČTU, Financial Administration, ministries and MPSV](https://www.mf.gov.cz) | `regulator/`, `metodika/`, `vestnik/`, `kolektivni-smlouvy/` | weekly | — | — | not watched yet |
| [National Digital Library](https://ndk.cz) | `historicke/` | — | — | — | closed source |
| [Supreme Court and the court decisions database](https://rozhodnuti.nsoud.cz) | `caselaw/` | — | — | — | paused: case law waits until legislation is fully monitored |

## The last 30 days

| Started (UTC) | Source | Read | Added | Changed | Removed | Not published (no reason) | Result | Commits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| [2026-11-23 07:00](checks/2026-11.md#cz-legislative-process-20261123t070000z) | legislative-process | 40 | 0 | 0 | 0 | 0 (0) | no change | — |
| [2026-11-23 06:50](checks/2026-11.md#cz-e-sbirka-extra-20261123t065001z) | e-sbirka-extra | 6 | 0 | 0 | 0 | 1 (0) | no change | — |
| [2026-11-23 05:30](checks/2026-11.md#cz-e-sbirka-20261123t053001z) | e-sbirka | 12 | 0 | 0 | 0 | 11 (0) | no change | — |
| [2026-11-22 19:50](checks/2026-11.md#cz-sppsu-20261122t195010z) | sppsu | 19 | 2 | 0 | 0 | 0 (0) | changes published | [2](https://github.com/lexifina/czechia-law/compare/40a9a83079c8...2e1979749470) |
| [2026-11-22 19:30](checks/2026-11.md#cz-sppsu-20261122t193032z) | sppsu | 167 | 2430 | 107 | 10 | 24664 (24188) | changes published, flagged `unexplained-gap` `mass-change` | [2569](https://github.com/lexifina/czechia-law/compare/f0c4e82f3221...3082f98884a3) |
| [2026-11-22 19:22](checks/2026-11.md#cz-legislative-process-20261122t192211z) | legislative-process | 75 | 5 | 8 | 0 | 0 (0) | changes published | [10](https://github.com/lexifina/czechia-law/compare/a6e6a0fde696...88f80d3e2512) |
| [2026-11-22 19:11](checks/2026-11.md#cz-e-sbirka-extra-20261122t191152z) | e-sbirka-extra | 6 | 1 | 7301 | 0 | 1 (0) | changes published, flagged `mass-change` | [7302](https://github.com/lexifina/czechia-law/compare/ea10ea6fb741...1a0481c885e3) |
| [2026-11-22 18:12](checks/2026-11.md#cz-e-sbirka-20261122t181234z) | e-sbirka | 6 | 0 | 0 | 0 | 11 (0) | no change | — |
| [2026-11-22 08:30](checks/2026-11.md#cz-e-sbirka-20261122t083006z) | e-sbirka | 6† | 0 | 3 | 0 | — | changes published `flip-flop` | [3](https://github.com/lexifina/czechia-law/compare/1143aee17299...523a83a18b6d) |
| [2026-11-21 08:30](checks/2026-11.md#cz-e-sbirka-20261121t083003z) | e-sbirka | 5† | 0 | 2533 | 0 | — | changes published, flagged `mass-change` `flip-flop` | [7202](https://github.com/lexifina/czechia-law/compare/88a0ce927dde...1143aee17299) |
| [2026-11-20 08:30](checks/2026-11.md#cz-e-sbirka-20261120t083003z) | e-sbirka | 6† | 0 | 0 | 0 | — | no change | — |
| [2026-11-19 08:30](checks/2026-11.md#cz-e-sbirka-20261119t083002z) | e-sbirka | 6† | 0 | 0 | 0 | — | no change | — |
| [2026-11-18 08:30](checks/2026-11.md#cz-e-sbirka-20261118t083002z) | e-sbirka | 6† | 0 | 3 | 0 | — | changes published `flip-flop` | [19](https://github.com/lexifina/czechia-law/compare/b22ffa38cfd9...88a0ce927dde) |
| [2026-11-17 08:30](checks/2026-11.md#cz-e-sbirka-20261117t083003z) | e-sbirka | 6† | 0 | 0 | 0 | — | no change | — |
| [2026-11-16 08:30](checks/2026-11.md#cz-e-sbirka-20261116t083003z) | e-sbirka | 6† | 0 | 1 | 0 | — | changes published `flip-flop` | [18](https://github.com/lexifina/czechia-law/compare/bdab4ddf45fb...109e39f00a11) |
| [2026-11-15 08:30](checks/2026-11.md#cz-e-sbirka-20261115t083003z) | e-sbirka | 5† | 0 | 0 | 0 | — | the source did not answer | — |
| [2026-11-14 13:02](checks/2026-11.md#cz-e-sbirka-20261114t130255z) | e-sbirka | 6† | 0 | 1 | 0 | — | changes published | [18](https://github.com/lexifina/czechia-law/compare/da664d61daae...3ad0b8914b91) |
| [2026-11-13 18:10](checks/2026-11.md#cz-e-sbirka-20261113t181010z) | e-sbirka | 0† | 0 | 0 | 0 | — | the source had not refreshed its data yet | — |

† Backfilled on 2026-11-22 from the run's log: its HEAD requests and census were not recorded, so only the downloads are listed.

## Check it yourself

```
python tools/checktrail.py                      # the latest check of every source
python tools/checktrail.py --day 2026-11-21     # every check of a day
python tools/checktrail.py --act sb/2026/220    # when an act was seen and published
git log --grep='^Kind: check' --format='%ci %s'  # the checks in the history
```

Only the text promulgated in the Collection of Laws and International Treaties (e-Sbírka, Ministry of the Interior of the Czech Republic) is legally binding; e-Sbírka's consolidated versions are informative.
