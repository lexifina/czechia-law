"""Render one e-Sbírka version (its ordered fragments) as one Markdown file. Shared by the builder and the checks.

Layout of `sb/<year>/<number>.md`:
    ---                                  front matter: facts about the act that never change
    citace: "1/1993 Sb."
    nazev: "..."
    druh: "Ústavní zákon"
    eli: "https://www.e-sbirka.cz/eli/cz/sb/1993/1"
    ---
    # <title>
    then every fragment of the version, in e-Sbírka's order, one block per fragment:
      ## <division>        část, hlava, díl, oddíl, pododdíl, kapitola, příloha headings
      ### <provision>      § N and Čl. N (the provision's heading line; its paragraphs follow as lines)
      **<heading>**        nadpis above or below a division or provision
      | a | b |            table rows
      plain text           everything else, with its label ("(1)", "a)") as e-Sbírka prints it
A fragment e-Sbírka marks with a different in-force date (odlišná účinnost) later than the version's own date gets
" *(účinnost od YYYY-MM-DD)*" at the end of its block. Blocks are separated by one blank line; every line of text is
one fragment (or one table row, or one <br>-separated line), so `git blame` credits a law per fragment.
"""
from __future__ import annotations

import html
import json
import re
from typing import Dict, List, Optional, Tuple

ESBIRKA = "https://www.e-sbirka.cz"
DIVISION = {"Cast", "Hlava", "Dil", "Oddil", "Pododdil", "Kapitola", "Sekce_Obecna", "Sekce_Zvlastni", "Cast_Priloha",
            "Hlavicka_priloha", "Nazev_Priloha", "Eu_Cast", "Eu_Hlava", "Eu_Kapitola", "Eu_Odddil", "Eu_Pododdil"}
PROVISION = {"Paragraf", "Clanek", "ClanekMS", "Clanek_novely", "Eu_Clanek"}
HEADING = {"Nadpis", "Nadpis_nad", "Nadpis_pod", "Nadpis_pod_velkymi", "Nadpis_prvni_casti", "Eu_NadpisPod"}
DRUH = {"ZAKON": "Zákon", "ZAKONUST": "Ústavní zákon", "NARIZENI": "Nařízení", "NARIZVLA": "Nařízení vlády",
        "VYHLASKA": "Vyhláška", "DEKRET": "Dekret", "DEKRETUST": "Ústavní dekret", "OPATRSEN": "Zákonné opatření Senátu",
        "OPATRZAK": "Zákonné opatření", "NALEZ": "Nález Ústavního soudu", "SDELENI": "Sdělení", "USNESENI": "Usnesení",
        "ROZHOD": "Rozhodnutí", "VYNOS": "Výnos", "OPATRENI": "Opatření", "OZNAMENI": "Oznámení", "VYHLASVL": "Vyhláška vlády",
        "SMLOUVA": "Smlouva", "UMLUVA": "Úmluva", "DOHODA": "Dohoda", "OPRAVA": "Oprava", "OSTATNI": "Předpis",
        "ZNENIUPL": "Úplné znění", "SDELMZV": "Sdělení MZV", "VYHLASMZV": "Vyhláška MZV", "SDELENIUS": "Sdělení Ústavního soudu"}

# Characters with no visible text: soft hyphen, zero-width space and joiners, bidi controls, invisible operators, BOM.
INVISIBLE = re.compile("[­​‌‍‎‏‪‫‬‭‮⁠⁡⁢⁣⁤﻿]")
SPACES = re.compile("[     \t\r\n ]+")
TAG = re.compile(r"<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)([^>]*)>", re.S)
BR = re.compile(r"<\s*br\s*/?\s*>", re.I)
TABLE = re.compile(r"<table\b.*?</table\s*>", re.S | re.I)
ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr\s*>", re.S | re.I)
CELL = re.compile(r"<t([dh])\b[^>]*>(.*?)</t[dh]\s*>", re.S | re.I)
MATH = re.compile(r"<math\b.*?</math\s*>", re.S | re.I)
IMG = re.compile(r"<img\b([^>]*)/?>", re.S | re.I)
ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')
COMMENT = re.compile(r"<!--.*?-->", re.S)                      # includes Word's <!--[if gte msEquation 12]>...<![endif]-->
DOWNLEVEL = re.compile(r"<!\[(?:if [^\]]*|endif)\]>", re.I)     # downlevel-revealed markers; their content is shown
KEEP = {"sup", "sub"}            # GitHub renders these; everything else is reduced to its text
MD_START = re.compile(r"^(#|>|[-+*](\s|$)|\d+[.)](\s|$)|\||=+$|`{3}|~{3})")


def clean(s: str) -> str:
    s = INVISIBLE.sub("", s)
    return SPACES.sub(" ", s).strip()


def _math(m: "re.Match") -> str:
    """MathML as one line: msub x_i, msup x^i, mfrac (a)/(b), msqrt √(x), mroot √[n](x); other elements
    give their children's text in order."""
    src = m.group(0)
    root: list = ["#root", []]
    stack = [root]
    pos = 0
    for t in TAG.finditer(src):
        txt = src[pos:t.start()]
        if txt.strip():
            stack[-1][1].append(html.unescape(txt).strip())
        pos = t.end()
        close, name = t.group(1), t.group(2).lower()
        if close:
            if len(stack) > 1:
                stack.pop()
        elif not t.group(3).rstrip().endswith("/"):
            node = [name, []]
            stack[-1][1].append(node)
            stack.append(node)
    def lin(n) -> str:
        if isinstance(n, str):
            return n
        name, kids = n
        k = [lin(x) for x in kids]
        w = lambda x: x if len(x) <= 1 else "(" + x + ")"
        if name in ("msub", "munder") and len(k) >= 2:
            return k[0] + "_" + w(k[1])
        if name in ("msup", "mover") and len(k) >= 2:
            return k[0] + "^" + w(k[1])
        if name in ("msubsup", "munderover") and len(k) >= 3:
            return k[0] + "_" + w(k[1]) + "^" + w(k[2])
        if name == "mfrac" and len(k) >= 2:
            return "(" + k[0] + ")/(" + k[1] + ")"
        if name == "msqrt":
            return "√(" + "".join(k) + ")"
        if name == "mroot" and len(k) >= 2:
            return "√[" + k[1] + "](" + k[0] + ")"
        return "".join(k)
    return " " + lin(root) + " "


def _img(m: "re.Match") -> str:
    a = dict(ATTR.findall(m.group(1)))
    ident = a.get("data-souborovy-dokument-id", "")
    alt = a.get("alt", "")
    return f" [obrázek{(' ' + alt) if alt else ''}{(', soubor ' + ident) if ident else ''}] "


def _tag(t: "re.Match") -> str:
    name = t.group(2).lower()
    if name in KEEP:
        return f"<{t.group(1)}{name}>"
    return ""


def _plain(s: str) -> str:
    """HTML outside MathML: images to placeholders, tags dropped (but <sup>/<sub>), then entities decoded."""
    return html.unescape(TAG.sub(_tag, IMG.sub(_img, s)))


def math_split(s: str):
    """(is_math, piece) in order. MathML is linearised on its own, after its entities are decoded, so a decoded "<"
    inside a formula ("10 < X") is never read as the start of a tag."""
    pos = 0
    for m in MATH.finditer(s):
        yield False, s[pos:m.start()]
        yield True, m
        pos = m.end()
    yield False, s[pos:]


def inline(s: str) -> str:
    """HTML of one line to text: keep <sup>/<sub>, drop other tags and comments, decode entities."""
    s = DOWNLEVEL.sub("", COMMENT.sub("", s))
    s = clean("".join(_math(x) if is_math else _plain(x) for is_math, x in math_split(s)))
    # Empty <sup></sup> pairs left by dropped content.
    return s.replace("<sup></sup>", "").replace("<sub></sub>", "")


def escape(line: str) -> str:
    """Keep a line of law from being read as Markdown syntax: a backslash goes before the "." of "1. text" and before
    a leading "-", "#", ">" and the like."""
    m = MD_START.match(line)
    if not m:
        return line
    d = re.match(r"^(\d+)([.)])", line)
    if d:
        return d.group(1) + "\\" + line[len(d.group(1)):]
    return "\\" + line


def table(s: str) -> List[str]:
    rows: List[List[str]] = []
    pos = 0

    def stray(piece: str) -> None:
        # Text between rows, outside any cell (malformed source HTML): kept, in place, as a one-cell row.
        t = inline(BR.sub(" <br> ", piece)).replace("|", "\\|")
        if t:
            rows.append([t])
    for r in ROW.finditer(s):
        stray(s[pos:r.start()])
        cells = [inline(BR.sub(" <br> ", c.group(2))).replace("|", "\\|") for c in CELL.finditer(r.group(1))]
        rows.append(cells)
        pos = r.end()
    stray(s[pos:])
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return []
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return out


TABLE_TAG = re.compile(r"<(/?)(table|tbody|thead|tfoot|tr|td|th)\b[^>]*>", re.I)


def outer_tables(text: str) -> List[Tuple[int, int]]:
    """Spans of the outermost <table> elements (tables nest: a cell may hold another table)."""
    spans = []
    depth = 0
    start = 0
    for m in TABLE_TAG.finditer(text):
        if m.group(2).lower() != "table":
            continue
        if not m.group(1):
            if depth == 0:
                start = m.start()
            depth += 1
        elif depth:
            depth -= 1
            if depth == 0:
                spans.append((start, m.end()))
    if depth:
        spans.append((start, len(text)))
    return spans


def flatten_nested(t: str) -> str:
    """A table whose cells hold tables: the inner tables' markup becomes spaces, so their text stays in the cell."""
    out = []
    pos = 0
    depth = 0
    for m in TABLE_TAG.finditer(t):
        name = m.group(2).lower()
        inner = depth >= 2 or (depth == 1 and name == "table" and not m.group(1))
        if name == "table":
            if not m.group(1):
                depth += 1
                inner = depth >= 2
            else:
                inner = depth >= 2
                depth -= 1
        out.append(t[pos:m.start()])
        out.append(" " if inner else m.group(0))
        pos = m.end()
    out.append(t[pos:])
    return "".join(out)


def fragment_blocks(typ: str, text: Optional[str]) -> List[List[str]]:
    """One fragment as blocks of lines (a block is one Markdown paragraph, heading or table)."""
    if not text:
        return []
    text = DOWNLEVEL.sub("", COMMENT.sub("", text))
    blocks: List[List[str]] = []
    # Tables become their own blocks; the text around them is handled like any other text.
    pos = 0
    pieces: List[Tuple[str, str]] = []
    for start, end in outer_tables(text):
        pieces.append(("text", text[pos:start]))
        pieces.append(("table", flatten_nested(text[start:end])))
        pos = end
    pieces.append(("text", text[pos:]))
    for kind, piece in pieces:
        if kind == "table":
            t = table(piece)
            if t:
                blocks.append(t)
            continue
        for part in BR.split(piece):
            line = inline(part)
            if not line:
                continue
            if typ in DIVISION:
                blocks.append(["## " + line])
            elif typ in PROVISION:
                blocks.append(["### " + line])
            elif typ in HEADING:
                blocks.append(["**" + line + "**"])
            else:
                blocks.append([escape(line)])
    return blocks


TOP = {"norma", "prefix", "postfix", "prilohy", "novela", "zaver", "poznamkypodcarou"}
UNIT = re.compile(r"^(par|cl|priloha|ppc)_")


def unit_of(path: str) -> str:
    """The provision a fragment belongs to, from its path below `dokument/`: a § or Čl., an attachment or a footnote;
    otherwise the heading it sits under, or the top part (prefix, postfix, ...)."""
    parts = [p for p in path.split("/") if p]
    for i, p in enumerate(parts):
        if UNIT.match(p):
            # A paragraph (odstavec) of a § or Čl. is its own unit, so changes by different acts to different
            # paragraphs of one provision on one day are credited separately.
            if i + 1 < len(parts) and parts[i + 1].startswith("odst_"):
                return "/".join(parts[:i + 2])
            return "/".join(parts[:i + 1])
    while parts and parts[-1].startswith("frag_") and len(parts) > 1 and parts[-2] not in TOP:
        parts.pop()
    if len(parts) >= 2 and parts[0] in ("prefix", "postfix", "zaver"):
        return parts[0]
    return "/".join(parts) or "dokument"


WORD = {"par": "§", "cl": "čl.", "priloha": "příloha", "ppc": "pozn.", "hlava": "hlava", "cast": "část", "dil": "díl",
        "oddil": "oddíl", "pododdil": "pododdíl", "kapitola": "kapitola"}


def unit_label(unit: str) -> str:
    bits = unit.split("#")[0].split("/")
    if len(bits) >= 2 and bits[-1].startswith("odst_") and UNIT.match(bits[-2]):
        return f"{unit_label('/'.join(bits[:-1]))} odst. {bits[-1][5:]}"
    last = bits[-1]
    if last in ("prefix", "postfix", "zaver", "norma", "dokument"):
        return {"prefix": "úvod", "postfix": "podpisy", "zaver": "závěr", "norma": "text", "dokument": "text"}[last]
    m = re.match(r"^([a-z]+)_(.+)$", last)
    if m and m.group(1) in WORD:
        return f"{WORD[m.group(1)]} {m.group(2)}"
    return last


_HK: Dict[str, tuple] = {}
_UNIT: Dict[str, str] = {}


def hkey(h: str):
    """Sort key of a hierarchyid path such as /2/1/10.1/3/ (depth-first order); memoised, since versions share paths."""
    k = _HK.get(h)
    if k is None:
        k = _HK[h] = tuple(_hkey(h))
        if len(_HK) > 2_000_000:
            _HK.clear()
    return k


def unit_cached(path: str) -> str:
    u = _UNIT.get(path)
    if u is None:
        u = _UNIT[path] = unit_of(path)
        if len(_UNIT) > 2_000_000:
            _UNIT.clear()
    return u


def _hkey(h: str):
    out = []
    for p in h.strip("/").split("/"):
        if not p:
            continue
        out.append(tuple(int(x) for x in p.split(".")))
    return out


def header(act: Dict[str, str]) -> str:
    q = lambda v: json.dumps(v, ensure_ascii=False)
    druh = DRUH.get(act.get("druh") or act.get("podtyp") or "", act.get("druh") or "")
    year, num = act["act"].split("/")[1:3]
    lines = ["---", f"citace: {q(act['citation'])}", f"nazev: {q(clean(act['title'] or ''))}", f"druh: {q(druh)}",
             f"eli: {q(ESBIRKA + '/eli/cz/' + act['act'])}", "---", "", "# " + clean(act["title"] or act["citation"])]
    return "\n".join(lines) + "\n"


def render_units(rows: List[Tuple], texts: Dict[int, Tuple[str, Optional[str]]], version_od: str, cache: Dict) -> Tuple[List[str], Dict[str, str]]:
    """rows: (h, fid, path-below-dokument, odlisna) for one version. Returns the unit order and each unit's text
    (its blocks joined). The file body is the units' texts joined by a blank line, in order."""
    order: List[str] = []
    units: Dict[str, List[str]] = {}
    runs: Dict[str, int] = {}
    last = None
    cur = ""
    for h, fid, path, odl in sorted(rows, key=lambda r: hkey(r[0])):
        typ, text = texts.get(fid, ("", None))
        ck = fid
        blocks = cache.get(ck)
        if blocks is None:
            blocks = ["\n".join(b) for b in fragment_blocks(typ, text)]
            cache[ck] = blocks
        if not blocks:
            continue
        if odl:
            d = json.loads(odl) if odl.startswith('"') else odl
            if isinstance(d, str) and d > version_od:
                blocks = blocks[:-1] + [blocks[-1] + f" *(účinnost od {d})*"]
        base = unit_cached(path)
        if base != last:
            # Units are contiguous runs in e-Sbírka's order. A unit met again after another (loose headings of one
            # část between its §§) is a new run, keyed "<unit>#<n>", so the text keeps e-Sbírka's order exactly.
            n = runs[base] = runs.get(base, 0) + 1
            cur = base if n == 1 else f"{base}#{n}"
            order.append(cur)
            units[cur] = []
            last = base
        units[cur].extend(blocks)
    return order, {u: "\n\n".join(b) for u, b in units.items()}


def body(order: List[str], units: Dict[str, str]) -> str:
    return "\n\n".join(units[u] for u in order if units.get(u))


def document(act: Dict[str, str], order: List[str], units: Dict[str, str]) -> str:
    b = body(order, units)
    return header(act) + ("\n" + b + "\n" if b else "")
