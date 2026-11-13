# Ministry bulletins (not law)

Bulletins (věstníky) of ministries and other central bodies: guidance, methodological instructions, notices and
announcements, each issue as published. **They are records, not law**: nothing here is a legal act, and the commits carry
`Kind: record` and no `In-force:`. Each issue is one file, `vestnik/<bulletin>/<year>/<issue>.md`, dated the day the
issue was published, with the text of its PDF one paragraph per line; the commit is authored by the issue and its
`Source:` is the PDF the text was read from. Birth numbers, dates of birth and home addresses of private persons are
removed where they appear (the commit says how many). Every text was checked letter by letter against an independent
extraction of the same PDF; issues that did not pass are not here.

240 issues:

| Folder | Bulletin | Publisher | Years | Issues |
| --- | --- | --- | --- | ---: |
| [`mf-financni-zpravodaj/`](mf-financni-zpravodaj/) | Finanční zpravodaj | Ministerstvo financí | 2003-2026 | 107 |
| [`mzd/`](mzd/) | Věstník Ministerstva zdravotnictví | Ministerstvo zdravotnictví | 2006-2026 | 52 |
| [`vestnik-vlady/`](vestnik-vlady/) | Věstník vlády pro orgány krajů a orgány obcí | Ministerstvo vnitra | 2020-2026 | 38 |
| [`mzp/`](mzp/) | Věstník Ministerstva životního prostředí | Ministerstvo životního prostředí | 2019-2026 | 21 |
| [`dia/`](dia/) | Věstník Digitální a informační agentury | Digitální a informační agentura | 2024-2026 | 8 |
| [`kraj-vysocina/`](kraj-vysocina/) | Věstník právních předpisů Kraje Vysočina | Kraj Vysočina | 2017-2021 | 7 |
| [`msmt/`](msmt/) | Věstník Ministerstva školství, mládeže a tělovýchovy | Ministerstvo školství, mládeže a tělovýchovy | 2025-2025 | 6 |
| [`md/`](md/) | Přepravní a tarifní věstník | Ministerstvo dopravy | 2019-2019 | 1 |

Sources: the bulletin index of the Portál veřejné správy (portal.gov.cz/vestniky), the Ministry of Health's archive
(mzd.gov.cz), the Ministry of Finance's Finanční zpravodaj archive (mf.gov.cz). The Cenový věstník is under
`regulator/`, with the bulletins of the ČNB, ERÚ and ČTÚ.
