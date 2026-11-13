"""Czech law on a given day, read from this repository by the In-force: trailer. Standard library only.

    python tools/czlaw.py on 2013-03-07 sb/1993/1.md     the Constitution as in force on 7 March 2013
    python tools/czlaw.py 2013-03-07 sb/1993/1.md        the same ("on" may be left out)
    python tools/czlaw.py on 2013-03-07 sb/1993          every act of 1993 in force that day: path, blob, last change
    python tools/czlaw.py log sb/1993/1.md               every change: in-force day, act, subject
    python tools/czlaw.py version 2013-03-07 sb/1993/1.md   the commit in force that day, its act and In-force day
    python tools/czlaw.py blame sb/1993/1.md             each line: commit, In-force day, the act that wrote it

Changes the history credits to `e-Sbírka` (no consolidation link names their act) are shown, in `log` and `blame`,
with the act data/credits/credits.csv resolves them to from the amending acts' own amendment points, labelled
"resolved by data/credits" with its confidence; ambiguous or unresolved ones stay `e-Sbírka`. The commits themselves
are unchanged (git log and git blame still name e-Sbírka).

The commit in force on a day is the last commit on `main` (or, after main's last day, on `future`) whose In-force:
trailer is on or before that day. Publisher corrections appended later ("Kind: correction", with
Corrects: <act> <from>..<to>) are left out of that order; for an act they touch, the text in force on a day comes
from the act's own history: the commit with the greatest In-force day on or before the day (a correction only within
the days it names), a later commit winning a tie. Commit dates are noon Prague time, and git cannot store days before 1970, so this
tool reads the trailer rather than the commit date: no time zone or `--before` subtleties.
"""
import bisect
import csv
import os
import re
import subprocess
import sys

PUBLISHER = "e-Sbírka"
CREDITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "credits", "credits.csv")
RESOLVED = ("high", "medium", "low")
UNIT_KIND = {"§": "par", "čl.": "cl", "článek": "cl", "příloha": "priloha", "pozn.": "ppc", "část": "cast",
             "hlava": "hlava", "díl": "dil", "oddíl": "oddil", "pododdíl": "pododdil", "kapitola": "kapitola"}


def roman(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    if not s or any(c not in vals for c in s):
        return None
    return sum(-vals[c] if i + 1 < len(s) and vals[s[i + 1]] > vals[c] else vals[c] for i, c in enumerate(s))


def unit_key(label):
    """A provision label ('§ 3 odst. 2', 'čl. II', 'Čl. 7', '§ 16 *(účinnost od ...)*') as (kind, number, odstavec)."""
    s = re.sub(r"\s*\*\(účinnost od [^)]*\)\*", "", label.strip().lstrip("„").strip())
    m = re.match(r"^(§|čl\.|článek|příloha|pozn\.|část|hlava|díl|oddíl|pododdíl|kapitola)\s*([0-9IVXLC]+[A-Za-z]{0,2}|\*+)"
                 r"\.?(?:\s+([a-z]))?(?::\d+)?\.?(?:\s+odst\.\s*(\d+[a-z]?)(?::\d+)?)?$", s, re.I)
    if not m:
        return ("other", label.strip(), None)
    kind = UNIT_KIND[m.group(1).lower()]
    n = m.group(2) + (m.group(3) or "")
    if re.fullmatch(r"[IVXLC]+", n) and kind in ("cl", "cast", "hlava", "dil", "oddil"):
        n = str(roman(n))
    elif re.fullmatch(r"\d+[a-zA-Z]{0,2}", n):
        d = re.match(r"\d+", n).group(0)
        n = str(int(d)) + n[len(d):].lower()
    return (kind, n, m.group(4))


def load_credits():
    """{(commit, path): [(provision key, acts, confidence)]} from data/credits/credits.csv, if present."""
    out = {}
    if not os.path.exists(CREDITS):
        return out
    with open(CREDITS, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            acts = [a.strip() for a in r["act"].split(" | ") if a.strip()] if r["confidence"] in RESOLVED else []
            out.setdefault((r["commit"], r["path"]), []).append((unit_key(r["provision"]), acts, r["confidence"]))
    return out


def resolved_name(rows):
    """The author column for a publisher commit on one file, from its credits rows; None when nothing is resolved."""
    acts, conf, done = [], [], 0
    order = {"high": 0, "medium": 1, "low": 2}
    for _, a, c in rows:
        if a:
            done += 1
            conf.append(c)
            acts += [x for x in a if x not in acts]
    if not acts:
        return None
    worst = max(conf, key=lambda c: order[c])
    part = "" if done == len(rows) else f" for {done} of {len(rows)} provisions; the rest {PUBLISHER}"
    return f"{'; '.join(acts)} (resolved by data/credits{part}, {worst})"


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def timeline(branch):
    """The law commits' In-force days in order, leaving out appended corrections (returned as {path: [...]})."""
    out = git("log", "--first-parent", "--reverse", "--format=%H\x1f%(trailers:key=In-force,valueonly,separator=)"
              "\x1f%(trailers:key=Kind,valueonly,separator=)\x1f%(trailers:key=Corrects,valueonly,separator=)", branch)
    days, shas, corr, late = [], [], {}, []
    for i, line in enumerate(out.splitlines()):
        sha, day, kind, corrects = (line.split("\x1f") + ["", "", ""])[:4]
        day = day.strip()
        if kind.strip().lower() == "correction":
            act, _, rng = corrects.strip().partition(" ")
            fr, _, to = rng.partition("..")
            corr.setdefault(act + ".md", []).append((fr, to or None, i, sha))
        elif day and days and day < days[-1]:
            # Appended later with an earlier In-force day (history added after the fact): read per path, like a
            # correction that runs on, not in the day order.
            late.append((day, i, sha))
        elif day:
            days.append(day)
            shas.append(sha)
        # A commit without In-force (Kind: record, Promulgated:) is not law in force: left out.
    for k in range(0, len(late), 400):
        chunk = late[k:k + 400]
        byname = {s: (d, i) for d, i, s in chunk}
        cur = None
        for row in git("show", "--no-renames", "--name-only", "--format=@@%H", *[s for _, _, s in chunk]).splitlines():
            if row.startswith("@@"):
                cur = row[2:]
            elif row.strip() and cur in byname:
                d, i = byname[cur]
                corr.setdefault(row.strip(), []).append((d, None, i, cur))
    return days, shas, corr


def corrected_commit(day, path, days, shas, corr):
    """For an act with appended corrections (Kind: correction, Corrects: <act> <from>..<to>): of the commits touching
    it, the one with the greatest In-force day on or before `day` (a correction only within the days it names), a
    later commit winning a tie."""
    dayof = dict(zip(shas, days))
    order = {s: i for i, s in enumerate(git("rev-list", "--first-parent", "--reverse", "main").split())}
    cands = [(dayof[s], order[s], s, dayof[s]) for s in git("log", "--first-parent", "--format=%H", "main", "--", path).split()
             if s in dayof and dayof[s] <= day]
    cands += [(f, o, s, f) for f, t, o, s in corr.get(path, []) if f <= day and (t is None or day <= t)]
    if not cands:
        return None, None
    _, _, sha, inforce = max(cands)
    return sha, inforce


def commit_on(day, path=""):
    days, shas, corr = timeline("main")
    has_future = subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/heads/future"], capture_output=True).returncode == 0
    if days and day > days[-1] and has_future:
        days, shas, _ = timeline("future")
    elif path.endswith(".md") and path in corr:
        return corrected_commit(day, path, days, shas, corr)
    i = bisect.bisect_right(days, day) - 1
    if i < 0:
        return None, None
    return shas[i], days[i]


def blame(path):
    """Each line of the file on main: commit, In-force day, and the act that wrote it (git blame's author, or for a
    line by e-Sbírka the act data/credits resolves its provision to)."""
    out = git("blame", "--line-porcelain", "main", "--", path)
    lines, meta, sha = [], {}, None
    for l in out.splitlines():
        if re.match(r"^[0-9a-f]{40} ", l):
            sha = l.split()[0]
            meta.setdefault(sha, {})
        elif l.startswith("author "):
            meta[sha]["author"] = l[7:]
        elif l.startswith("\t"):
            lines.append((sha, l[1:]))
    shas = sorted(meta)
    days = {}
    for i in range(0, len(shas), 500):
        for row in git("show", "-s", "--format=%H\t%(trailers:key=In-force,valueonly,separator=)", *shas[i:i + 500]).splitlines():
            if "\t" in row:
                s, d = row.split("\t", 1)
                days[s] = d.strip()
    credits = load_credits()
    prov, para = None, None
    sys.stdout.reconfigure(encoding="utf-8")
    for sha, text in lines:
        if text.startswith("### "):
            prov, para = text[4:].strip(), None
        elif text.startswith("## "):
            prov, para = None, None
        else:
            m = re.match(r"^\((\d+[a-z]?)\) ", text)
            if m and prov:
                para = m.group(1)
        author = meta[sha].get("author", "")
        if author == PUBLISHER and credits.get((sha, path)):
            rows = credits[(sha, path)]
            key = unit_key(prov + (f" odst. {para}" if para else "")) if prov else None
            hit = [r for r in rows if key and r[0] == key] or [r for r in rows if key and r[0][:2] == key[:2]]
            if len({tuple(r[1]) for r in hit}) > 1:
                hit = []
            if not hit:
                acts = {tuple(r[1]) for r in rows}
                hit = rows if len(acts) == 1 and rows[0][1] else []
            name = resolved_name(hit[:1]) if hit else None
            if name:
                author = name
        print(f"{sha[:10]} {days.get(sha, ''):10} {author}\t{text}")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == "log" and len(argv) == 2:
        out = git("log", "--format=%H\t%(trailers:key=In-force,valueonly,separator=)\t%an\t%s", "main", "--", argv[1])
        credits = load_credits()
        lines = []
        for line in out.splitlines(keepends=True):
            sha, rest = line.split("\t", 1)
            day, author, subject = (rest.split("\t", 2) + ["", ""])[:3]
            if author == PUBLISHER and credits:
                name = resolved_name(credits.get((sha, argv[1].replace("\\", "/")), []))
                if name:
                    rest = f"{day}\t{name}\t{subject}"
            lines.append((day.strip(), rest))
        # In-force order, newest first (history appended later with earlier days sorts into place; a later commit
        # comes first on the same day; records without In-force last).
        lines.sort(key=lambda x: x[0], reverse=True)
        print("".join(r for _, r in lines), end="")
        return
    if cmd == "blame" and len(argv) == 2:
        blame(argv[1].replace("\\", "/"))
        return
    if cmd in ("on", "version"):
        argv = argv[1:]
    if len(argv) != 2 or len(argv[0]) != 10:
        sys.exit(__doc__)
    day, path = argv
    path = path.rstrip("/")
    sha, inforce = commit_on(day, path)
    if not sha:
        sys.exit(f"nothing in force on {day}")
    if cmd == "version":
        print(f"{sha} In-force {inforce} {git('log', '-1', '--format=%an', sha).strip()}")
        return
    kind = git("cat-file", "-t", f"{sha}:{path}").strip() if subprocess.run(
        ["git", "cat-file", "-e", f"{sha}:{path}"], capture_output=True).returncode == 0 else ""
    if kind == "blob":
        sys.stdout.reconfigure(encoding="utf-8")
        print(git("show", f"{sha}:{path}"), end="")
    elif kind == "tree":
        days, shas, corr = timeline("main")
        rows = {}
        for line in git("ls-tree", "-r", sha, "--", path).splitlines():
            meta, _, name = line.partition("\t")
            rows[name] = meta.split()[2][:12]
        if day <= (days[-1] if days else ""):
            for p in corr:
                if p.startswith(path + "/"):
                    csha, _ = corrected_commit(day, p, days, shas, corr)
                    blob = subprocess.run(["git", "rev-parse", "-q", "--verify", f"{csha}:{p}"], capture_output=True,
                                          text=True).stdout.strip() if csha else ""
                    if blob:
                        rows[p] = blob[:12]
                    else:
                        rows.pop(p, None)
        for name in sorted(rows):
            print(f"{name}\t{rows[name]}")
    else:
        sys.exit(f"{path} is not in force on {day} (commit {sha[:10]}, In-force {inforce})")


if __name__ == "__main__":
    main(sys.argv[1:])
