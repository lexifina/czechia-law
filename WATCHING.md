# Sledování zdrojů: co se sleduje pro Česko

[English](WATCHING.en.md)

Jak global-law sleduje zdroje všech zemí: [global-law WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md). Tato stránka je totéž jen pro Česko: každý oficiální zdroj, ze kterého tento repozitář bere text, co se na něm čte, jak často a kdy naposledy. Každé čtení a jeho výsledek: [monitoring/](monitoring/README.md).

| Zdroj | Co se čte | Složky | Jak často | Naposledy přečteno | Stav |
| --- | --- | --- | --- | --- | --- |
| [e-Sbírka – otevřená data (Ministerstvo vnitra ČR)](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | šest denních datových sad (předpisy, znění, fragmenty znění, fragmenty, metadata, konsolidační vazby); hlavička každé sady, celá sada jen když se změnila | `sb/` | denně | 2026-11-22 18:12 UTC | sledován |
| [e-Sbírka – mezinárodní smlouvy a Úřední list](https://opendata.eselpoint.gov.cz/datove-sady-esbirka/) | tytéž denní datové sady, sbírka mezinárodních smluv a Úřední list | `sbms/`, `ul/` | denně | — | zatím nesledován |
| [Sbírka právních předpisů územních samosprávných celků](https://sbirkapp.gov.cz) | první stránky každého výpisu předpisů a detail každého nového předpisu | `local/` | denně | — | zatím nesledován |
| [Úřad pro publikace EU (Cellar)](https://publications.europa.eu) | seznam předpisů EU v češtině a jejich nová konsolidovaná znění | `eu/` | týdně | — | zatím nesledován |
| [Poslanecká sněmovna, ODOK vlády a e-Legislativa](https://www.psp.cz) | sněmovní tisky, hlasování a vládní materiály | `navrhy/` | týdně | — | zatím nesledován |
| [Ministerstvo financí, ERÚ, ČTU, Finanční správa, ministerstva a MPSV](https://www.mf.gov.cz) | výpisy cenových rozhodnutí, věstníků, metodik a kolektivních smluv vyššího stupně | `regulator/`, `metodika/`, `vestnik/`, `kolektivni-smlouvy/`, `usneseni-vlady/` | týdně | — | zatím nesledován |
| [Národní digitální knihovna](https://ndk.cz) | skeny historických sbírek (uzavřené) | `historicke/` | — | — | uzavřený zdroj |
| [Nejvyšší soud a databáze soudních rozhodnutí](https://rozhodnuti.nsoud.cz) | databáze rozhodnutí | `caselaw/` | — | — | pozastaven: judikatura počká, nejdřív plné sledování předpisů |

Zdroje se čtou podle jejich robots.txt a pokynů, s pauzami mezi dotazy; e-Sbírku z jejích denních otevřených dat, ne procházením portálu.
