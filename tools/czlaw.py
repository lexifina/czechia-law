"""Czech law on a given day, read from this repository by the In-force: trailer. Standard library only.

    python tools/czlaw.py on 2013-03-07 sb/1993/1.md     the Constitution as in force on 7 March 2013
    python tools/czlaw.py 2013-03-07 sb/1993/1.md        the same ("on" may be left out)
    python tools/czlaw.py on 2013-03-07 sb/1993          every act of 1993 in force that day: path, blob, last change
    python tools/czlaw.py log sb/1993/1.md               every change: in-force day, act, subject
    python tools/czlaw.py version 2013-03-07 sb/1993/1.md   the commit in force that day, its act and In-force day

The commit in force on a day is the last commit on `main` (or, after main's last day, on `future`) whose In-force:
trailer is on or before that day. Commit dates are noon Prague time, and git cannot store days before 1970, so this
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
    out = git("log", "--first-parent", "--reverse", "--format=%H\x1f%(trailers:key=In-force,valueonly,separator=)", branch)
    days, shas = [], []
    for line in out.splitlines():
        sha, _, day = line.partition("\x1f")
        if day.strip():
            days.append(day.strip())
            shas.append(sha)
    return days, shas


def commit_on(day):
    days, shas = timeline("main")
    has_future = subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/heads/future"], capture_output=True).returncode == 0
    if days and day > days[-1] and has_future:
        days, shas = timeline("future")
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
    sha, inforce = commit_on(day)
    if not sha:
        sys.exit(f"nothing in force on {day}")
    path = path.rstrip("/")
    if cmd == "version":
        print(f"{sha} In-force {inforce} {git('log', '-1', '--format=%an', sha).strip()}")
        return
    kind = git("cat-file", "-t", f"{sha}:{path}").strip() if subprocess.run(
        ["git", "cat-file", "-e", f"{sha}:{path}"], capture_output=True).returncode == 0 else ""
    if kind == "blob":
        sys.stdout.reconfigure(encoding="utf-8")
        print(git("show", f"{sha}:{path}"), end="")
    elif kind == "tree":
        for line in git("ls-tree", "-r", sha, "--", path).splitlines():
            meta, _, name = line.partition("\t")
            print(f"{name}\t{meta.split()[2][:12]}")
    else:
        sys.exit(f"{path} is not in force on {day} (commit {sha[:10]}, In-force {inforce})")


if __name__ == "__main__":
    main(sys.argv[1:])
