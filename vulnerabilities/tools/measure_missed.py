"""Measure what textscan.limits() still misses in Czech: every "do" ("until") followed within 40 characters by a past
date or year (before the pin's date), in the texts at the pin, that the time-limit search does not read. Prints counts by
form and by law/other, and samples.   python -X utf8 measure_missed.py"""
import collections, random, re, subprocess, sys
sys.path.insert(0, "gl/vulnerabilities/scripts")
from ingest import textscan
G = "gl/vulnerabilities/scripts/sources/corpus/czechia-law.git"; PIN = "aa02aa05dc66bdff595c04995523e3955feed005"
TODAY = "2026-11-15"
NOT_LAW = ("navrhy/", "caselaw/", "usneseni-vlady/", "vestnik/", "metodika/", "data/", "tools/")
MON = "ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince"
MONN = "leden|únor|březen|duben|květen|červen|červenec|srpen|září|říjen|listopad|prosinec"
FORMS = [  # (name, regex on the text right after "do "); the year is group y
    ("date: 31. prosince 2020", rf"(?:dne\s+)?\d{{1,2}}\.\s*(?:{MON})\s+(?P<y>\d{{4}})"),
    ("date: 31.12.2020 / 31. 12. 2020", r"(?:dne\s+)?\d{1,2}\.\s?\d{1,2}\.\s?(?P<y>\d{4})"),
    ("year end: konce roku 2020", r"konce\s+roku\s+(?P<y>\d{4})"),
    ("year end with a word between: konce kalendářního roku 2020", r"konce\s+(?:kalendářního|účetního|školního|rozpočtového|hospodářského)\s+roku\s+(?P<y>\d{4})"),
    ("month end: konce června 2020", rf"konce\s+(?:měsíce\s+)?(?:{MON}|{MONN})\s+(?P<y>\d{{4}})"),
    ("month: června 2020", rf"(?:{MON}|{MONN})\s+(?P<y>\d{{4}})"),
    ("year: roku 2020 / 2020", r"(?:roku\s+)?(?P<y>(?:18|19|20)\d{2})(?![\d./])"),
]
FRX = [(n, re.compile(r)) for n, r in FORMS]
DO = re.compile(r"(?i)\b(?:až\s+|nejpozději\s+)?do\s+")
files = [l for l in subprocess.run(["git", "-C", G, "ls-tree", "-r", "--name-only", PIN], capture_output=True)
         .stdout.decode("utf-8").splitlines() if l.endswith(".md")]
cat = subprocess.Popen(["git", "-C", G, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
def read(p):
    cat.stdin.write(f"{PIN}:{p}\n".encode()); cat.stdin.flush()
    h = cat.stdout.readline().split()
    if len(h) < 3: return ""
    d = cat.stdout.read(int(h[2])); cat.stdout.read(1)
    return d.decode("utf-8", "replace")
cnt = collections.Counter(); samples = collections.defaultdict(list); total = 0
for i, p in enumerate(files):
    t = read(p)
    if " do " not in t: continue
    kind = "other" if p.startswith(NOT_LAW) else "law"
    spans = [(m.start(), m.end()) for m in textscan.LIMIT.finditer(t)]
    for d in DO.finditer(t):
        rest = t[d.end():d.end() + 60]
        for name, rx in FRX:
            m = rx.match(rest)
            if m: break
        else:
            continue
        y = int(m.group("y"))
        if y < 1800 or y >= int(TODAY[:4]): continue  # a date in the current year is left out (no day check for years)
        e = d.end() + m.end()
        read_ = any(s <= d.end() and en >= e - 1 for s, en in spans)
        total += 1
        cnt[(read_, kind, name)] += 1
        if not read_ and len(samples[name]) < 3000: samples[name].append((kind, p, t[max(0, d.start() - 60):e + 10].replace("\n", " ")))
    if i % 20000 == 0: print(i, "files", file=sys.stderr)
print("total past-date 'do' phrases:", total)
for (r, kind, f), n in sorted(cnt.items(), key=lambda x: (-x[0][0], x[0][1], -x[1])):
    print(f"{'READ  ' if r else 'MISSED'} {kind:5} {n:7}  {f}")
random.seed(1)
for f, s in samples.items():
    law = [x for x in s if x[0] == "law"]
    print("\n##", f)
    for k, p, c in random.sample(law, min(6, len(law))): print("  ", p, "|", c[-150:])
