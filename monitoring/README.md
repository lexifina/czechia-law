# Monitoring: co se čte a co z toho vzešlo

[English](README.en.md)

Jak global-law sleduje všechny země: [global-law monitoring/](https://github.com/lexifina/global-law/tree/main/monitoring). Tato stránka je totéž jen pro Česko: každé čtení oficiálního zdroje, kdy proběhlo a co z něj vzešlo (nové, změněné a zrušené předpisy). Strojově čitelná podoba je v [data/checks/](../data/checks/) (JSON Lines, schéma `lexifina-check/1`), v `git log` jako commity `Kind: check` a po měsících v [checks/](checks/).

**Poslední kontrola:** 2026-11-22 18:13 UTC, e-Sbírka – otevřená data (Ministerstvo vnitra ČR): přečteno 6 adres; 0 nových, 0 změněných, 0 zrušených; beze změny; nezveřejněno 11, z toho bez důvodu 0.

## Zdroje

| Zdroj | Složky | Jak často | Poslední úspěšná kontrola | Poslední výsledek | Stav |
| --- | --- | --- | --- | --- | --- |
| [e-Sbírka – otevřená data (Ministerstvo vnitra ČR)](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | `sb/` | denně | 2026-11-22 18:13 UTC | beze změny | sledován |
| [e-Sbírka – mezinárodní smlouvy a Úřední list](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | `sbms/`, `ul/` | denně | — | — | zatím nesledován |
| [Sbírka právních předpisů územních samosprávných celků](https://sbirkapp.gov.cz) | `local/` | denně | — | — | zatím nesledován |
| [Úřad pro publikace EU (Cellar)](https://publications.europa.eu) | `eu/` | týdně | — | — | zatím nesledován |
| [Poslanecká sněmovna, ODOK vlády a e-Legislativa](https://www.psp.cz) | `navrhy/` | týdně | — | — | zatím nesledován |
| [Ministerstvo financí, ERÚ, ČTU, Finanční správa, ministerstva a MPSV](https://www.mf.gov.cz) | `regulator/`, `metodika/`, `vestnik/`, `kolektivni-smlouvy/`, `usneseni-vlady/` | týdně | — | — | zatím nesledován |
| [Národní digitální knihovna](https://ndk.cz) | `historicke/` | — | — | — | uzavřený zdroj |
| [Nejvyšší soud a databáze soudních rozhodnutí](https://rozhodnuti.nsoud.cz) | `caselaw/` | — | — | — | pozastaven: judikatura počká, nejdřív plné sledování předpisů |

## Posledních 30 dní

| Začátek (UTC) | Zdroj | Přečteno | Nové | Změněné | Zrušené | Nezveřejněno (bez důvodu) | Výsledek | Commity |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| [2026-11-22 18:12](checks/2026-11.md#cz-e-sbirka-20261122t181234z) | e-sbirka | 6 | 0 | 0 | 0 | 11 (0) | beze změny | — |
| [2026-11-22 08:30](checks/2026-11.md#cz-e-sbirka-20261122t083006z) | e-sbirka | 6† | 0 | 3 | 0 | — | změny zveřejněny `flip-flop` | [3](https://github.com/lexifina/czechia-law/compare/1143aee17299...523a83a18b6d) |
| [2026-11-21 08:30](checks/2026-11.md#cz-e-sbirka-20261121t083003z) | e-sbirka | 5† | 0 | 2533 | 0 | — | změny zveřejněny, s příznakem `mass-change` `flip-flop` | [7202](https://github.com/lexifina/czechia-law/compare/88a0ce927dde...1143aee17299) |
| [2026-11-20 08:30](checks/2026-11.md#cz-e-sbirka-20261120t083003z) | e-sbirka | 6† | 0 | 0 | 0 | — | beze změny | — |
| [2026-11-19 08:30](checks/2026-11.md#cz-e-sbirka-20261119t083002z) | e-sbirka | 6† | 0 | 0 | 0 | — | beze změny | — |
| [2026-11-18 08:30](checks/2026-11.md#cz-e-sbirka-20261118t083002z) | e-sbirka | 6† | 0 | 3 | 0 | — | změny zveřejněny `flip-flop` | [19](https://github.com/lexifina/czechia-law/compare/b22ffa38cfd9...88a0ce927dde) |
| [2026-11-17 08:30](checks/2026-11.md#cz-e-sbirka-20261117t083003z) | e-sbirka | 6† | 0 | 0 | 0 | — | beze změny | — |
| [2026-11-16 08:30](checks/2026-11.md#cz-e-sbirka-20261116t083003z) | e-sbirka | 6† | 0 | 1 | 0 | — | změny zveřejněny `flip-flop` | [18](https://github.com/lexifina/czechia-law/compare/bdab4ddf45fb...109e39f00a11) |
| [2026-11-15 08:30](checks/2026-11.md#cz-e-sbirka-20261115t083003z) | e-sbirka | 5† | 0 | 0 | 0 | — | zdroj neodpověděl | — |
| [2026-11-14 13:02](checks/2026-11.md#cz-e-sbirka-20261114t130255z) | e-sbirka | 6† | 0 | 1 | 0 | — | změny zveřejněny | [18](https://github.com/lexifina/czechia-law/compare/da664d61daae...3ad0b8914b91) |
| [2026-11-13 18:10](checks/2026-11.md#cz-e-sbirka-20261113t181010z) | e-sbirka | 0† | 0 | 0 | 0 | — | data zdroje ještě nebyla obnovena | — |

† Doplněno 22. 11. 2026 ze záznamu běhu: dotazy HEAD a sčítání (census) se tehdy nezapisovaly, uvedena jsou jen stažení.

## Jak to ověřit sami

```
python tools/checktrail.py                      # poslední kontrola každého zdroje
python tools/checktrail.py --day 2026-11-21     # všechny kontroly jednoho dne
python tools/checktrail.py --act sb/2026/220    # kdy byl předpis viděn a zveřejněn
git log --grep='^Kind: check' --format='%ci %s'  # kontroly v historii
```

Právně závazné je jen znění vyhlášené ve Sbírce zákonů a mezinárodních smluv (e-Sbírka, Ministerstvo vnitra ČR); konsolidovaná znění e-Sbírky jsou informativní.
