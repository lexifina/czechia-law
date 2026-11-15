"""Compute every number for the 20 charts into <build>/data.json.

    python prep.py <build-dir>

Reads <build>/commits.json, <build>/paths.json (from make.py) and the tables archived into <build>/repo/
(navrhy/data/ and data/). Every rule that reads a category out of a title is in this file.
"""
import collections, csv, glob, json, os, re, statistics, sys
from datetime import date

B = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '.build')
R = os.path.join(B, 'repo')
csv.field_size_limit(10 ** 9)
C = json.load(open(os.path.join(B, 'commits.json'), encoding='utf-8'))
P = json.load(open(os.path.join(B, 'paths.json'), encoding='utf-8'))
OUT, PROFILE = {}, {}
D = lambda s: date.fromisoformat(s[:10])


def rd(path):
    return list(csv.DictReader(open(os.path.join(R, path), encoding='utf-8')))


def tr(r, k):
    v = r['t'].get(k)
    return v[0].strip() if v else None


def files(r):
    for p in P.get(r['h'], []):
        st, _, f = p.partition('\t')
        yield st[:1], f


def kind_of(author):
    m = re.match(r'^(.*?) č\.', author)
    return m.group(1) if m else author


def first_line_title(r):
    """'NN/YYYY Sb. (Title): first version...' -> Title; else the part of the first body line after the colon."""
    line = r['body'].split('\n')[0]
    i, j = line.find(' ('), line.rfind('): ')
    if 0 < i < j:
        return line[i + 2:j]
    m = re.search(r':\s*(.*)', line)
    return (m.group(1) if m else line).strip()


# ------------------------------------------------------------------ indexes over the history
first_add = {}          # path -> commit that added it first (oldest)
for r in reversed(C):
    for st, f in files(r):
        if st == 'A' and f not in first_add:
            first_add[f] = r
tree_now = set()
for f in first_add:
    pass
# files present at the tip = added and not deleted afterwards (walk newest -> oldest)
seen_state = {}
for r in C:  # newest first
    for st, f in files(r):
        if f not in seen_state:
            seen_state[f] = st
tree_now = {f for f, st in seen_state.items() if st != 'D'}

law_commits = []  # commits on sb/ that carry the law (not as-promulgated, not corrections, not docs)
for r in C:
    k = tr(r, 'Kind')
    if k in ('as-promulgated', 'correction', 'documentation', 'data', 'tooling', 'record', 'draft', 'case-law'):
        continue
    fs = [(st, f) for st, f in files(r) if f.startswith('sb/') and f.endswith('.md')]
    if fs and tr(r, 'In-force'):
        law_commits.append((r, fs))
print('law commits', len(law_commits))

titles = {}  # sb path -> title
for f, r in first_add.items():
    if f.startswith(('sb/', 'ul/', 'sbms/')):
        titles[f] = first_line_title(r)
promulgated_only = {f for f, r in first_add.items() if tr(r, 'Kind') == 'as-promulgated'}


def act_path(author):
    m = re.search(r'č\. (n?\d+)/(\d{4}) Sb\.$', author)
    return f'sb/{m.group(2)}/{m.group(1)}.md' if m else None


# ------------------------------------------------------------------ I. Parliament
bills = rd('navrhy/data/bills.csv')
stages = rd('navrhy/data/bill-stages.csv')
st_by = collections.defaultdict(list)
for s in stages:
    st_by[s['psp_id']].append(s)
TERMS = ['1993', '1996', '1998', '2002', '2006', '2010', '2013', '2017', '2021', '2025']
TERM_SPAN = {'1993': '1993–1996', '1996': '1996–1998', '1998': '1998–2002', '2002': '2002–2006', '2006': '2006–2010',
             '2010': '2010–2013', '2013': '2013–2017', '2017': '2017–2021', '2021': '2021–2025', '2025': '2025–'}
is_bill = lambda b: b['kind'] in ('Vládní návrh zákona', 'Návrh zákona') and '/' not in b['print'] and not b['print'].endswith('-E')


def became_law(b):
    return bool(b['became']) and ('Zákon' in b['became_kind'] or 'Ústavní zákon' in b['became_kind'])


def initiator(b):
    t = b['initiator_type']
    if t == 'vláda': return 'gov'
    if t in ('poslanec', 'skupina poslanců'): return 'mps'
    if t == 'Senát': return 'senate'
    if t == 'zastupitelstvo kraje': return 'region'
    if b['kind'] == 'Vládní návrh zákona': return 'gov'
    return 'other'


# c01: who proposes, who succeeds
c01 = []
cnt = collections.Counter()
for b in bills:
    if not is_bill(b): continue
    i = initiator(b)
    cnt[(b['term'], i, 'n')] += 1
    if became_law(b): cnt[(b['term'], i, 'law')] += 1
for t in TERMS:
    row = {'t': t, 'span': TERM_SPAN[t]}
    for i in ('gov', 'mps', 'senate', 'region', 'other'):
        row[i] = [cnt[(t, i, 'n')], cnt[(t, i, 'law')]]
    c01.append(row)
OUT['c01'] = c01
print('c01', [(r['t'], r['gov'], r['mps'], r['other']) for r in c01])

# c02: days from submission to promulgation, laws only; § 90(2) approvals flagged
c02 = []
for t in TERMS:
    pts = []
    for b in bills:
        if b['term'] != t or not is_bill(b) or not became_law(b) or not b['submitted'] or not b['became_published']: continue
        d = (D(b['became_published']) - D(b['submitted'])).days
        if d < 0: continue
        fast = any(s['stage'].startswith('1. čtení (§ 90') and s['action'] == 'souhlas s RJ' for s in st_by[b['psp_id']])
        pts.append((d, 1 if fast else 0, 1 if initiator(b) == 'gov' else 0))
    if not pts: continue
    ds = sorted(p[0] for p in pts)
    q = statistics.quantiles(ds, n=4) if len(ds) > 3 else [ds[0], ds[len(ds) // 2], ds[-1]]
    c02.append({'t': t, 'span': TERM_SPAN[t], 'n': len(ds), 'med': statistics.median(ds), 'q1': q[0], 'q3': q[2],
                'fast': sum(p[1] for p in pts), 'pts': [[p[0], p[1]] for p in pts]})
OUT['c02'] = c02
print('c02', [(r['t'], r['n'], r['med'], r['fast']) for r in c02])

# c03: what the Senate does with the bills it receives
c03 = []
oc = collections.Counter()
for b in bills:
    if not is_bill(b) and b['kind'] != 'Zákonné opatření Senátu': continue
    ss = st_by[b['psp_id']]
    acts = [(s['stage'], s['action']) for s in ss]
    if ('Senát', 'doručen') not in acts: continue
    if b['term'] not in TERMS: continue
    returned = ('Sněmovna (Senát)', 'vrácen') in acts
    rejected = ('Sněmovna (Senát)', 'zamítnut') in acts
    if returned:
        if ('Prezident', 'pozm. přijat') in acts: o = 'ret_acc'
        elif any(a == 'setrváno' for _, a in acts): o = 'ret_ins'
        elif became_law(b): o = 'ret_ins'
        else: o = 'ret_fail'
    elif rejected:
        o = 'rej_over' if (any(a == 'setrváno' for _, a in acts) or became_law(b)) else 'rej_fail'
    elif ('Prezident', 'nezabýval se') in acts: o = 'ignored'
    elif ('Prezident', 'schválen') in acts or ('Prezident', 'schváleno') in acts or ('Prezident', 'souhlas') in acts: o = 'approved'
    else: o = 'pending'
    oc[(b['term'], o)] += 1
KEYS3 = ['approved', 'ignored', 'ret_acc', 'ret_ins', 'ret_fail', 'rej_over', 'rej_fail', 'pending']
for t in TERMS:
    if t == '1993': continue  # the Senate first sat in December 1996
    c03.append({'t': t, 'span': TERM_SPAN[t], **{k: oc[(t, k)] for k in KEYS3}})
OUT['c03'] = c03
print('c03', c03)

# c04: presidential vetoes
PRES = [('havel', '1993-02-02', '2003-02-02'), ('klaus', '2003-03-07', '2013-03-07'), ('zeman', '2013-03-08', '2023-03-08'), ('pavel', '2023-03-09', '2099-01-01')]
vetoes = {}
for b in bills:
    ss = st_by[b['psp_id']]
    v = [s for s in ss if s['stage'] == 'Sněmovna (Prezident)' and s['action'] == 'nepodepsal']
    if not v: continue
    d = min(s['date'] for s in v if s['date']) if any(s['date'] for s in v) else None
    if not d:
        continue
    p = next(k for k, a, z in PRES if a <= d <= z) if any(a <= d <= z for _, a, z in PRES) else 'havel'
    after = [s for s in ss if s['date'] and s['date'] >= d]
    over = became_law(b) or any(s['action'] == 'setrváno' and s['stage'] == 'Sbírka zákonů' for s in after)
    lapsed = not over and not any(s['stage'] == 'KONEC' for s in after)  # the term ended before the Chamber voted again
    vetoes[b['psp_id']] = {'d': d, 'p': p, 'o': 'lapsed' if lapsed else ('over' if over else 'kept'), 'title': b['title'], 'term': b['term'], 'print': b['print'], 'became': b['became']}
c04 = sorted(vetoes.values(), key=lambda v: v['d'])
OUT['c04'] = c04
print('c04', len(c04), collections.Counter((v['p'], v['o']) for v in c04))

# votes
votes = {}
for f in sorted(glob.glob(os.path.join(R, 'navrhy/data/votes/[0-9][0-9][0-9][0-9].csv'))):
    for v in csv.DictReader(open(f, encoding='utf-8')):
        votes[v['vote_id']] = v
mps = rd('navrhy/data/votes/poslanci.csv')
mp_list = {(m['term'], m['mp_id']): m['elected_for'] for m in mps}

# c05: party unity (Rice index) by electoral list and term
LISTNAME = {'ODS-KDS': 'ODS-KDS', 'ANO2011': 'ANO', 'PirSTAN': 'Piráti+STAN', 'Piráti': 'Piráti', 'CSSD': 'ČSSD', 'KSCM': 'KSČM', 'LB': 'LB',
            'K': 'Koalice', 'SPOLU': 'SPOLU', 'TOP09': 'TOP 09', 'VV': 'VV', 'Usvit': 'Úsvit', 'KDU-ČSL': 'KDU-ČSL', 'US': 'US', 'SPR': 'SPR-RSČ',
            'ODA': 'ODA', 'SPD': 'SPD', 'STAN': 'STAN', 'Moto': 'Motoristé', 'SZ': 'SZ', 'LSU': 'LSU', 'HSD-SMS': 'HSD-SMS', 'ODS': 'ODS'}
c05 = []
rice_all = collections.defaultdict(list)
for t in TERMS:
    f = os.path.join(R, f'navrhy/data/votes/{t}-poslanci.csv')
    with open(f, encoding='utf-8') as fh:
        rdr = csv.reader(fh)
        head = next(rdr)
        cols = [mp_list.get((t, h)) for h in head]
        acc = collections.defaultdict(list)
        part = collections.defaultdict(list)
        for row in rdr:
            v = votes.get(row[0])
            if not v or v['mode'] != 'N' or v['void'] == '1': continue
            yes = collections.Counter(); no = collections.Counter(); seats = collections.Counter(); here = collections.Counter()
            for c, x in zip(cols[1:], row[1:]):
                if not c or not x: continue
                seats[c] += 1
                if x == 'A': yes[c] += 1
                elif x in ('B', 'N'): no[c] += 1
                if x in ('A', 'B', 'N', 'C', 'F', 'K'): here[c] += 1
            for c in seats:
                n = yes[c] + no[c]
                if n >= 5:
                    acc[c].append(abs(yes[c] - no[c]) / n)
                part[c].append(here[c] / seats[c])
    size = collections.Counter(m['elected_for'] for m in mps if m['term'] == t)
    for c, xs in acc.items():
        if size[c] < 8 or len(xs) < 500: continue
        c05.append({'t': t, 'l': LISTNAME.get(c, c), 'k': c, 'rice': round(sum(xs) / len(xs), 4), 'nv': len(xs), 'mps': size[c],
                    'part': round(sum(part[c]) / len(part[c]), 4)})
OUT['c05'] = c05
print('c05', [(r['t'], r['l'], r['rice'], r['part']) for r in c05])

# c06: how big the majority is on the final vote of each law
c06 = []
for t in TERMS:
    pts = []
    for b in bills:
        if b['term'] != t or not is_bill(b): continue
        for s in st_by[b['psp_id']]:
            if s['stage'] == 'Odesíláno do Senátu' and s['action'] == 'souhlas' and s['vote_id'] in votes:
                v = votes[s['vote_id']]
                pts.append([int(v['yes']), int(v['no']), 1 if initiator(b) == 'gov' else 0, b['print']])
                break
    if pts:
        ys = [p[0] for p in pts]
        c06.append({'t': t, 'span': TERM_SPAN[t], 'n': len(pts), 'med': statistics.median(ys), 'ge120': sum(1 for y in ys if y >= 120),
                    'no0': sum(1 for p in pts if p[1] == 0), 'pts': [[p[0], p[1], p[2]] for p in pts]})
OUT['c06'] = c06
print('c06', [(r['t'], r['n'], r['med'], r['ge120'], r['no0']) for r in c06])

# c07: when the Chamber votes (weekday x hour)
grid = collections.Counter(); late = collections.Counter(); per_term = collections.Counter(); late_days = collections.Counter()
for v in votes.values():
    if not v['date'] or not v['time']: continue
    wd = D(v['date']).weekday(); h = int(v['time'][:2])
    grid[(wd, h)] += 1
    per_term[v['term']] += 1
    if h >= 22 or h < 6:
        late[v['term']] += 1
        if h < 6: late_days[v['date']] += 1
OUT['c07'] = {'grid': [[wd, h, n] for (wd, h), n in sorted(grid.items())], 'n': sum(grid.values()),
              'terms': [[t, per_term[t], late[t]] for t in TERMS], 'small_hours': sorted(late_days.items(), key=lambda x: -x[1])[:8]}
print('c07', OUT['c07']['terms'], OUT['c07']['small_hours'][:3])

# ------------------------------------------------------------------ II. The Collection of Laws
GROUP = {'Zákon': 'law', 'Ústavní zákon': 'law', 'Zákonné opatření': 'law', 'Zákonné opatření Senátu': 'law', 'Dekret': 'law', 'Ústavní dekret': 'law',
         'Nařízení vlády': 'govreg', 'Nařízení': 'govreg', 'Vyhláška vlády': 'govreg',
         'Vyhláška': 'decree', 'Opatření': 'decree',
         'Sdělení': 'notice', 'Oznámení': 'notice', 'Úplné znění': 'notice', 'Oprava chyby': 'notice'}
sb_first = {f: r for f, r in first_add.items() if f.startswith('sb/') and f.endswith('.md')}

# c08: items promulgated in the Sbírka each year, by kind
yk = collections.defaultdict(collections.Counter)
for f, r in sb_first.items():
    y = int(f.split('/')[1])
    yk[y][GROUP.get(kind_of(r['an']), 'other')] += 1
OUT['c08'] = [{'y': y, **yk[y]} for y in range(1945, 2027)]
PROFILE['sb_items'] = len(sb_first)
PROFILE['sb_items_1945'] = sum(sum(yk[y].values()) for y in range(1945, 2027))
print('c08', [(r['y'], sum(v for k, v in r.items() if k != 'y')) for r in OUT['c08'][::10]])

# c09: what is in force today (consolidated acts present in the tree), by kind and era of promulgation
ERAS = [('e1', 1918, 1938), ('e2', 1939, 1944), ('e3', 1945, 1947), ('e4', 1948, 1989), ('e5', 1990, 1992), ('e6', 1993, 2026)]
c09 = collections.defaultdict(collections.Counter)
c09n = collections.Counter()
for f, r in sb_first.items():
    if f not in tree_now or f in promulgated_only: continue
    g = GROUP.get(kind_of(r['an']), 'other')
    if g == 'notice': continue
    y = int(f.split('/')[1])
    e = next(k for k, a, z in ERAS if a <= y <= z)
    c09[g][e] += 1
    c09n[g] += 1
ul_now = [f for f in tree_now if f.startswith('ul/') and f.endswith('.md') and f not in promulgated_only]
OUT['c09'] = {'rows': [{'g': g, **c09[g]} for g in ('law', 'govreg', 'decree', 'other')], 'ul_in_force': len(ul_now)}
print('c09', OUT['c09'])

# c10: how many acts change each year (consolidated versions taking effect), by kind of the act changed
c10 = collections.defaultdict(collections.Counter)
amend_acts = collections.defaultdict(set)
for r, fs in law_commits:
    y = int(tr(r, 'In-force')[:4])
    if y < 1990 or y > 2026: continue
    for st, f in fs:
        if st != 'M': continue
        g = GROUP.get(kind_of(sb_first[f]['an']) if f in sb_first else 'Zákon', 'other')
        c10[y][g] += 1
    if r['an'] != 'e-Sbírka' and any(st == 'M' for st, _ in fs):
        amend_acts[y].add(r['an'])
OUT['c10'] = [{'y': y, **c10[y], 'acts': len(amend_acts[y])} for y in range(1990, 2027)]
print('c10', [(r['y'], r.get('law'), r['acts']) for r in OUT['c10'][::4]])

# c11: the most-changed laws: every day each changed
chg = collections.defaultdict(set)
for r, fs in law_commits:
    for st, f in fs:
        if st == 'M':
            chg[f].add(tr(r, 'In-force')[:10])
laws_only = [f for f in chg if f in sb_first and GROUP.get(kind_of(sb_first[f]['an'])) == 'law']
top = sorted(laws_only, key=lambda f: -len(chg[f]))[:25]
OUT['c11'] = [{'f': f, 'cit': re.sub(r'^sb/(\d+)/(n?\d+)\.md$', r'\2/\1 Sb.', f), 'title': titles.get(f, f), 'n': len(chg[f]),
               'first': tr(sb_first[f], 'In-force'), 'days': sorted(chg[f]), 'now': f in tree_now} for f in top]
print('c11', [(r['cit'], r['title'][:50], r['n']) for r in OUT['c11']])

# c12: the day of the year a change takes effect
c12 = collections.defaultdict(collections.Counter)
for r, fs in law_commits:
    if r['an'] == 'e-Sbírka': continue
    d = tr(r, 'In-force')[:10]
    m = re.search(r'/(\d{4}) Sb\.$', r['an'])
    if not m: continue
    y = int(m.group(1))  # the year the act making the change was promulgated
    if y < 1995 or y > 2026: continue
    md = d[5:]
    k = 'jan1' if md == '01-01' else 'jul1' if md == '07-01' else 'first' if d[8:] == '01' else 'other'
    c12[y][k] += 1
OUT['c12'] = [{'y': y, **c12[y]} for y in range(1995, 2027)]
print('c12', [(r['y'], r) for r in OUT['c12'][-8:]])

# c13: omnibus amending acts: how many acts one act changes
reach = collections.defaultdict(set)
for r, fs in law_commits:
    if r['an'] == 'e-Sbírka' or not r['an'].startswith(('Zákon', 'Ústavní zákon', 'Zákonné opatření')): continue
    own = act_path(r['an'])
    for st, f in fs:
        if st == 'M' and f != own:
            reach[r['an']].add(f)
c13 = []
for a, s in reach.items():
    m = re.search(r'(\d+)/(\d{4})', a)
    if not m: continue
    own = act_path(a)
    c13.append({'a': a, 'y': int(m.group(2)), 'n': len(s), 'title': titles.get(own, '')})
c13.sort(key=lambda x: -x['n'])
OUT['c13'] = {'pts': [[x['y'], x['n'], x['a'].replace('Zákon č. ', '')] for x in c13], 'top': c13[:12]}
print('c13', len(c13), [(x['a'], x['n'], x['title'][:60]) for x in c13[:10]])

# c16: the Úřední list 1945-1961
UL_TOPIC = [('prices', r'\bcen|cenov|cenách|ceník'), ('enterprise', r'národní(ch|m)? pod|podnik|znárodn|n\. p\.'), ('supply', r'zásobov|přídě|lístk|odbyt|dodáv|výkup|povinn\w+ dodáv|rozdělov'),
            ('labour', r'mzd|mzdov|pracovn|zaměstnan|dovolen|pojišt'), ('agri', r'zemědě|obil|dobyt|mléka|mlék|lesní|lesů|osiv|hospodářsk\w+ zvířat|sklizn'),
            ('transport', r'doprav|železnic|silnič|tarif|pošt'), ('tax', r'daň|daně|poplat|cl[ao]\b|celní')]
c16 = collections.defaultdict(collections.Counter)
ul_first = {f: r for f, r in first_add.items() if f.startswith('ul/') and f.endswith('.md')}
for f, r in ul_first.items():
    y = int(f.split('/')[1])
    t = titles.get(f, '').lower()
    k = next((k for k, rx in UL_TOPIC if re.search(rx, t)), 'other')
    c16[y][k] += 1
OUT['c16'] = {'rows': [{'y': y, **c16[y]} for y in sorted(c16)], 'n': len(ul_first), 'in_force': len(ul_now)}
print('c16', OUT['c16']['rows'])

# ------------------------------------------------------------------ III. Changes made from outside the Parliament
# c14: Constitutional Court findings that changed an act
c14y = collections.defaultdict(set)
c14acts = collections.defaultdict(set)
for r, fs in law_commits:
    if not r['an'].startswith('Nález'): continue
    y = int(tr(r, 'In-force')[:4])
    c14y[y].add(r['an'])
    for st, f in fs:
        if st in ('M', 'D'): c14acts[f].add(r['an'])
OUT['c14'] = {'years': [[y, len(c14y[y])] for y in range(1993, 2027)], 'n': len(set().union(*c14y.values())),
              'acts': [[f, re.sub(r'^sb/(\d+)/(n?\d+)\.md$', r'\2/\1 Sb.', f), titles.get(f, f), len(s)] for f, s in sorted(c14acts.items(), key=lambda x: -len(x[1]))[:12]]}
print('c14', OUT['c14']['n'], OUT['c14']['years'][-10:], OUT['c14']['acts'][:5])

# c15: acts that stop being in force (file removed), by year, and the acts that repeal most
c15 = collections.defaultdict(collections.Counter)
rep_by = collections.Counter()
for r, fs in law_commits:
    y = int(tr(r, 'In-force')[:4])
    for st, f in fs:
        if st != 'D': continue
        g = GROUP.get(kind_of(sb_first[f]['an']) if f in sb_first else 'Zákon', 'other')
        k = 'named' if r['an'] != 'e-Sbírka' else 'unnamed'
        c15[y][k] += 1
        if r['an'] != 'e-Sbírka': rep_by[r['an']] += 1
obs = collections.Counter()  # what the 2024 clean-up (276/2023 Sb.) removed, by era of promulgation
for r, fs in law_commits:
    if r['an'] != 'Zákon č. 276/2023 Sb.': continue
    for st, f in fs:
        if st == 'D':
            y = int(f.split('/')[1])
            obs[next(k for k, a, z in ERAS if a <= y <= z)] += 1
OUT['c15'] = {'years': [{'y': y, **c15[y]} for y in range(1990, 2027)], 'obs': dict(obs),
              'top': [[a, n, titles.get(act_path(a) or '', '')] for a, n in rep_by.most_common(10)]}
print('c15', OUT['c15']['years'][-12:], OUT['c15']['top'][:6])

# c17: EU-related government bills
c17 = []
for t in TERMS:
    g = [b for b in bills if b['term'] == t and is_bill(b) and initiator(b) == 'gov']
    e = [b for b in g if b['eu'] == '1']
    c17.append({'t': t, 'span': TERM_SPAN[t], 'gov': len(g), 'eu': len(e), 'eu_law': sum(1 for b in e if became_law(b)), 'gov_law': sum(1 for b in g if became_law(b))})
OUT['c17'] = c17
print('c17', c17)

# c18: treaty partners (Sbírka mezinárodních smluv since 2000; treaty notices in the Sbírka zákonů before)
CTRY = [('SK', r'slovensk'), ('AT', r'rakous'), ('DE', r'německ'), ('PL', r'polsk'), ('HU', r'maďar'), ('UA', r'ukrajin'), ('RU', r'rusk'),
        ('US', r'spojen\w* stát|americk'), ('FR', r'francouz|francie'), ('IT', r'itals|itálie'), ('ES', r'španěl'), ('PT', r'portugal'), ('BE', r'belgi'),
        ('NL', r'nizozem'), ('LU', r'lucember'), ('DK', r'dánsk|dánsko'), ('SE', r'švédsk'), ('NO', r'norsk|norsko'), ('FI', r'finsk'), ('IS', r'islandsk'),
        ('IE', r'irsk'), ('GB', r'velk\w* británi|spojen\w* královstv'), ('CH', r'švýcar'), ('SI', r'slovinsk'), ('HR', r'chorvat'), ('RS', r'srbsk|srbsko'),
        ('BA', r'bosn'), ('ME', r'černohor'), ('MK', r'makedon'), ('AL', r'albán'), ('BG', r'bulhar'), ('RO', r'rumun'), ('MD', r'moldav'), ('BY', r'bělorus'),
        ('LT', r'litev|litv'), ('LV', r'lotyš'), ('EE', r'eston'), ('GR', r'řeck'), ('CY', r'kypr'), ('MT', r'maltsk|malta'), ('TR', r'turec|turecko'),
        ('IL', r'izrael'), ('EG', r'egypt'), ('CN', r'čín'), ('JP', r'japon'), ('KR', r'korej'), ('IN', r'indick|indie\b'), ('VN', r'vietnam'), ('MN', r'mongol'),
        ('KZ', r'kazach'), ('UZ', r'uzbek'), ('GE', r'gruz'), ('AM', r'arméns'), ('AZ', r'ázerbájdž'), ('CA', r'kanad'), ('MX', r'mexi'), ('BR', r'brazil'),
        ('AR', r'argentin'), ('CL', r'chilsk|chile'), ('AU', r'austral'), ('NZ', r'nov\w* zéland'), ('ZA', r'jihoafri'), ('MA', r'maroc'), ('TN', r'tunis'),
        ('JO', r'jordán'), ('KW', r'kuvajt'), ('AE', r'spojen\w* arabsk'), ('QA', r'katar'), ('SA', r'saúdsk'), ('ID', r'indonés'), ('SG', r'singap'),
        ('TH', r'thajsk'), ('PH', r'filipín'), ('MY', r'malajs'), ('KG', r'kyrgyz'), ('TJ', r'tádžik'), ('TM', r'turkmen'), ('LB', r'libanon'), ('SY', r'syrsk|sýri'),
        ('IR', r'írán'), ('IQ', r'irác|irák'), ('PK', r'pákistán'), ('CU', r'kubánsk|kuby|kubou'), ('CO', r'kolumbi'), ('VE', r'venezuel'), ('EC', r'ekvádor'),
        ('UY', r'urugua'), ('PY', r'paragua'), ('BO', r'bolív'), ('ET', r'etiop'), ('KE', r'keňs'), ('NG', r'nigéri'), ('GH', r'ghan'), ('AO', r'angol'),
        ('MZ', r'mosambi'), ('ZM', r'zambi'), ('LK', r'srí lank'), ('NP', r'nepál'), ('BD', r'bangladéš'), ('AF', r'afghán'), ('OM', r'omán'), ('LY', r'libyj|libye'),
        ('MC', r'monack|monako'), ('SM', r'san marin'), ('VA', r'svat\w* stolic|vatikán'), ('LI', r'lichtenštejn'), ('KP', r'korejsk\w* lidově'), ('PE', r'perusk')]
c18 = collections.defaultdict(collections.Counter)
c18n = collections.Counter()
for f, r in first_add.items():
    if not f.endswith('.md'): continue
    if f.startswith('sbms/'):
        pass
    elif f.startswith('sb/') and kind_of(r['an']) == 'Sdělení' and 'zahraničních věcí' in titles.get(f, ''):
        pass
    else:
        continue
    y = int(f.split('/')[1])
    if y < 1990: continue
    t = titles.get(f, '').lower()
    t = re.sub(r'česk\w* a slovensk\w*|československ\w*|česk\w* republik\w*', ' ', t)
    hits = [k for k, rx in CTRY if re.search(r'\b(?:' + rx + ')', t)]
    if 'KP' in hits and 'KR' in hits: hits.remove('KR')
    if len(set(hits)) > 3: hits = []  # a title naming many states is a multilateral treaty (EU accessions and the like)
    if 'AE' in hits and 'US' in hits and 'spojen' not in t.replace('spojenými arabskými', ''): hits.remove('US')
    dec = (y // 5) * 5
    if not hits:
        k = 'multi'
        c18['multi'][dec] += 1; c18n['multi'] += 1
    else:
        for k in set(hits):
            c18[k][dec] += 1; c18n[k] += 1
OUT['c18'] = {'rows': [{'k': k, 'n': n, 'by': dict(c18[k])} for k, n in c18n.most_common()],
              'total': sum(1 for f in first_add if f.startswith('sbms/')) }
print('c18', c18n.most_common(30))

# ------------------------------------------------------------------ IV. Towns, regions and numbers
LOC_TOPIC = [('repeal', r'^(,\s*)?(kterou|kterým) se (zrušuj|ruší)|^o zrušení'),
             ('waste', r'odpad|komunáln'), ('dogs', r'psů|psi\b|psa\b'), ('stay', r'pobyt|ubytovac|lázeňsk|rekreační'),
             ('space', r'veřejného prostranství|užívání veřejn'), ('quiet', r'nočn\w* klid|hlučn|klidu'), ('gambling', r'hazard|výherní|loterií'),
             ('alcohol', r'alkohol'), ('proptax', r'koeficient|daně z nemovit'), ('fire', r'požár|požární'), ('school', r'školsk'),
             ('trade', r'podomní|pochůzkov|tržní řád|tržního řádu|prodej\w* mimo|tržišt'), ('nature', r'přírodní|rezervac|památn\w* strom|chráněn'),
             ('police', r'polici'), ('roads', r'sjízdnost|schůdnost|místních komunikac|parkov|stání'), ('order', r'čistot|veřejného pořádku|veřejný pořádek|veřejné zeleně|zeleň|pohyb osob|žebr|kouř'),
             ('fees', r'poplatk')]
c19 = collections.defaultdict(collections.Counter)
c19reg = collections.defaultdict(collections.Counter)
c19n = collections.Counter()
loc_first = {f: r for f, r in first_add.items() if f.startswith('local/') and f.endswith('.md')}
for f, r in loc_first.items():
    line = r['body'].split('\n')[0] if r['body'] else ''
    t = r['subj']
    m = re.search(r'č\. [\w/.-]+:\s*(.*)$', t)
    t = (m.group(1) if m else t).lower()
    # subject of an amendment names the amended ordinance in brackets: use its title from the first body line
    line = (re.search(r':\s*(.*)$', r['body'].split('\n')[0]).group(1) if re.search(r':\s*(.*)$', r['body'].split('\n')[0] if r['body'] else '') else t).lower()
    t = re.sub(r'^(obecně závazná vyhláška|nařízení|ozv)\b.*?(?=\b(o|kterou|kterým|k)\b)', '', line).strip()
    k = next((k for k, rx in LOC_TOPIC if re.search(rx, t)), 'other')
    y = int((tr(r, 'In-force') or '2020')[:4])
    c19[k][min(max(y, 2019), 2026)] += 1
    c19n[k] += 1
    c19reg[f.split('/')[1]][k] += 1
OUT['c19'] = {'rows': [{'k': k, 'n': n, 'by': dict(c19[k])} for k, n in c19n.most_common()], 'n': len(loc_first),
              'regions': {g: dict(c) for g, c in c19reg.items()}}
print('c19', c19n.most_common(), len(loc_first))

# c20: numbers the law sets: the minimum wage and the default-interest rate
mw = [r for r in rd('data/tables/minimum-wage.csv') if r['kind'] == 'minimum wage' and r['scope'] in ('general', 'general (monthly wage)') and r['monthly']]
wage = {}
for r in mw:
    wage.setdefault(r['valid_from'], [r['valid_from'], r['valid_to'], float(r['monthly']), r['currency'], r['act']])
OUT['c20'] = {'wage': [wage[k] for k in sorted(wage)],
              'interest': [[r['period_from'], r['period_to'], float(r['default_interest_percent']), r['reference_rate'], r['reference_rate_percent'], r['act']]
                           for r in rd('data/tables/default-interest.csv') if r['default_interest_percent']]}
print('c20', OUT['c20']['wage'][:3], OUT['c20']['wage'][-3:], len(OUT['c20']['interest']), OUT['c20']['interest'][-2:])

# ------------------------------------------------------------------ profile
PROFILE.update({
    'commits': len(C), 'head': os.environ.get('HEAD_SHA', ''), 'built': date.today().isoformat(),
    'sb_consolidated_now': sum(1 for f in sb_first if f in tree_now and f not in promulgated_only),
    'law_commits': len(law_commits),
    'bills': sum(1 for b in bills if is_bill(b)), 'bills_law': sum(1 for b in bills if is_bill(b) and became_law(b)), 'prints': len(bills),
    'votes': len(votes), 'mp_votes': 16690400,
    'ul': len(ul_first), 'sbms': sum(1 for f in first_add if f.startswith('sbms/') and f.endswith('.md')),
    'local': len(loc_first), 'eu': sum(1 for f in first_add if f.startswith('eu/') and f.endswith('.md')),
    'last_in_force': max(tr(r, 'In-force') for r, _ in law_commits),
})
json.dump({'charts': OUT, 'profile': PROFILE}, open(os.path.join(B, 'data.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('profile', PROFILE)
