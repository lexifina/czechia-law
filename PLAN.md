# The plan: every source a Czech lawyer or citizen needs

This is the plan for this repository, part by part, with what is published so far. The aim is everything a Czech lawyer or citizen needs, in one dated git history: every act with every version, case law, local law, treaties, EU law and the legislative history behind each act.

**52.3%** of the plan is published, weighted by how binding each source is and how often it is used. Unlike some plans, this one counts history too: an act counts as held only with every consolidated version e-Sbírka publishes. Targets were counted from the official sources on 2026-11-13.

| Part | Will be in | Weight | Progress | How | Status |
| --- | --- | ---: | --- | --- | --- |
| **Primary legislation (Sbírka zákonů)** | | | | | |
| Constitution, Charter, constitutional acts, laws, government and ministerial decrees, with every consolidated version | sb/<year>/<number>.md | 38.0% | 18,583 of 18,608 acts e-Sbírka consolidates · 99.9% | e-Sbírka open data; every version checked byte for byte | done |
| Items of the Sbírka zákonů published only as promulgated (Constitutional Court findings, sdělení, oznámení, republished full texts, usnesení, opatření, crisis resolutions, Senate statutory measures, presidential decisions) | sb/<year>/<number>.md, labelled "as promulgated" | 4.0% | 11,956 of 12,600 items · 94.9% | e-Sbírka open data, the promulgated text | planned |
| Which act made each change | the author of each commit | 2.0% | 33,535 of 36,217 changes credited to an act · 92.6% | e-Sbírka's consolidation links; the rest from the amending acts' own amendment points | collecting |
| Úřední list (1945-1961: ministerial vyhlášky) | ul/<year>/<number>.md | 2.0% | 12,621 of 12,621 items · 100.0% | e-Sbírka open data (11,985 with consolidated versions) | planned |
| **Historical law** | | | | | |
| Sbírka zákonů a nařízení 1918-1938, the Protectorate 1939-1945, and the Austrian and Hungarian law received in 1918 | sb/<year>/<number>.md; historicke/rgbl/<year>/<number>.md | 3.0% | 593 of about 6,340 numbered acts of 1918-1938 · 9.4%; 1939-1945 and the received law not started | e-Sbírka scans, the National Library's digitised gazettes, ÖNB ALEX (RGBl 1849-1918); OCR checked against the printed text | planned |
| **Case law** | | | | | |
| Constitutional Court (nálezy, usnesení, plenary opinions) | judikatura/us/<year>/ | 7.0% | 0 of 105,034 decisions (6,622 nálezy, 98,366 usnesení, 46 plenary opinions) · 0.0% | NALUS; linked to the provisions they annul or interpret | planned |
| Supreme Court (incl. the Sbírka soudních rozhodnutí a stanovisek) | judikatura/ns/<year>/ | 4.0% | 0 of 165,523 decisions · 0.0% | the court's decision database | planned |
| Supreme Administrative Court (incl. the Sbírka rozhodnutí NSS) | judikatura/nss/<year>/ | 4.0% | 0 of 84,449 decisions · 0.0% | the court's decision database | planned |
| Regional, district and high courts (civil and criminal since 2020; administrative) | separate repositories, one per court level | 2.0% | 0 of 702,518 decisions (615,315 published by the Ministry of Justice, 87,203 regional administrative-court decisions) · 0.0% | rozhodnuti.justice.cz open data (anonymised); the Supreme Administrative Court's database | planned |
| ECHR judgments concerning the Czech Republic | judikatura/eslp/ | 1.0% | 0 of 1,063 judgment documents (306 in Czech) and 1,155 decisions · 0.0% | HUDOC; the Government Agent's Czech translations | planned |
| CJEU decisions on Czech references | judikatura/sdeu/ | 0.5% | 0 of 130 references (108 judgments, 13 orders) · 0.0% | CURIA / EUR-Lex: operative part and metadata | planned |
| Competition and procurement authority (ÚOHS), Financial Arbiter, energy and telecoms regulators | judikatura/<body>/ | 1.5% | 0 of 29,754 decisions (ÚOHS 22,442, ERÚ about 5,880, Finanční arbitr 1,269, ČTÚ 163) · 0.0% | each body's decision database; identifiers removed | planned |
| **Local law** | | | | | |
| Ordinances of municipalities and regions (obecně závazné vyhlášky, nařízení) | local/<region>/<municipality>/<year>/<number>/ | 11.0% | 0 of 79,204 regulations (49,900 in force) · 0.0% | the Sbírka právních předpisů územních samosprávných celků (sbirkapp.gov.cz): every regulation in force was filed there by 2024; history built from its amendment and repeal links | planned |
| Other acts in that collection (Constitutional Court decisions on ordinances, suspensions, states of danger) | local/<region>/<body>/ | 0.3% | 0 of 135 acts · 0.0% | sbirkapp.gov.cz | planned |
| Local ordinances repealed before 2022 | local/<region>/<municipality>/<year>/<number>/ | 0.7% | target unknown | regional bulletins and municipal archives | planned |
| **Regulators and other secondary rules** | | | | | |
| Binding measures of regulators (ČNB, ERÚ, ČTÚ) and price regulation (Cenový věstník) | regulator/<body>/<year>/ | 3.0% | target being counted (about 300 ERÚ entries; ČNB and ČTÚ bulletins since 1990 and 1996) · 0.0% | each bulletin as published | planned |
| Ministry bulletins (guidance) | vestnik/<ministry>/<year>/ | 0.5% | 1,008 issues indexed on portal.gov.cz · 0.0% | portal.gov.cz index, each ministry's bulletin | planned |
| Collective agreements of higher degree | kolektivni-smlouvy/<year>/ | 0.5% | 0 of 322 texts · 0.0% | MPSV open data; the extension notices are already sdělení in the Sbírka | planned |
| **Treaties and EU law** | | | | | |
| Treaties (Sbírka mezinárodních smluv 2000-2023; treaties in the Sbírka zákonů) | smlouvy/<year>/<number>.md | 3.0% | 4,005 of 4,006 treaties and notices (2,263 in the Sbírka mezinárodních smluv; the treaties in the Sbírka zákonů are in sb/) · 100.0% | e-Sbírka open data; the Ministry of Foreign Affairs' treaty database (3,766 treaties) for status | planned |
| EU law in Czech (regulations and directives in force) | eu/<kind>/<year>/<number>/ | 1.0% | 1,580 of 6,767 acts · 23.3% | EUR-Lex / Cellar, the Czech Official Journal text | planned |
| EU transposition links | eu/transposition.csv | 2.0% | 3,890 of 3,890 notified measures · 100.0% | EUR-Lex national implementing measures for CZ | planned |
| **Legislative history** | | | | | |
| Bills and explanatory reports (Chamber of Deputies and Senate prints since 1993) | navrhy/<chamber>/<term>/<print>/, labelled not law; data/bills.csv | 3.5% | 199 of 11,332 Chamber prints and 5,415 Senate prints · 1.2% | psp.cz open data (prints linked to the acts they became); the reports from each print | planned |
| Votes | data/votes/<term>.csv | 0.5% | 10 of 10 terms · 100.0% | psp.cz open data | planned |
| Government drafts in consultation (with impact assessments and EU correlation tables) | navrhy/vlada/<year>/, labelled not law | 1.0% | 4 of 8,717 materials · 0.0% | ODok / VeKLEP open data | planned |
| Government resolutions | usneseni-vlady/<year>/<number>.md | 1.0% | target being counted (about 800-1,300 a year since 1991) · 0.0% | the Government Office's resolution archive | planned |
| **Oversight and practical tables** | | | | | |
| Ombudsman (Veřejný ochránce práv) and Supreme Audit Office (NKÚ) | dohled/<body>/ | 2.0% | 0 of 6,885 Ombudsman documents; NKÚ being counted · 0.0% | each body's own publications | planned |
| Practical tables (which court covers each municipality, court fees, deadlines, minimum wage, default interest) | data/ | 1.0% | 3 of 5 tables · 60.0% | computed from the acts in this repository, each row citing its provision | planned |
| **Out of scope** | | | | | |
| Technical standards (ČSN) | none: standard numbers cited only | – | out of scope | ČSN may be copied only with the Agency's consent (zákon 22/1997 Sb., § 5(10)) | not planned |

Progress counts what is on `main`. Targets are the official counts: e-Sbírka's open data (46,093 items: 31,208 in the Sbírka zákonů, of which 18,608 consolidated and 12,600 promulgated only; 2,264 in the Sbírka mezinárodních smluv; 12,621 in the Úřední list), the Sbírka právních předpisů územních samosprávných celků (79,204 regulations), psp.cz and ODok open data, EUR-Lex. NALUS, the Supreme Court's and the Supreme Administrative Court's databases, rozhodnuti.justice.cz, HUDOC, CURIA and the ÚOHS's collections give the case-law counts. Parts with no count yet are being counted.
