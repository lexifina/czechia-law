# Návrhy: the legislative history behind the acts

**Not law.** Nothing under `navrhy/` was ever in force as written here. Bills, explanatory reports (důvodové zprávy),
amendments, committee resolutions and government drafts are what was proposed; the law is the act a bill became, in
`sb/<year>/<number>.md`, from its own in-force day. Commits under `navrhy/` carry `Kind: draft` or `Kind: record` and
no `In-force:` trailer, so no reader of the law in force (`tools/czlaw.py`) takes text from them.

| Path | What | Source |
| --- | --- | --- |
| `data/` | every Chamber print since 1993 with its steps and the act it became (`bills.csv`), Senate prints, every Chamber vote with each MP's vote | Chamber of Deputies open data, psp.cz |

Nepublikuje se zde právo: jde o návrhy a podklady legislativního procesu. Platné právo je předpis, kterým se návrh
stal (`sb/<rok>/<číslo>.md`).
