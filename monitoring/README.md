# Monitoring: co se čte a co z toho vzešlo

[English](README.en.md)

Jak global-law sleduje všechny země: [global-law monitoring/](https://github.com/lexifina/global-law/tree/main/monitoring). Tato stránka je totéž jen pro Česko: každé čtení oficiálního zdroje, kdy proběhlo a co z něj vzešlo (nové, změněné a zrušené předpisy). Strojově čitelná podoba je v [data/checks/](../data/checks/) (JSON Lines, schéma `lexifina-check/1`), v `git log` jako commity `Kind: check` a po měsících v [checks/](checks/).

**Poslední kontrola:** 2026-11-24 05:44 UTC, e-Sbírka – otevřená data (Ministerstvo vnitra ČR): přečteno 12 adres; 0 nových, 1 změněných, 0 zrušených; změny zveřejněny; nezveřejněno 10, z toho bez důvodu 0.

## Zdroje

| Zdroj | Složky | Jak často | Poslední úspěšná kontrola | Poslední výsledek | Stav |
| --- | --- | --- | --- | --- | --- |
| [e-Sbírka – otevřená data (Ministerstvo vnitra ČR)](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | `sb/` | denně | 2026-11-24 05:44 UTC | změny zveřejněny | sledován |
| [e-Sbírka – mezinárodní smlouvy a Úřední list](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | `sbms/`, `ul/`, `sb/` | denně | 2026-11-23 06:55 UTC | beze změny | sledován |
| [Sbírka právních předpisů územních samosprávných celků](https://sbirkapp.gov.cz) | `local/` | denně | 2026-11-22 20:04 UTC | kontrola selhala | sledován: sčítání jednou týdně; předpisy, jejichž detail se dosud nečetl, jsou vedeny bez důvodu |
| [Úřad pro publikace EU (Cellar)](https://publications.europa.eu) | `eu/` | týdně | — | — | zatím nesledován |
| [Poslanecká sněmovna (otevřená data a tisky) a e-Legislativa](https://www.psp.cz) | `navrhy/`, `usneseni-vlady/` | týdně | 2026-11-23 07:03 UTC | beze změny | sledován: materiály ODOK a usnesení vlády se nečtou: robots.txt odok.gov.cz zakazuje roboty; z e-Legislativy jen hlavičky datových sad |
| [Ministerstvo financí, ERÚ, ČTU, Finanční správa, ministerstva a MPSV](https://www.mf.gov.cz) | `regulator/`, `metodika/`, `vestnik/`, `kolektivni-smlouvy/` | týdně | — | — | zatím nesledován |
| [Národní digitální knihovna](https://ndk.cz) | `historicke/` | — | — | — | uzavřený zdroj |
| [Nejvyšší soud a databáze soudních rozhodnutí](https://rozhodnuti.nsoud.cz) | `caselaw/` | — | — | — | pozastaven: judikatura počká, nejdřív plné sledování předpisů |

## Posledních 30 dní

| Začátek (UTC) | Zdroj | Přečteno | Nové | Změněné | Zrušené | Nezveřejněno (bez důvodu) | Výsledek | Commity |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| [2026-11-24 05:30](checks/2026-11.md#cz-e-sbirka-20261124t053001z) | e-sbirka | 12 | 0 | 1 | 0 | 10 (0) | změny zveřejněny | [1](https://github.com/lexifina/czechia-law/compare/0d4cdb16805c...47009f20be95) |
| [2026-11-23 15:20](checks/2026-11.md#cz-sppsu-20261123t152003z) | sppsu | 18 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 14:20](checks/2026-11.md#cz-sppsu-20261123t142003z) | sppsu | 24 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 13:20](checks/2026-11.md#cz-sppsu-20261123t132003z) | sppsu | 25 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 12:20](checks/2026-11.md#cz-sppsu-20261123t122003z) | sppsu | 34 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 11:20](checks/2026-11.md#cz-sppsu-20261123t112003z) | sppsu | 19 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 10:20](checks/2026-11.md#cz-sppsu-20261123t102018z) | sppsu | 18 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 09:50](checks/2026-11.md#cz-sppsu-20261123t095026z) | sppsu | 29 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 08:20](checks/2026-11.md#cz-sppsu-20261123t082002z) | sppsu | 27 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 07:20](checks/2026-11.md#cz-sppsu-20261123t072002z) | sppsu | 22 | 0 | 0 | 0 | 0 (0) | kontrola selhala | — |
| [2026-11-23 07:00](checks/2026-11.md#cz-legislative-process-20261123t070000z) | legislative-process | 40 | 0 | 0 | 0 | 0 (0) | beze změny | — |
| [2026-11-23 06:50](checks/2026-11.md#cz-e-sbirka-extra-20261123t065001z) | e-sbirka-extra | 6 | 0 | 0 | 0 | 1 (0) | beze změny | — |
| [2026-11-23 05:30](checks/2026-11.md#cz-e-sbirka-20261123t053001z) | e-sbirka | 12 | 0 | 0 | 0 | 11 (0) | beze změny | — |
| [2026-11-22 19:50](checks/2026-11.md#cz-sppsu-20261122t195010z) | sppsu | 19 | 2 | 0 | 0 | 0 (0) | změny zveřejněny | [2](https://github.com/lexifina/czechia-law/compare/40a9a83079c8...2e1979749470) |
| [2026-11-22 19:30](checks/2026-11.md#cz-sppsu-20261122t193032z) | sppsu | 167 | 2430 | 107 | 10 | 24664 (24188) | změny zveřejněny, s příznakem `unexplained-gap` `mass-change` | [2569](https://github.com/lexifina/czechia-law/compare/f0c4e82f3221...3082f98884a3) |
| [2026-11-22 19:22](checks/2026-11.md#cz-legislative-process-20261122t192211z) | legislative-process | 75 | 5 | 8 | 0 | 0 (0) | změny zveřejněny | [10](https://github.com/lexifina/czechia-law/compare/a6e6a0fde696...88f80d3e2512) |
| [2026-11-22 19:11](checks/2026-11.md#cz-e-sbirka-extra-20261122t191152z) | e-sbirka-extra | 6 | 1 | 7301 | 0 | 1 (0) | změny zveřejněny, s příznakem `mass-change` | [7302](https://github.com/lexifina/czechia-law/compare/ea10ea6fb741...1a0481c885e3) |
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
