# CzechVOC: the legal vocabulary of e-Sbírka

CzechVOC is the thesaurus of Czech legal terms that the Ministry of the Interior keeps in e-Sbírka: concepts with
their terms, the statutory definitions that define them (linked to the provisions that hold them), and the
hierarchy of concepts. e-Sbírka's 542,982 related-concept links (dataset 035) are not included. These files are e-Sbírka's open datasets 030-040 of 2026-11-13
(https://opendata.eselpoint.cz/datove-sady-esbirka), as tables. This folder is a record, not law: the law is in
`sb/`. Nothing here was written by a model; the text of each definition is e-Sbírka's, with its HTML reduced to text.

| File | Rows | What |
| --- | ---: | --- |
| `terms.csv` | 14,988 | every term, with its concept (14,988 concepts) |
| `definitions.csv` | 28,244 | definitions of concepts, each with the provision and the act's file here |
| `hierarchy.csv` | 97,790 | broader -> narrower concept links |

## Columns

- `terms.csv`: `concept_id` (CzechVOC concept), `term_id`, `term`, `preferred` (1 for the concept's preferred term),
  `state` (C valid, D obsolete, U undefined), `schemes` (VECNYREJ subject index, POJMREJ concept index, EUROVOC),
  `legal_area` (1 when the concept is an area of law), `created`, `changed`.
- `definitions.csv`: `definition_id`, `concept_id`, `term` (the concept's preferred term), `kind` (Z statutory
  definition, from an act; M substantive definition, from e-Legislativa; P conceptual definition, made in CzechVOC),
  `citation` (as e-Sbírka gives it, such as `73/2023 Sb. § 2 odst. 2`), `act` (the act's file in this repository,
  `sb/<year>/<number>.md`; `sbms/` and `ul/` for treaties and the Úřední list), `provision` (e-Sbírka's path of the defining fragment in the act, such as
  `norma/par_2/odst_2/pism_a`, from the latest version linked), `valid_from`, `valid_to` (the days the link between
  the definition and the provision holds), `text` (the definition as e-Sbírka gives it: HTML tags dropped, entities
  decoded, `<sup>`/`<sub>` kept).
- `hierarchy.csv`: `broader_concept_id`, `broader_term`, `narrower_concept_id`, `narrower_term`.

## How it was checked

Every definition was checked against this repository: its act's file must exist, and the letters and digits of each
fragment of its text (a definition is an excerpt: the defining paragraph and the points that define, without the
others) must each appear in that file as in force on the definition's `valid_from` day (or in the file on
`main`); superscripts and subscripts may be missing from a definition ("m<sup>2</sup>" given as "m").
28,301 definitions in e-Sbírka; 28,244 pass and are here; 57 are left out
(text not found in the act's file (its fragments, as in force on valid_from, nor on main): 57).
