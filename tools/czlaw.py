"""Czech law on a given day, read from this repository by the In-force: trailer. Standard library only.

    python tools/czlaw.py on 2013-03-07 sb/1993/1.md     the Constitution as in force on 7 March 2013
    python tools/czlaw.py 2013-03-07 sb/1993/1.md        the same ("on" may be left out)
    python tools/czlaw.py on 2013-03-07 sb/1993          every act of 1993 in force that day: path, blob, last change
    python tools/czlaw.py log sb/1993/1.md               every change: in-force day, act, subject
    python tools/czlaw.py version 2013-03-07 sb/1993/1.md   the commit in force that day, its act and In-force day

The commit in force on a day is the last commit on `main` (or, after main's last day, on `future`) whose In-force:
trailer is on or before that day. Publisher corrections appended later ("Kind: correction", with
Corrects: <act> <from>..<to>) are left out of that order; for an act they touch, the text in force on a day comes
from the act's own history: the commit with the greatest In-force day on or before the day (a correction only within
the days it names), a later commit winning a tie. Commit dates are noon Prague time, and git cannot store days before 1970, so this
tool reads the trailer rather than the commit date: no time zone or `--before` subtleties.
"""
import bisect
import subprocess
import sys


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def timeline(branch):
    """The law commits' In-force days in order, leaving out appended corrections (returned as {path: [...]})."""
    out = git("log", "--first-parent", "--reverse", "--format=%H\x1f%(trailers:key=In-force,valueonly,separator=)"
              "\x1f%(trailers:key=Kind,valueonly,separator=)\x1f%(trailers:key=Corrects,valueonly,separator=)", branch)
    days, shas, corr = [], [], {}
    for i, line in enumerate(out.splitlines()):
        sha, day, kind, corrects = (line.split("\x1f") + ["", "", ""])[:4]
        if kind.strip().lower() == "correction":
            act, _, rng = corrects.strip().partition(" ")
            fr, _, to = rng.partition("..")
            corr.setdefault(act + ".md", []).append((fr, to or None, i, sha))
        elif day.strip():
            days.append(day.strip())
            shas.append(sha)
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


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == "log" and len(argv) == 2:
        out = git("log", "--format=%(trailers:key=In-force,valueonly,separator=)\t%an\t%s", "main", "--", argv[1])
        print(out, end="")
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
