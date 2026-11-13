"""Resolve each change credited to e-Sbírka to the act that made it, from the amending acts' own amendment points.

    python -X utf8 resolve.py --events ../events.jsonl --db ../db --out ../out

For every changed provision of every publisher change (events.jsonl), the candidates are the acts whose promulgated
text holds a block amending that act (blocks.sqlite), plus the act itself where its own text carries a later
in-force day (a delayed provision). A candidate's point counts when
  - its day is the change's in-force day: the point's own day from e-Sbírka (odlišná účinnost), or the day the
    act's commencement provisions give for that point ("čl. I bodu 5 ... nabývá účinnosti dnem 1. července 2006"),
    or, when neither says, the act's in-force day (metadata);
  - it names the changed provision (refs: § / čl. / příloha / poznámka / část ..., with odstavec where both give one),
    or the whole text ("v celém textu");
  - and the words it quotes are where they should be in the commit's diff (inserted words among the added lines,
    replaced or removed words among the removed lines).
Confidence, per provision:
  high     one act; a point in force that day names the provision (to the odstavec where the change has one) and its
           quoted words, if it quotes any, are found in the diff
  medium   one act; a point in force that day names the provision only at § level, or names it but none of its quoted
           words are found, or a whole-text point whose quoted words are found
  low      one act amends this act with effect that day, but no point of it names the provision (or its day is only
           possible: one of the act's commencement days, not pinned to the point)
  ambiguous  several acts tie at the best level: all are listed
  unresolved no act amends this act with effect that day, in the texts e-Sbírka publishes
No model is used: rules and string matching only.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(next(p for p in (HERE.parents[2] / 'tools' / 'build', HERE.parent / 'clone' / 'tools' / 'build')
                           if p.exists())))
import blocks as B  # noqa: E402
import render as R  # noqa: E402

ESB = 'https://www.e-sbirka.cz/eli/cz/'
KIND = {'§': 'par', 'čl.': 'cl', 'článek': 'cl', 'příloha': 'priloha', 'pozn.': 'ppc', 'část': 'cast', 'hlava': 'hlava',
        'díl': 'dil', 'oddíl': 'oddil', 'pododdíl': 'pododdil', 'kapitola': 'kapitola'}
LEVELS = {'high': 3, 'medium': 2, 'low': 1}
LABEL_OF = {'par': '§', 'cl': 'čl.', 'priloha': 'příloha', 'ppc': 'pozn.', 'cast': 'část', 'hlava': 'hlava', 'dil': 'díl',
            'oddil': 'oddíl', 'pododdil': 'pododdíl'}


def norm_unit(u):
    """A unit label of the build ('§ 3 odst. 2', 'čl. 7', 'pozn. 1:2', '„§ 16 *(účinnost od ...)* odst. 1')
    -> (kind, number, odstavec or None); ('other', label, None) for anything else."""
    s = u.strip().lstrip('„').strip()
    s = re.sub(r'\s*\*\(účinnost od [^)]*\)\*', '', s)
    m = re.match(r'^(§|čl\.|Článek|příloha|pozn\.|část|hlava|díl|oddíl|pododdíl|kapitola)\s*([0-9IVXLC]+[A-Za-z]{0,2}|\*+)'
                 r'\.?(?:\s+([a-z]))?(?::\d+)?\.?(?:\s+odst\.\s*(\d+[a-z]?)(?::\d+)?)?$', s)
    if not m:
        return ('other', u, None)
    kind = KIND[m.group(1).lower()]
    n = m.group(2) + (m.group(3) or '')
    if kind in ('cl', 'cast', 'hlava', 'dil', 'oddil') and re.fullmatch(r'[IVXLC]+', n):
        n = B.num(n)
    elif re.fullmatch(r'\d+[a-zA-Z]{0,2}', n):
        n = str(int(re.match(r'\d+', n).group(0))) + n[len(re.match(r'\d+', n).group(0)):].lower()
    return (kind, n, m.group(4))


def match_level(unit, refs):
    """How a point's refs cover a unit: 'exact', 'provision', 'whole' or None."""
    kind, n, odst = unit
    best = None
    if odst:
        named = {ro for rk, rn, ro in refs if rk == kind and rn == n and ro}
        if named and odst not in named:
            # The point names other odstavce of this provision, not this one.
            refs = [r for r in refs if not (r[0] == kind and r[1] == n)]
    for rk, rn, ro in refs:
        if rk == '*':
            best = best or 'whole'
            continue
        if rk != kind:
            continue
        if rn != n and rn != '*':
            continue
        if rn == '*':
            lvl = 'provision'
        elif odst and ro:
            if odst != ro:
                continue
            lvl = 'exact'
        elif not odst and not ro:
            lvl = 'exact'
        else:
            lvl = 'provision'
        if lvl == 'exact':
            return 'exact'
        best = 'provision' if best in (None, 'whole') else best
    return best


def norm_text(t):
    t = t.replace('\\', '')
    t = re.sub(r'\s+', ' ', t)
    return t


def quote_check(point, added, removed):
    """(hits, misses): quoted words found where they should be in the diff, and those found nowhere."""
    hits = misses = 0
    for q in point['new']:
        q = norm_text(q).strip()
        if len(q) < 3:
            continue
        if q in added and q not in removed:
            hits += 1
        elif q not in added:
            misses += 1
    for q in point['old']:
        q = norm_text(q).strip()
        if len(q) < 3:
            continue
        if q in removed and q not in added:
            hits += 1
        elif q not in removed:
            misses += 1
    for c in point['content'][:20]:
        c = norm_text(c).strip()
        c = re.sub(r'^(?:\(\d+[a-z]?\)|[a-z]\)|\d+\.)\s+', '', c)[:80]
        if len(c) < 12:
            continue
        if c in added:
            hits += 1
        else:
            misses += 1
    return hits, misses


POINTS_RE = re.compile(r'\b(?:čl\.|článku)\s*([IVXLC]+|\d+)\s*,?\s*(?:bod(?:u|ů|y|ech)?|body)\s*([0-9][0-9 ,aaž–-]*)')
ART_RE = re.compile(r'\b(?:čl\.|článku|článků)\s*([IVXLC]+|\d+)\b(?!\s*,?\s*bod)')
PART_RE = re.compile(r'\bčást(?:i|í)?\s+(\w+)')


def point_days(act_dates, inforce):
    """From an act's commencement clauses: {(article number, point number or None): day}, {part number: day}."""
    exc, parts = {}, {}
    for day, before, after in act_dates:
        for m in POINTS_RE.finditer(before):
            art = B.num(m.group(1))
            nums = re.findall(r'(\d+)\s*(?:(až|–|-)\s*(\d+))?', m.group(2))
            for a, rng, b in nums:
                if rng and b:
                    for k in range(int(a), int(b) + 1):
                        exc[(art, str(k))] = day
                else:
                    exc[(art, str(int(a)))] = day
        for m in ART_RE.finditer(before):
            exc.setdefault((B.num(m.group(1)), None), day)
        for m in PART_RE.finditer(before):
            o = B.ordinal(m.group(1))
            if o:
                parts.setdefault(str(o), day)
    return exc, parts


def point_day(block, point, exc, parts, inforce):
    """(day, how): the point's own odlišná účinnost, a commencement exception naming it, or the act's in-force day."""
    if point.get('odl'):
        return point['odl'], 'odlišná účinnost'
    art = None
    m = re.search(r'cl_(\w+)', block.get('container') or '')
    if m:
        art = B.num(m.group(1))
    if art and point.get('point') and (art, point['point']) in exc:
        return exc[(art, point['point'])], 'commencement clause (point)'
    if art and (art, None) in exc:
        return exc[(art, None)], 'commencement clause (article)'
    m = re.search(r'cast_(\d+)', block.get('container') or '')
    if m and m.group(1) in parts:
        return parts[m.group(1)], 'commencement clause (part)'
    return inforce, 'act in force'


class Store:
    def __init__(self, db):
        self.meta = sqlite3.connect(f'file:{db / "meta.sqlite"}?mode=ro', uri=True)
        self.bl = sqlite3.connect(f'file:{db / "blocks.sqlite"}?mode=ro', uri=True)
        self.pv = sqlite3.connect(f'file:{db / "pv.sqlite"}?mode=ro', uri=True)
        cols = [d[1] for d in self.meta.execute('pragma table_info(acts)')]
        self.acts = {r[0]: dict(zip(cols, r)) for r in self.meta.execute('select * from acts')}
        self._blocks = {}
        self._dates = {}

    def name(self, act):
        info = self.acts.get(act)
        if not info:
            coll, year, n = act.split('/')[:3]
            return f'Předpis č. {n}/{year} Sb.'
        kind = R.DRUH.get(info.get('druh') or '', None) or R.DRUH.get(info.get('podtyp') or '', 'Předpis')
        return f"{kind} č. {info['citation']}"

    def blocks_for(self, target):
        if target not in self._blocks:
            self._blocks[target] = [json.loads(d) for (d,) in self.bl.execute('select data from blocks where target=?', (target,))]
        return self._blocks[target]

    def dates(self, act):
        if act not in self._dates:
            row = self.bl.execute('select own, effect from acts_dates where act=?', (act,)).fetchone()
            own = json.loads(row[0]) if row else []
            eff = B.parse_effect(json.loads(row[1])) if row else []
            inforce = (self.acts.get(act) or {}).get('in_force_from')
            exc, parts = point_days(eff, inforce)
            alld = set(own) | {d for d, _, _ in eff} | ({inforce} if inforce else set())
            self._dates[act] = (inforce, exc, parts, alld)
        return self._dates[act]

    def own_delayed(self, act, day):
        """The act's own fragments whose odlišná účinnost is that day: their units."""
        rows = self.pv.execute('select path from pvf where act=? and odl=?', (act, day)).fetchall()
        return [R.unit_of(p) for (p,) in rows if p]


def evaluate(store, ev):
    """[(unit label, verdict dict)] for one event."""
    X, D = ev['act'], ev['day']
    added = norm_text('\n'.join(ev['added']))
    removed = norm_text('\n'.join(ev['removed']))
    units = ev['units'] or ['text']
    # Candidate points: every point of every block that amends X.
    cands = defaultdict(list)          # act -> [(block, point, day, how, qhits, qmiss)]
    for b in store.blocks_for(X):
        A = b['act']
        if A == X:
            continue
        inforce, exc, parts, alld = store.dates(A)
        for p in b['points']:
            day, how = point_day(b, p, exc, parts, inforce)
            if day == D:
                dlev = 'exact'
            elif how == 'act in force' and D in alld:
                dlev = 'possible'
            else:
                continue
            h, mi = quote_check(p, added, removed)
            cands[A].append((b, p, dlev, how, h, mi))
    # The act's own delayed provisions (its promulgated text dates them to this day).
    own_units = set(store.own_delayed(X, D)) if store.acts.get(X, {}).get('in_force_from') != D else set()
    out = []
    for u in units:
        nu = norm_unit(u)
        per_act = {}
        for A, pts in cands.items():
            best = None
            for b, p, dlev, how, h, mi in pts:
                ml = match_level(nu, p['refs']) if nu[0] != 'other' else None
                quotes = h + mi
                if dlev == 'exact' and ml == 'exact' and (h > 0 or quotes == 0):
                    lvl = 'high'
                elif dlev == 'exact' and ml == 'provision' and h > 0:
                    lvl = 'high'
                elif dlev == 'exact' and ml in ('exact', 'provision'):
                    lvl = 'medium'
                elif dlev == 'exact' and ml == 'whole' and h > 0:
                    lvl = 'medium'
                elif dlev == 'exact' and nu[0] == 'other' and h > 0:
                    lvl = 'medium'
                elif dlev == 'possible' and ml in ('exact', 'provision') and h > 0:
                    lvl = 'medium'
                elif dlev == 'exact':
                    lvl = 'low'
                elif dlev == 'possible' and ml in ('exact', 'provision', 'whole'):
                    lvl = 'low'
                else:
                    continue
                key = (LEVELS[lvl], h, {'exact': 2, 'provision': 1}.get(ml, 0))
                if best is None or key > best[0]:
                    best = (key, lvl, b, p, how, h, mi, ml)
            if best:
                per_act[A] = best
        if own_units:
            ub = None
            for ou in own_units:
                if R.unit_label(ou) == u or R.unit_label(ou.split('/odst_')[0]) == u.split(' odst.')[0]:
                    ub = ou
                    break
            if ub:
                per_act[X] = ((LEVELS['high'], 0, 2), 'high', None, None, 'own odlišná účinnost', 0, 0, 'exact')
        if not per_act:
            out.append((u, {'confidence': 'unresolved', 'acts': [], 'evidence': f'no act in e-Sbírka\'s texts amends {X} with effect {D}'}))
            continue
        top = max(v[0][0] for v in per_act.values())
        tops = {A: v for A, v in per_act.items() if v[0][0] == top}
        if len(tops) > 1:
            # Quoted words found in the diff break a tie between acts at the same level.
            hmax = max(v[0][1] for v in tops.values())
            if hmax > 0:
                tops2 = {A: v for A, v in tops.items() if v[0][1] == hmax}
                if len(tops2) == 1:
                    tops = tops2
        if len(tops) > 1:
            # A point naming the odstavec beats one naming only the §.
            mmax = max(v[0][2] for v in tops.values())
            tops2 = {A: v for A, v in tops.items() if v[0][2] == mmax}
            if len(tops2) == 1 and mmax == 2:
                tops = tops2
        acts = sorted(tops, key=lambda a: (a.split('/')[1], a))
        verdict = {'confidence': tops[acts[0]][1] if len(acts) == 1 else 'ambiguous', 'acts': acts,
                   'level': tops[acts[0]][1], 'evidence': ' || '.join(evidence(store, A, tops[A], D) for A in acts)}
        out.append((u, verdict))
    return out


def evidence(store, A, best, D):
    key, lvl, b, p, how, h, mi, ml = best
    nm = store.name(A)
    if b is None:
        return f'{nm}: its own provision with odlišná účinnost {D}'
    where = []
    m = re.search(r'cast_(\d+)', b.get('container') or '')
    if m:
        where.append(f'část {m.group(1)}')
    if b.get('article'):
        k, _, n = b['article'].partition('_')
        where.append(('čl. ' if k == 'cl' else '§ ') + n)
    if p.get('point'):
        where.append(f"bod {p['point']}")
    head = p['head'] if p['key'] != '@intro' else b['intro']
    head = re.sub(r'\s+', ' ', head)
    if len(head) > 240:
        head = head[:239] + '…'
    tgt = re.sub(r'\s+', ' ', b['intro'])
    tgt = tgt[:160] + ('…' if len(tgt) > 160 else '')
    parts = [f"{nm}, {' '.join(where) or b['intro_path']}: „{head}“",
             f'target: „{tgt}“' if p['key'] != '@intro' else '',
             f'in force {D} ({how})',
             f'names: {ml or "no provision"}',
             f'quotes in diff: {h} found, {mi} not found' if h + mi else '']
    return '; '.join(x for x in parts if x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--events', required=True)
    ap.add_argument('--db', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    store = Store(Path(a.db))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    evs = [json.loads(l) for l in open(a.events, encoding='utf-8')]
    if a.limit:
        evs = evs[:a.limit]
    rows, ev_class = [], []
    for i, ev in enumerate(evs):
        res = evaluate(store, ev)
        classes = [v['confidence'] for _, v in res]
        if all(c in LEVELS for c in classes):
            ec = min(classes, key=lambda c: LEVELS[c])
        elif any(c in LEVELS for c in classes):
            ec = 'partial'
        elif all(c == 'ambiguous' for c in classes) or ('ambiguous' in classes and 'unresolved' not in classes):
            ec = 'ambiguous'
        elif 'ambiguous' in classes:
            ec = 'ambiguous'
        else:
            ec = 'unresolved'
        acts = sorted({A for _, v in res if v['confidence'] in LEVELS for A in v['acts']})
        ev_class.append({'commit': ev['commit'], 'path': ev['path'], 'day': ev['day'], 'branch': ev['branch'],
                         'class': ec, 'acts': acts, 'units': len(res)})
        for u, v in res:
            rows.append({'commit': ev['commit'], 'path': ev['path'], 'provision': u, 'in_force': ev['day'],
                         'act': ' | '.join(store.name(A) for A in v['acts']),
                         'act_eli': ' | '.join(ESB + A for A in v['acts']),
                         'evidence': v['evidence'], 'confidence': v['confidence']})
        if i % 500 == 0:
            print(i, flush=True)
    with open(out / 'credits.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['commit', 'path', 'provision', 'in_force', 'act', 'act_eli', 'evidence', 'confidence'],
                           lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(out / 'events_class.jsonl', 'w', encoding='utf-8', newline='\n') as fh:
        for e in ev_class:
            fh.write(json.dumps(e, ensure_ascii=False) + '\n')
    from collections import Counter
    print('events', Counter(e['class'] for e in ev_class))
    print('rows', Counter(r['confidence'] for r in rows))


if __name__ == '__main__':
    main()
