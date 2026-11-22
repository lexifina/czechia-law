# Watching the sources: what is watched for Czechia

[Čeština](WATCHING.md)

How global-law watches every country's sources: [global-law WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md). This page is the same for Czechia only: every official source this repository takes text from, what is read on it, how often and when it was last read. Every read and what came of it: [monitoring/](monitoring/README.en.md).

| Source | What is read | Folders | How often | Last read | State |
| --- | --- | --- | --- | --- | --- |
| [e-Sbírka open data (Ministry of the Interior)](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | six daily datasets (acts, versions, version fragments, fragments, metadata, consolidation links); each dataset's headers, the whole dataset only when it changed | `sb/` | daily | 2026-11-22 18:12 UTC | watched |
| [e-Sbírka: international treaties and the Official Journal](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | the same daily datasets: the treaty collection and the Official Journal | `sbms/`, `ul/` | daily | — | not watched yet |
| [Collection of Legal Regulations of Local and Regional Authorities](https://sbirkapp.gov.cz) | the first pages of each listing of regulations and the detail of each new one | `local/` | daily | — | not watched yet |
| [EU Publications Office (Cellar)](https://publications.europa.eu) | the list of EU acts in Czech and their new consolidated versions | `eu/` | weekly | — | not watched yet |
| [Chamber of Deputies, the Government's ODOK and e-Legislativa](https://www.psp.cz) | parliamentary prints, votes and government papers | `navrhy/` | weekly | — | not watched yet |
| [Ministry of Finance, ERÚ, ČTU, Financial Administration, ministries and MPSV](https://www.mf.gov.cz) | the listings of price decisions, bulletins, guidance and higher-level collective agreements | `regulator/`, `metodika/`, `vestnik/`, `kolektivni-smlouvy/`, `usneseni-vlady/` | weekly | — | not watched yet |
| [National Digital Library](https://ndk.cz) | scans of historical collections (closed) | `historicke/` | — | — | closed source |
| [Supreme Court and the court decisions database](https://rozhodnuti.nsoud.cz) | the decisions databases | `caselaw/` | — | — | paused: case law waits until legislation is fully monitored |

Sources are read within their robots.txt and guidance, with pauses between requests; e-Sbírka from its daily open data, not by crawling the portal.
