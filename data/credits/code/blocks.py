"""Index the amendment points of every act, from its promulgated text (e-Sbírka 003/004, loaded by ingest_pv.py).

    python -X utf8 blocks.py --db C:/Users/alany/law8/czechia/lanes/credits/db

A block is the part of an amending act that amends one other act: an intro fragment naming the target act with an
amending verb ("Zákon č. 61/2000 Sb., ... se mění takto:", "V zákoně č. 110/2006 Sb., ... se ...", "V § 5 zákona
č. X/Y Sb. se ...", "Ustanovení § 5 zákona č. X/Y Sb. ... se ruší"), and the points that follow it in the same
article (or the intro alone when it is the only instruction). Each point keeps its head text, the provisions it names
(refs), the words it quotes (old: words replaced or removed; new: words inserted), the text of its quoted content, and
its own in-force day where e-Sbírka gives one (znění-fragment-odlišná-účinnost). The act's commencement provisions
("nabývá účinnosti dnem ...") are kept too, to date points of acts whose fragments carry no day.

Writes blocks.sqlite: blocks(target, act, article, intro_path, intro, data) and acts_dates(act, inforce, dates, clauses).
Rules and string matching only.
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in (Path(__file__).resolve().parents[3] / 'tools' / 'build',
                                    Path(__file__).resolve().parents[1] / 'clone' / 'tools' / 'build') if p.exists())))
import render as R  # noqa: E402

CIT = re.compile(r'č\.\s*(\d+)\s*/\s*(\d{4})\s*(?:Sb|Zb)\b')
CIT_OLD = re.compile(r'ze dne \d{1,2}\.\s*\w+\s+(\d{4}),?\s*č\.\s*(\d+)\s*(?:Sb|Zb)\b')
QUOTE = re.compile(r'„[^„“]*“')
VERB = re.compile(r'(?:\bse\b[^.;:]{0,300}?\b(?:mění|doplňuj\w*|doplní|zrušuj\w*|ruší|nahrazuj\w*|nahradí|vklád\w*|vloží|'
                  r'vypouští|vypouštěj\w*|vypustí|označuj\w*|přečísl\w*|zní|znějí|upravuje)\b|\b(?:zní|znějí)\s*:|'
                  r'\bmění\s+(?:a\s+doplňuje\s+)?takto|\b[Rr]uší\s+se\b|\b[Zz]rušuj[eí]\s+se\b|\btakto\s*:)')
LABEL = re.compile(r'^(?:\(?\d+[a-z]?[.)]|[a-z]\))\s+')
MONTHS = {'ledna': 1, 'února': 2, 'března': 3, 'dubna': 4, 'května': 5, 'června': 6, 'července': 7, 'srpna': 8,
          'září': 9, 'října': 10, 'listopadu': 11, 'prosince': 12}
DATE = re.compile(r'(\d{1,2})\.\s*(' + '|'.join(MONTHS) + r')\s+(\d{4})')
DATE_NUM = re.compile(r'\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b')
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
ORD = {'první': 1, 'druhá': 2, 'třetí': 3, 'čtvrtá': 4, 'pátá': 5, 'šestá': 6, 'sedmá': 7, 'osmá': 8, 'devátá': 9,
       'desátá': 10, 'jedenáctá': 11, 'dvanáctá': 12, 'třináctá': 13, 'čtrnáctá': 14, 'patnáctá': 15, 'šestnáctá': 16,
       'sedmnáctá': 17, 'osmnáctá': 18, 'devatenáctá': 19, 'dvacátá': 20}
ORD_STEM = {k[:-1]: v for k, v in ORD.items()}       # první -> prv(ní/ní), druhá -> druh(á/é/ou)


def roman(s):
    s = s.upper()
    if not s or any(ch not in ROMAN for ch in s):
        return None
    tot = 0
    for i, ch in enumerate(s):
        v = ROMAN[ch]
        tot += -v if i + 1 < len(s) and ROMAN[s[i + 1]] > v else v
    return tot


def num(s):
    if s is None:
        return None
    if s.isdigit():
        return str(int(s))
    r = roman(s)
    if r:
        return str(r)
    m = re.match(r'^(\d+)\s*([a-z]{1,2})$', s)
    if m:
        return str(int(m.group(1))) + m.group(2)
    return s


def ordinal(word):
    w = word.lower()
    if w in ORD:
        return ORD[w]
    for stem, v in ORD_STEM.items():
        if w.startswith(stem) and len(w) - len(stem) <= 3:
            return v
    return None


def mask_quotes(t):
    return QUOTE.sub(lambda m: '„' + ' ' * (len(m.group(0)) - 2) + '“', t)


def targets(t):
    """Acts cited outside quotes, in order of appearance: [(start, 'sb/YYYY/N')]."""
    mt = mask_quotes(t)
    out = [(m.start(), f'sb/{m.group(2)}/{int(m.group(1))}') for m in CIT.finditer(mt)]
    out += [(m.start(), f'sb/{m.group(1)}/{int(m.group(2))}') for m in CIT_OLD.finditer(mt)]
    return sorted(out)


def iso(d, mon, y):
    return f'{int(y):04d}-{MONTHS[mon]:02d}-{int(d):02d}'


def expand(a, b):
    """§ 43 až 46 -> 43..46 (numbers with the same or no letter)."""
    ma, mb = re.match(r'^(\d+)([a-z]*)$', a or ''), re.match(r'^(\d+)([a-z]*)$', b or '')
    if not ma or not mb:
        return [x for x in (a, b) if x]
    x, y = int(ma.group(1)), int(mb.group(1))
    if y < x or y - x > 400:
        return [a, b]
    out = [str(i) for i in range(x, y + 1)]
    if ma.group(2):
        out[0] = a
    if mb.group(2):
        out[-1] = b
    return out


PAR = re.compile(r'§§?\s*(\d+[a-z]{0,2})\b((?:\s*(?:,|a|až|-|–|nebo)\s*(?:§\s*)?\d+[a-z]{0,2}\b)*)')
ODST = re.compile(r'\b(?:odst\.|odstav(?:ec|ce|ci|cích|ců|cem))\s*(\d+)((?:\s*(?:,|a|až|-|–|nebo)\s*\d+\b)*)')
CL = re.compile(r'\b(?:[čČ]l\.|[čČ]lán(?:ek|ku|ky|cích|ků))\s*([IVXLC]+|\d+[a-z]?)\b((?:\s*(?:,|a|až|-|–)\s*(?:[IVXLC]+|\d+)\b)*)')
PRIL = re.compile(r'\b[Pp]říloh(?:a|y|u|ou|ách|ám|e)\b(?:\s*(?:č\.|číslo)\s*(\d+[a-z]?)((?:\s*(?:,|a|až)\s*\d+)*))?')
PPC = re.compile(r'\b[Pp]oznám(?:ka|ky|ce|ek|kách)\s+pod\s+čarou\s*(?:(?:č\.|číslo)\s*)?(\d+[a-z]?)?((?:\s*(?:,|a|až|-|–)\s*\d+[a-z]?)*)')
DIV = re.compile(r'\b(část|hlav|díl|oddíl|pododdíl)\w*\s+(?:č\.\s*)?([IVXLC]+\b|\d+[A-Za-z]?\b|[a-zěščřžýáíéůú]+)')
WHOLE = re.compile(r'v celém textu|v celém zákoně|v celé vyhlášce|v celém nařízení|ve všech ustanoveních|v textu (?:zákona|vyhlášky|nařízení)', re.I)


def listnums(first, rest):
    nums = [first]
    if rest:
        toks = re.findall(r'(až|-|–)?\s*(?:§\s*)?([IVXLC]+|\d+[a-z]{0,2})\b', rest)
        for rng, n in toks:
            n = n.replace(' ', '')
            if rng and nums:
                nums = nums[:-1] + expand(nums[-1], n)
            else:
                nums.append(n)
    return [num(n.replace(' ', '')) for n in nums if n]


def refs_of(text, ctx=None):
    """Provisions a point's instruction text names: [(kind, number, odst or None)]; ('*', '*', None) for the whole act.
    ctx is the § the previous text named (for "Dosavadní odstavce 5 a 6 ...")."""
    t = mask_quotes(text)
    # Cut the target citation clause: "zákona č. X/Y Sb., o ..., ve znění ..." names no provision of the target.
    out = []
    if WHOLE.search(t):
        out.append(('*', '*', None))
    last = ctx
    pos = 0
    items = []
    for m in PAR.finditer(t):
        items.append((m.start(), 'par', listnums(m.group(1).replace(' ', ''), m.group(2)), m.end()))
    for m in CL.finditer(t):
        items.append((m.start(), 'cl', listnums(m.group(1), m.group(2)), m.end()))
    for m in PRIL.finditer(t):
        items.append((m.start(), 'priloha', listnums(m.group(1), m.group(2)) if m.group(1) else ['*'], m.end()))
    for m in PPC.finditer(t):
        items.append((m.start(), 'ppc', listnums(m.group(1), m.group(2)) if m.group(1) else ['*'], m.end()))
    for m in DIV.finditer(t):
        w = m.group(1).lower()
        kind = {'část': 'cast', 'hlav': 'hlava', 'díl': 'dil', 'oddíl': 'oddil', 'pododdíl': 'pododdil'}[w]
        v = m.group(2)
        n = str(ordinal(v)) if ordinal(v) else num(v) if (v.isdigit() or roman(v) or re.match(r'^\d+[A-Za-z]$', v)) else None
        if n:
            items.append((m.start(), kind, [n], m.end()))
    odsts = [(m.start(), listnums(m.group(1), m.group(2))) for m in ODST.finditer(t)]
    items.sort()
    for i, (start, kind, nums, end) in enumerate(items):
        nxt = items[i + 1][0] if i + 1 < len(items) else len(t)
        if kind in ('par', 'cl'):
            last = (kind, nums[-1])
            ods = [o for s, os in odsts if end <= s < nxt for o in os]
            # "odst." right after the number belongs to it; "se odstavec 4 zrušuje" later in the sentence too.
            for n in nums:
                out.append((kind, n, None))
            if len(nums) == 1:
                for o in ods:
                    out.append((kind, nums[0], o))
        else:
            for n in nums:
                out.append((kind, n, None))
        pos = end
    if not any(k in ('par', 'cl') for _, k, _, _ in items) and ctx and odsts:
        for s, os in odsts:
            for o in os:
                out.append((ctx[0], ctx[1], o))
    seen, res = set(), []
    for r in out:
        if r not in seen:
            seen.add(r)
            res.append(r)
    return res, last


OLDQ = re.compile(r'^\s*(?:se\s+)?(?:nahrazuj\w*|zrušuj\w*|vypouští|vypouštějí|nahradí|vypustí|zruší)')


def quotes_of(text):
    """(old, new): quoted words a point removes or replaces, and quoted words it inserts."""
    old, new = [], []
    for m in QUOTE.finditer(text):
        q = m.group(0)[1:-1].strip()
        if len(q) < 1:
            continue
        after = text[m.end():m.end() + 40]
        (old if OLDQ.match(after) else new).append(q)
    return old, new


def strip_quote(t):
    t = t.strip()
    if t.startswith('„'):
        t = t[1:]
    t = re.sub(r'“\s*\.?\s*$', '', t)
    return t.strip()


def effect_clauses(frs):
    """The act's commencement text: [(date or 'vyhlaseni', text)] from fragments saying "nabývá účinnosti"."""
    out = []
    for path, typ, text, odl in frs:
        if 'účinnosti' not in text or not re.search(r'nabýv\w* účinnosti|účinnosti dnem|nabude účinnosti', text):
            continue
        if text.lstrip().startswith('„'):
            continue
        out.append(text)
    return out


def parse_effect(texts):
    """Clauses of the commencement provisions: [(day, exception text)] — each date with the words that precede it up
    to the previous date (the provisions it applies to). The first date of "Tento zákon nabývá účinnosti dnem X" is
    the general one."""
    res = []
    for t in texts:
        prev = 0
        found = []
        for m in DATE.finditer(t):
            found.append((m.start(), m.end(), iso(m.group(1), m.group(2), m.group(3))))
        for m in DATE_NUM.finditer(t):
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12:
                found.append((m.start(), m.end(), f'{y:04d}-{mo:02d}-{d:02d}'))
        for s, e, day in sorted(found):
            res.append((day, t[prev:s], t[e:e + 300]))
            prev = e
    return res


def build_act(act, rows):
    """rows: [(path, typ, text_html, odl, hier)] of one act's promulgated version."""
    rows.sort(key=lambda r: R.hkey(r[4] or '/'))
    frs = []
    for path, typ, html_, odl, hier in rows:
        t = R.inline(html_) if html_ else ''
        frs.append((path, typ or '', t, odl))
    intros = []
    for i, (path, typ, t, odl) in enumerate(frs):
        if not t or t.startswith('„') or path.startswith(('prefix', 'postfix', 'poznamkypodcarou')):
            continue
        parts = path.split('/')
        if any(p.startswith('bod_') for p in parts[:-1]):
            continue
        if 'č.' not in t and 'ze dne' not in t:
            continue
        tg = targets(t)
        if not tg:
            continue
        mt = mask_quotes(t)
        v = VERB.search(mt)
        if not v:
            continue
        # The target is the first act cited before the verb (or the first cited at all when the verb comes first).
        before = [x for x in tg if x[0] < v.start()]
        target = (before or tg)[0][1]
        if target == act:
            continue
        intros.append((i, target))
    blocks = []
    intro_idx = {i for i, _ in intros}
    for k, (i, target) in enumerate(intros):
        path = frs[i][0]
        last = path.split('/')[-1]
        if last.startswith('bod_'):
            container = path
            members = [i] + [j for j in range(i + 1, len(frs)) if frs[j][0].startswith(path + '/')]
        else:
            container = path.rsplit('/', 1)[0] if '/' in path else ''
            members = [i]
            for j in range(i + 1, len(frs)):
                if j in intro_idx:
                    break
                p = frs[j][0]
                if container and not p.startswith(container + '/'):
                    break
                members.append(j)
        # Points: the intro, then one per child of the container (bod_N, odst_N, ...), in order.
        points = []
        groups = {}
        order = []
        for j in members:
            p = frs[j][0]
            if j == i:
                key = '@intro'
            else:
                rest = p[len(container) + 1:] if container else p
                key = rest.split('/')[0]
                if key.startswith('frag_') and order and order[-1] != '@intro' and not frs[j][2].lstrip().startswith(('V ', 've ', 'Ve ', 'Za ', '§')):
                    key = order[-1]          # a loose fragment belongs to the point before it
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(j)
        ctx = None
        art = None
        m = re.search(r'(?:^|/)(cl_\w+|par_\w+)', container)
        if m:
            art = m.group(1)
        for key in order:
            js = groups[key]
            head = frs[js[0]][2]
            # Instruction text is what lies outside quotes; quoted content runs from „ to the matching “, across
            # fragments ("§ 12n zní: „§ 12n ... (1) ... (2) ...“.").
            instr, content, bal = [], [], 0
            for j in js:
                tt = frs[j][2]
                if not tt:
                    continue
                if bal <= 0 and not tt.lstrip().startswith('„'):
                    instr.append(tt)
                elif j != js[0]:
                    content.append(strip_quote(tt))
                bal = max(0, bal + tt.count('„') - tt.count('“'))
            refs, ctx2 = refs_of(' '.join(instr), ctx)
            if key == '@intro':
                # The intro names provisions only after the target's citation clause ("se v § 2 ...").
                tpos = targets(head)
                cut = head
                if tpos:
                    tail = mask_quotes(head)
                    vv = VERB.search(tail)
                    cut = head[:tpos[0][0]] + ' ' + head[vv.start():] if vv else head[:tpos[0][0]]
                refs, ctx2 = refs_of(cut, None)
            if not refs and key != '@intro' and points and points[0]['key'] == '@intro':
                refs = [r for r in points[0]['refs']]
            ctx = ctx2 or ctx
            old, new = [], []
            for tt in instr:
                o, n = quotes_of(tt)
                old += o
                new += n
            odls = sorted({frs[j][3] for j in js if frs[j][3]})
            bm = re.match(r'^bod_(\w+)', key)
            points.append({'key': key, 'path': frs[js[0]][0], 'point': bm.group(1) if bm else None,
                           'head': head[:600], 'refs': refs, 'old': old, 'new': new,
                           'content': [c[:400] for c in content if c][:60], 'odl': frs[js[0]][3], 'odls': odls})
        blocks.append({'target': target, 'act': act, 'article': art, 'container': container, 'intro_path': path,
                       'intro': frs[i][2][:600], 'points': points})
    eff = effect_clauses(frs)
    own = sorted({f[3] for f in frs if f[3]})
    return blocks, eff, own


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    a = ap.parse_args()
    db = Path(a.db)
    src = sqlite3.connect(f'file:{db / "pv.sqlite"}?mode=ro', uri=True)
    out_p = db / 'blocks.sqlite'
    if out_p.exists():
        out_p.unlink()
    out = sqlite3.connect(out_p)
    out.execute('create table blocks (target text, act text, article text, intro_path text, intro text, data text)')
    out.execute('create table acts_dates (act text primary key, own text, effect text)')
    t0 = time.time()
    cur = src.execute('select p.act, p.path, f.typ, f.text, p.odl, p.hier from pvf p left join fr f on f.fid = p.fid order by p.act')
    act, rows, n, nb = None, [], 0, 0

    def flush():
        nonlocal nb
        if not act:
            return
        blocks, eff, own = build_act(act, rows)
        for b in blocks:
            out.execute('insert into blocks values (?,?,?,?,?,?)', (b['target'], b['act'], b['article'], b['intro_path'],
                                                                    b['intro'], json.dumps(b, ensure_ascii=False)))
        nb += len(blocks)
        out.execute('insert or replace into acts_dates values (?,?,?)', (act, json.dumps(own), json.dumps(eff, ensure_ascii=False)))
    for r in cur:
        if r[0] != act:
            flush()
            act, rows = r[0], []
            n += 1
            if n % 2000 == 0:
                out.commit()
                print(f'{n} acts, {nb} blocks, {time.time() - t0:.0f}s', flush=True)
        rows.append((r[1], r[2], r[3], r[4], r[5]))
    flush()
    out.execute('create index blocks_target on blocks(target)')
    out.execute('create index blocks_act on blocks(act)')
    out.commit()
    print(f'done {n} acts, {nb} blocks, {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
