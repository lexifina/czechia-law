"""Check a built repository against the e-Sbírka store, version by version.

    python -I -X utf8 check_repo.py --data DATA --repo REPO --docs-date 2026-10-28 [--workers 10] [--acts ...] [--record FILE]

1. Every consolidated version of every act (the same versions build.py reads) is rendered again from the store, and its
   git blob id must equal the file's blob in the commit in force on the version's day: on `main` for days up to the
   docs date, on `future` after it. The commit in force on a day is the last commit whose In-force: trailer is on or
   before that day, so versions that changed nothing, and have no commit of their own, are checked too.
2. An act whose last version ends has no file from the next day on, and still has it the day before.
3. Text fidelity, independent of the Markdown layout: the letters and digits of each rendered version, in order,
   must equal those of e-Sbírka's own fragment texts with their HTML tags removed (front matter, the účinnost marks
   and image placeholders that the renderer adds are left out first; HTML comments are dropped on both sides, and
   MathML is linearised on both sides by the renderer's own function, the one step the two sides share). It compares
   the stream of letters and digits, not words, because linearised MathML has no word boundaries of its own.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build as B  # noqa: E402
import render as R  # noqa: E402

ALNUM = re.compile(r"[^\W_]", re.U)
MARK = re.compile(r" \*\(účinnost od \d{4}-\d{2}-\d{2}\)\*")
IMGP = re.compile(r"\[obrázek[^\]\n]*\]")
SUPSUB = re.compile(r"</?su[pb]>|<br>")
ANYTAG = re.compile(r"<[^>]*>", re.S)


def blob_id(text: str) -> str:
    b = text.encode("utf-8")
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def stream_rendered(doc: str) -> str:
    body = doc.split("\n---\n", 1)[1] if doc.startswith("---\n") else doc
    body = body.split("\n", 2)[2] if body.startswith("\n# ") else body   # drop the title line
    body = MARK.sub("", body)
    body = IMGP.sub("", body)
    body = SUPSUB.sub("", body)
    return "".join(ALNUM.findall(R.INVISIBLE.sub("", body)))


def stream_raw(rows, texts) -> str:
    out = []
    for h, fid, path, odl in sorted(rows, key=lambda r: R.hkey(r[0])):
        t = texts.get(fid, ("", None))[1]
        if t:
            t = R.DOWNLEVEL.sub("", R.COMMENT.sub("", t))
            # MathML as the renderer linearises it (the only shared step); everything else: tags out, then entities.
            out.append(SUPSUB.sub("", "".join(R._math(x) if m else html.unescape(ANYTAG.sub(" ", x)) for m, x in R.math_split(t))))
    return "".join(ALNUM.findall(R.INVISIBLE.sub("", " ".join(out))))


def check_act(job: dict) -> dict:
    act, info = job["act"], job["info"]
    vers = B.versions_of(B._S["meta"], act)
    docs = [v[0] for v in vers]
    rows = B.version_rows(docs) if docs else {}
    fids = sorted({r[1] for rs in rows.values() for r in rs if r[1] is not None})
    texts = B.fragment_texts(fids)
    cache: dict = {}
    out = []
    fidelity_bad = []
    for doc, od, do, v in vers:
        order, units = R.render_units(rows.get(doc, []), texts, od, cache)
        text = R.document(info, order, units)
        out.append((od, blob_id(text), v))
        if stream_rendered(text) != stream_raw(rows.get(doc, []), texts):
            fidelity_bad.append(v)
    end = None
    if vers and vers[-1][2] and vers[-1][2] < "2099-12-31":
        end = (dt.date.fromisoformat(vers[-1][2]) + dt.timedelta(days=1)).isoformat()
    return {"act": act, "versions": out, "end": end, "fidelity_bad": fidelity_bad}


class Repo:
    """A branch's law timeline, read by In-force: as tools/czlaw.py reads it. Appended "Kind: correction" commits
    (Corrects: <act> <from>..<to>) are left out of the timeline, and so are law commits appended later with an
    In-force day earlier than one before them (other parts of the record, appended after the build), and commits
    without In-force (documentation, `Kind: record`). For a path that a correction or such an out-of-order commit
    touches, the text in force on a day comes from the path's own history: of the law commits and corrections
    touching it, the one with the greatest In-force day on or before the day (a correction only within the days it
    names), a later commit winning a tie. Every other path reads the last in-order law commit on or before the day."""

    def __init__(self, repo: Path, branch: str):
        self.repo = repo
        rows = subprocess.run(["git", "log", "--first-parent", "--reverse", "--format=%H\x1f%(trailers:key=In-force,valueonly,separator=)\x1f%(trailers:key=Kind,valueonly,separator=)\x1f%(trailers:key=Corrects,valueonly,separator=)", branch],
                              cwd=repo, capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
        self.days, self.shas = [], []
        self.corr: dict = defaultdict(list)     # path -> [(from, until or None, order, sha)]
        self.late: dict = {}                    # sha -> (day, order) of out-of-order law commits
        order, dayof = {}, {}
        for i, r in enumerate(rows):
            sha, day, kind, corrects = (r.split("\x1f") + ["", "", ""])[:4]
            day = day.strip()
            order[sha] = i
            if kind.strip().lower() == "correction":
                act, _, rng = corrects.strip().partition(" ")
                fr, _, to = rng.partition("..")
                self.corr[act + ".md"].append((fr, to or None, i, sha))
                continue
            if day:
                dayof[sha] = day
                if self.days and day < self.days[-1]:
                    self.late[sha] = (day, i)
                    continue
                self.days.append(day)
                self.shas.append(sha)
        self.touch: dict = defaultdict(list)    # per-file path -> [(in-force, order, sha)] of the law commits touching it
        self.perfile = set(self.corr)
        if self.late:
            out = subprocess.run(["git", "log", "--first-parent", "--no-renames", "--format=@@%H", "--name-only", branch],
                                 cwd=repo, capture_output=True, text=True, encoding="utf-8", check=True).stdout
            sha = None
            for line in out.splitlines():
                if line.startswith("@@"):
                    sha = line[2:]
                elif line and sha in self.late:
                    self.perfile.add(line)
        if self.perfile:
            out = subprocess.run(["git", "log", "--first-parent", "--no-renames", "--format=@@%H", "--name-only", branch, "--", *sorted(self.corr)] if not self.late else
                                 ["git", "log", "--first-parent", "--no-renames", "--format=@@%H", "--name-only", branch],
                                 cwd=repo, capture_output=True, text=True, encoding="utf-8", check=True).stdout
            sha = None
            for line in out.splitlines():
                if line.startswith("@@"):
                    sha = line[2:]
                elif line and sha in dayof and line in self.perfile:
                    self.touch[line].append((dayof[sha], order[sha], sha))

    def at(self, day: str):
        i = bisect.bisect_right(self.days, day) - 1
        return self.shas[i] if i >= 0 else None

    def read(self, batch, path: str, day: str):
        """(commit, blob id or None) of `path` in force on `day`."""
        if path not in self.perfile:
            sha = self.at(day)
            return sha, (batch.blob(f"{sha}:{path}") if sha else None)
        cands = [(d, o, s) for d, o, s in self.touch[path] if d <= day]
        cands += [(f, o, s) for f, t, o, s in self.corr.get(path, ()) if f <= day and (t is None or day <= t)]
        if not cands:
            return None, None
        _, _, sha = max(cands)
        return sha, batch.blob(f"{sha}:{path}")


class Batch:
    def __init__(self, repo: Path):
        self.p = subprocess.Popen(["git", "cat-file", "--batch-check"], cwd=repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def blob(self, spec: str):
        self.p.stdin.write(spec.encode("utf-8") + b"\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline().split()
        return None if len(line) < 2 or line[1] == b"missing" else line[0].decode()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--docs-date", required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--acts", default="")
    ap.add_argument("--types", default="")
    ap.add_argument("--record", default="")
    a = ap.parse_args()
    t0 = time.time()
    repo = Path(a.repo)
    jobs, infos = B.load_jobs(Path(a.data), [x for x in a.acts.split(",") if x] or None, [x for x in a.types.split(",") if x] or None)
    main_ = Repo(repo, "main")
    has_future = subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/heads/future"], cwd=repo, capture_output=True).returncode == 0
    fut = Repo(repo, "future") if has_future else None
    batch = Batch(repo)
    n = bad = nofile = ends = endbad = fid_bad = 0
    examples = []
    with ProcessPoolExecutor(a.workers, initializer=B._init, initargs=(a.data,)) as pool:
        for res in pool.map(check_act, jobs, chunksize=4):
            coll, year, num = res["act"].split("/")
            path = f"{coll}/{year}/{num}.md"
            for od, want, v in res["versions"]:
                r = main_ if od <= a.docs_date else fut
                sha, got = r.read(batch, path, od) if r else (None, None)
                n += 1
                if got != want:
                    bad += 1
                    if got is None:
                        nofile += 1
                    if len(examples) < 20:
                        examples.append(f"{v}: {'no file' if got is None else 'differs'} at {sha and sha[:10]}")
            if res["end"]:
                r = main_ if res["end"] <= a.docs_date else fut
                if r:
                    ends += 1
                    after = r.read(batch, path, res["end"])[1]
                    before = r.read(batch, path, (dt.date.fromisoformat(res["end"]) - dt.timedelta(days=1)).isoformat())[1]
                    if after or not before:
                        endbad += 1
                        if len(examples) < 20:
                            examples.append(f"{res['act']}: end {res['end']} not as expected")
            if res["fidelity_bad"]:
                fid_bad += len(res["fidelity_bad"])
                if len(examples) < 20:
                    examples.append(f"fidelity: {res['fidelity_bad'][:2]}")
    result = {"versions_checked": n, "versions_differ": bad, "versions_without_file": nofile, "ends_checked": ends,
              "ends_wrong": endbad, "fidelity_mismatch": fid_bad, "acts": len(jobs), "seconds": round(time.time() - t0),
              "main_commits_with_in_force": len(main_.days), "correction_commits": sum(len(v) for v in main_.corr.values()), "out_of_order_commits": len(main_.late), "future_commits": (len(fut.days) - len(main_.days)) if fut else 0}
    print(json.dumps(result, indent=1))
    for e in examples:
        print("  " + e)
    if a.record:
        p = Path(a.record)
        rec = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        rec["check"] = {k: v for k, v in result.items() if k != "seconds"}
        p.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0 if not (bad or endbad or fid_bad) else 1


if __name__ == "__main__":
    sys.exit(main())
