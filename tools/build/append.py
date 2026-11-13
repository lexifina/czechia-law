"""Append a newer e-Sbírka snapshot to the published history: what is new, nothing rebuilt or rewritten.

    python -I -X utf8 append.py plan   --data DATA --repo CLONE --ref origin/main --snapshot 2026-11-13 --prev 2026-11-08 --out BATCH
    python -I -X utf8 append.py verify --data DATA --repo CLONE --ref origin/main --snapshot 2026-11-13 --expected BATCH/expected.json.gz

DATA is the SQLite store of the snapshot (tools/build/ingest.py, or ingest_gz.py), CLONE a git clone of czechia-law
that this script may write refs into (never the shared clone). `plan` writes BATCH/commits.jsonl for cz_publish.py,
BATCH/plan.json (counts, held-back acts, tags the constitutional acts would get) and BATCH/expected.json.gz (the blob
id of every version), imports the commits onto refs/heads/candidate of CLONE and verifies them there. `verify` checks a
published ref against expected.json.gz without rendering again.

What is appended, all rendered and credited by tools/build's own code (render.py, build.process_act, build.describe), so
every file is byte for byte what build.py would write from the same data:
  - L is the last In-force day of the law commits touching the acts build.py would write (main's last law day).
  - Corrections, for days up to L: for every act, at every day where its text can change (its versions' first days, its
    end, and the days the published history changes its file), the text the published history has in force (as
    tools/czlaw.py and check_repo.py read it: law commits by In-force, earlier corrections within their Corrects:
    range) must be e-Sbírka's current version for that day. Where it is not, a `Kind: correction` commit by e-Sbírka
    sets the file to the current text (or removes it) from that day (In-force:, Corrected:, Corrects: <act> <from>..<to>,
    Supersedes:, Reason:), closed at the next day the history changes the file again. If an act's file at the tip is
    then not its current text, one more correction restates it, unchanged, from its last day of change. The published
    commits stay as they were.
  - Law, for days after L up to the snapshot day: build.py's commits for those days (first versions of new acts,
    changes, ends with Repeals:), one per (day, act that made the change), same messages, authors and author dates.
Versions in force after the snapshot day are not appended (they belong on a future branch, which only moves forward).
Acts on main that the snapshot no longer consolidates are reported in plan.json and left alone.
Verification is check_repo.py's comparison: check_act renders every version again and its fidelity check compares the
letters and digits with e-Sbírka's fragment texts; every version in force on or before the snapshot day and every end
must read back from the ref with the same git blob id.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import gzip
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
LAW8 = Path(os.environ.get("CZ_ROOT", r"C:\Users\alany\law8\czechia"))
BUILD_DIR = os.environ.get("CZ_BUILD_DIR") or str(HERE if (HERE / "render.py").exists() else HERE / "pub" / "tools" / "build" if (HERE / "pub" / "tools" / "build" / "render.py").exists() else LAW8 / "repo" / "tools" / "build")
sys.path.insert(0, BUILD_DIR)
import build as B  # noqa: E402
import check_repo as C  # noqa: E402
import render as R  # noqa: E402

PRAGUE = ZoneInfo("Europe/Prague")
PUBLISHER = "e-Sbírka <publisher@esbirka.invalid>"
SOURCE = "https://opendata.eselpoint.cz/datove-sady-esbirka/"
BASELINE = "6744361da955327900e0dca50d70e388aafb380b"   # main before the lanes of 2026-11-13: the acts the build wrote
FAR = "9999-12-31"


def git(repo, *a, inp=None, check=True) -> str:
    r = subprocess.run(["git", *a], cwd=repo, capture_output=True, input=inp)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(a[:3])}: {r.stderr.decode('utf-8', 'replace')[-600:]}")
    return r.stdout.decode("utf-8", "replace")


def path_of(act: str) -> str:
    coll, year, num = act.split("/")[:3]
    return f"{coll}/{year}/{num}.md"


def day_before(d: str) -> str:
    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()


def day_after(d: str) -> str:
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()


# ---------------------------------------------------------------- the published history, per file

class History:
    """Each file's history on a ref: law commits (In-force day, order, sha) and corrections (from, to, order, sha).
    The text in force on a day is that of the commit with the greatest (day, order) among the law commits on or
    before the day and the corrections whose range holds it: check_repo.Repo's rule for corrected acts, which for an
    uncorrected act gives the last law commit on or before the day, as Repo.at does when In-force never goes back."""

    FMT = "@@%H\x1f%(trailers:key=In-force,valueonly,separator=)\x1f%(trailers:key=Kind,valueonly,separator=)\x1f%(trailers:key=Corrects,valueonly,separator=)"

    def __init__(self, repo: Path, ref: str, prefix: str = "sb/"):
        self.repo = repo
        out = git(repo, "log", "--first-parent", "--reverse", "--no-renames", f"--format={self.FMT}", "--name-only", ref, "--", prefix)
        self.law = defaultdict(list)
        self.corr = defaultdict(list)
        self.all_days, self.all_shas = [], []
        self.n = 0
        cur = None
        for line in out.splitlines():
            if line.startswith("@@"):
                sha, day, kind, corrects = (line[2:].split("\x1f") + ["", "", ""])[:4]
                day = day.strip()
                cur = None
                if kind.strip().lower() == "correction":
                    act, _, rng = corrects.strip().partition(" ")
                    fr, _, to = rng.partition("..")
                    self.corr[act + ".md"].append((fr, to or None, self.n, sha))
                elif day:
                    cur = (day, self.n, sha)
                    self.all_days.append(day)
                    self.all_shas.append(sha)
                self.n += 1
            elif line and cur:
                self.law[line].append(cur)
        self.cat = C.Batch(repo)
        self.blobs = {}

    def blob(self, sha: str, path: str):
        k = (sha, path)
        if k not in self.blobs:
            self.blobs[k] = self.cat.blob(f"{sha}:{path}")
        return self.blobs[k]

    def read(self, path: str, day: str, extra=()):
        """(blob or None, sha or None, (day, order)) in force on `day`; extra: planned corrections (from, to, order, blob, ...)."""
        best = None
        for d, o, s in self.law.get(path, ()):
            if d <= day and (best is None or (d, o) > best[0]):
                best = ((d, o), s, None)
        for f, t, o, s in self.corr.get(path, ()):
            if f <= day and (t is None or day <= t) and (best is None or (f, o) > best[0]):
                best = ((f, o), s, None)
        for x in extra:
            f, t, o, b = x[:4]
            if f <= day and (t is None or day <= t) and (best is None or (f, o) > best[0]):
                best = ((f, o), None, ("planned", b))
        if best is None:
            return None, None, None
        if best[2]:
            return best[2][1], None, best[0]
        return self.blob(best[1], path), best[1], best[0]

    def days_of(self, path: str):
        out = set()
        for d, _, _ in self.law.get(path, ()):
            out.add(d)
        for f, t, _, _ in self.corr.get(path, ()):
            out.add(f)
            if t:
                out.add(day_after(t))
        return out

    def in_force_commit(self, day: str):
        best = None
        for d, s in zip(self.all_days, self.all_shas):
            if d <= day:
                best = s
        return best


# ---------------------------------------------------------------- workers

def w_init(data: str) -> None:
    B._init(data)


def w_act(args):
    job, law_to, snap = args
    res = C.check_act(job)          # versions [(od, blob id, v)], end, fidelity_bad: check_repo's own rendering
    ods = [od for od, _, _ in res["versions"]]
    if any(law_to < od <= snap for od in ods) or (res["end"] and law_to < res["end"] <= snap):
        pr = B.process_act(job)
        res["events"] = [e for e in pr["events"] if law_to < e["date"] <= snap]
    return res


def w_texts(args):
    job, ods = args
    vers = B.versions_of(B._S["meta"], job["act"])
    docs = [v[0] for v in vers]
    rows = B.version_rows(docs) if docs else {}
    fids = sorted({r[1] for rs in rows.values() for r in rs if r[1] is not None})
    texts = B.fragment_texts(fids)
    cache: dict = {}
    out = {}
    for doc, od, do, v in vers:
        order, units = R.render_units(rows.get(doc, []), texts, od, cache)
        if od in ods:
            out[od] = R.document(job["info"], order, units)     # the last version of a day wins, as in build.py
    return job["act"], out


# ---------------------------------------------------------------- plan

def want_at(res, day):
    """(blob, version) e-Sbírka's current data has in force on `day` (None: no file)."""
    if res["end"] and day >= res["end"]:
        return None, None
    best = (None, None, None)
    for od, b, v in res["versions"]:
        if od <= day:
            best = (od, b, v)
    return best[1], (best[0], best[2]) if best[0] else None


def stamp(snap: str, k: int) -> str:
    t = dt.datetime.fromisoformat(f"{snap}T12:00:00").replace(tzinfo=PRAGUE) + dt.timedelta(seconds=k)
    return t.isoformat()


def corr_message(act, kind, f, t, sup, version, new, prev):
    p = act
    rng = f"{f}..{t or ''}"
    span = f"{f}..{t}" if t else f"{f} on"
    if kind == "restate":
        subject = f"Oprava / Correction: {p} as in force from {f}"
        body = (f"The published text of {p} from {f} is right; the corrections to its earlier days above set the file to "
                f"older texts, and this commit sets it back to the text in force from {f}.")
        reason = ("restates the text in force from this day, unchanged, after the corrections to earlier days of this "
                  "act above, so that its file at the tip is its current text again")
    elif kind == "removed":
        subject = f"Oprava / Correction: {p} not in force from {f}"
        body = (f"e-Sbírka's current data has no consolidated version of {p} in force for {span}, but the published "
                f"history has its file on those days. This commit removes the file for those days; the published commits "
                f"stay as they were.")
        reason = (f"e-Sbírka's open data of {new} has no version of this act in force on this day; its data of {prev} had one")
    elif kind == "added":
        subject = f"Oprava / Correction: {p} as in force from {f}"
        body = (f"The published history has no text of {p} for {span}; e-Sbírka's current data has a consolidated "
                f"version in force on those days. This commit sets the file to that text for those days; the published "
                f"commits stay as they were.")
        reason = f"e-Sbírka's open data of {new} has this act in force on this day; its data of {prev} did not"
    else:
        subject = f"Oprava / Correction: {p} as in force from {f}"
        body = (f"The published text of {p} differs from e-Sbírka's current consolidated text for {span}. This commit "
                f"sets it to that text for those days; the published commits stay as they were.")
        reason = (f"e-Sbírka's open data of {new} publishes a different consolidated text for this act on this day than "
                  f"its data of {prev}")
    tr = ["Kind: correction", f"In-force: {f}", f"Corrected: {f}", f"Corrects: {p} {rng}"]
    if sup:
        tr.append(f"Supersedes: {sup}")
    tr.append(f"Reason: {reason}")
    tr.append(f"Act: {R.ESBIRKA}/eli/cz/{act}")
    if version and kind != "removed":
        tr.append(f"Version: {R.ESBIRKA}/eli/cz/{version}")
    tr.append(f"Source: {SOURCE} (open data of {new})")
    return subject + "\n\n" + body + "\n\n" + "\n".join(tr) + "\n"


def plan(a) -> int:
    t0 = time.time()
    data, repo, out = Path(a.data), Path(a.repo), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    def say(m):
        print(f"{time.strftime('%H:%M:%S')} {m} ({time.time() - t0:.0f}s)", flush=True)

    jobs, infos = B.load_jobs(data, [x for x in a.acts.split(",") if x] or None, None)
    hist = History(repo, a.ref)
    paths = {path_of(j["act"]): j["act"] for j in jobs}
    law_to = max((d for p in paths for d, _, _ in hist.law.get(p, ())), default="0000-00-00")
    if a.law_to:
        law_to = a.law_to
    snap = a.snapshot
    say(f"{len(jobs)} acts; main's last law day for them {law_to}; snapshot {snap}; {hist.n} commits on {a.ref}")
    if law_to >= snap:
        say("nothing to append after the last law day")

    results = {}
    with ProcessPoolExecutor(a.workers, initializer=w_init, initargs=(str(data),)) as pool:
        for i, res in enumerate(pool.map(w_act, [(j, law_to, snap) for j in jobs], chunksize=4)):
            results[res["act"]] = res
            if (i + 1) % 2000 == 0:
                say(f"rendered {i + 1}/{len(jobs)}")
    say(f"rendered {len(results)} acts")

    # Corrections, days up to law_to.
    planned = defaultdict(list)          # act -> [[from, to, order, blob, kind, sup, version_od, version_v]]
    order = hist.n + 1
    held = []
    for j in jobs:
        act = j["act"]
        res = results[act]
        p = path_of(act)
        bps = {od for od, _, _ in res["versions"]} | hist.days_of(p)
        if res["end"]:
            bps.add(res["end"])
        for d in sorted(x for x in bps if x <= law_to):
            got, gsha, _ = hist.read(p, d, planned[act])
            want, ver = want_at(res, d)
            if got != want:
                if planned[act] and planned[act][-1][0] == d:
                    raise SystemExit(f"{act}: correction at {d} does not hold")
                published = hist.read(p, d)[0]
                kind = "removed" if want is None else "added" if published is None else "differs"
                sup = gsha or (None if got is not None else hist.in_force_commit(d))
                if gsha is None and got is not None:      # read from a correction planned here
                    sup = planned[act][-1][5]
                planned[act].append([d, None, order, want, kind, sup, ver[0] if ver else None, ver[1] if ver else None])
                order += 1
        # Close each correction at the next day the file changes again; restate the tip if needed.
        cs = planned[act]
        if cs:
            law_days = sorted(d for d, _, _ in hist.law.get(p, ()))
            for k, c in enumerate(cs):
                nxt = [x[0] for x in cs[k + 1:k + 2]] + [d for d in law_days if d > c[0]][:1]
                c[1] = day_before(min(nxt)) if nxt else None
            if not res.get("events"):
                cur, csha, key = hist.read(p, FAR, cs)
                if cs[-1][1] is not None and cs[-1][3] != cur:
                    lastd = key[0]
                    want, ver = want_at(res, lastd)
                    if want != cur:
                        raise SystemExit(f"{act}: tip reading {cur} is not the current text {want}")
                    cs.append([lastd, None, order, want, "restate" if want is not None else "removed", csha,
                               ver[0] if ver else None, ver[1] if ver else None])
                    order += 1
            # Re-check every breakpoint with the closed ranges.
            for d in sorted(x for x in bps if x <= law_to):
                if hist.read(p, d, cs)[0] != want_at(res, d)[0]:
                    raise SystemExit(f"{act}: planned corrections do not give the current text on {d}")
    # Acts the build wrote that the snapshot no longer consolidates.
    base = set(git(repo, "ls-tree", "-r", "--name-only", BASELINE, "--", "sb/").split())
    tip = set(git(repo, "ls-tree", "-r", "--name-only", a.ref, "--", "sb/").split())
    for p in sorted((base & tip) - set(paths)):
        held.append({"path": p, "why": "on main, but the snapshot has no consolidated version of it (left as it is)"})

    need = defaultdict(set)
    for act, cs in planned.items():
        for c in cs:
            if c[3] is not None:
                need[act].add(c[6])
    texts = {}
    if need:
        jmap = {j["act"]: j for j in jobs}
        with ProcessPoolExecutor(min(a.workers, len(need)), initializer=w_init, initargs=(str(data),)) as pool:
            for act, tx in pool.map(w_texts, [(jmap[x], sorted(ods)) for x, ods in need.items()]):
                texts[act] = tx
    commits = []
    k = 0
    ncorr = defaultdict(int)
    for act in sorted((x for x in planned if planned[x]), key=B.act_key):
        for f, t, _, blob, kind, sup, vod, v in planned[act]:
            k += 1
            text = texts[act][vod] if blob is not None else None
            if text is not None and C.blob_id(text) != blob:
                raise SystemExit(f"{act} {vod}: rendered text does not match its blob")
            commits.append({"author": PUBLISHER, "date": stamp(snap, k),
                            "message": corr_message(act, kind, f, t, sup, v, a.label or snap, a.prev),
                            "files": {path_of(act): text}})
            ncorr[kind] += 1
    say(f"{len(commits)} corrections {dict(ncorr)} in {sum(1 for x in planned.values() if x)} acts")

    # Law commits after law_to: build.py's own grouping, order and messages.
    events = []
    for act, res in results.items():
        for e in res.get("events", []):
            e = dict(e)
            e["act"] = act
            events.append((e["date"], B.cause_key(e["cause"]), B.act_key(act), e))
    events.sort(key=lambda x: (x[0], x[1], x[2]))
    tags = []
    nlaw = 0
    i = 0
    while i < len(events):
        jx = i
        while jx < len(events) and events[jx][0] == events[i][0] and events[jx][1] == events[i][1]:
            jx += 1
        date = events[i][0]
        group = [x[3] for x in events[i:jx]]
        cause = group[0]["cause"]
        subject, body, author = B.describe(date, cause, group, infos)
        files = {}
        for e in sorted(group, key=lambda e: B.act_key(e["act"])):
            files[path_of(e["act"])] = e.get("text")
            info = infos[e["act"]]
            if e["kind"] != "end" and (info.get("podtyp") in B.CONSTITUTIONAL or e["act"] in ("sb/1993/1",) + B.EXTRA_ACTS):
                tags.append(f"{e['act']}/{date}")
        commits.append({"author": f"{author[0]} <{author[1]}>", "date": date, "message": subject + "\n\n" + body, "files": files})
        nlaw += 1
        i = jx
    new_acts = sorted({x[3]["act"] for x in events if x[3]["kind"] == "first"}, key=B.act_key)
    ends = sorted({x[3]["act"] for x in events if x[3]["kind"] == "end"}, key=B.act_key)
    versions = sorted({(x[3]["act"], x[0]) for x in events if x[3]["kind"] != "end"})
    say(f"{nlaw} law commits, {len(versions)} versions, {len(new_acts)} new acts, {len(ends)} ends")

    with open(out / "commits.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for c in commits:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    with gzip.open(out / "expected.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({act: {"versions": r["versions"], "end": r["end"], "fidelity_bad": r["fidelity_bad"]} for act, r in results.items()}, fh)
    summary = {"snapshot": snap, "prev": a.prev, "ref": a.ref, "ref_sha": git(repo, "rev-parse", a.ref).strip(),
               "law_to_before": law_to, "acts": len(jobs), "correction_commits": len(commits) - nlaw,
               "corrections_by_kind": dict(ncorr), "corrected_acts": sorted(x for x in planned if planned[x]),
               "law_commits": nlaw, "law_days": sorted({x[0] for x in events}), "versions_appended": len(versions),
               "new_acts": new_acts, "ends": ends, "tags_not_pushed": tags, "held_back": held,
               "fidelity_mismatch": sum(len(r["fidelity_bad"]) for r in results.values())}
    (out / "plan.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    say(json.dumps({k: v for k, v in summary.items() if k not in ("corrected_acts",)}, ensure_ascii=False)[:2000])
    if not commits:
        (out / "commits.jsonl").unlink()
        say("nothing to append")
        return 0
    # Candidate: the batch on top of the ref, as cz_publish.py builds it, then check_repo's comparison on it.
    sys.path.insert(0, str(LAW8 / "tools"))
    import cz_publish as P
    head = git(repo, "rev-parse", a.ref).strip()
    ctime = int(git(repo, "log", "-1", "--format=%ct", head).strip())
    stream, _ = P.stream(commits, head, ctime, 1)
    stream = stream.replace(b"commit refs/heads/publish\n", b"commit refs/heads/candidate\n")
    r = subprocess.run(["git", "fast-import", "--quiet", "--force"], cwd=repo, input=stream, capture_output=True)
    if r.returncode:
        raise SystemExit("fast-import: " + r.stderr.decode("utf-8", "replace")[-600:])
    touched = set(git(repo, "diff", "--name-only", head, "candidate").split())
    if any(not x.startswith("sb/") for x in touched):
        raise SystemExit(f"candidate touches paths outside sb/: {sorted(touched)[:5]}")
    res = verify_ref(repo, "candidate", results, snap, say)
    summary["verify_candidate"] = res
    (out / "plan.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if res["ok"] else 1


def verify_ref(repo: Path, ref: str, results: dict, snap: str, say) -> dict:
    """check_repo.py's comparison (its Repo reader: In-force order with corrections) for every version in force on or
    before `snap` and every end up to it; where other commits make In-force go backwards on the ref, the same rule per
    file (History)."""
    try:
        r = C.Repo(repo, ref)
        batch = C.Batch(repo)
        read = lambda p, d: r.read(batch, p, d)[1]
        how = "check_repo.Repo"
    except SystemExit as e:
        h = History(repo, ref)
        read = lambda p, d: h.read(p, d)[0]
        how = f"per file (check_repo.Repo: {e})"
    n = bad = nofile = ends = endbad = later = 0
    examples = []
    for act, res in results.items():
        p = path_of(act)
        for od, want, v in res["versions"]:
            if od > snap:
                later += 1
                continue
            n += 1
            got = read(p, od)
            if got != want:
                bad += 1
                nofile += got is None
                if len(examples) < 20:
                    examples.append(f"{v}: {'no file' if got is None else 'differs'}")
        if res["end"] and res["end"] <= snap:
            ends += 1
            if read(p, res["end"]) or not read(p, day_before(res["end"])):
                endbad += 1
                if len(examples) < 20:
                    examples.append(f"{act}: end {res['end']} not as expected")
    fid = sum(len(r["fidelity_bad"]) for r in results.values())
    out = {"ref": ref, "sha": git(repo, "rev-parse", ref).strip(), "reader": how, "acts": len(results),
           "versions_checked": n, "versions_differ": bad, "versions_without_file": nofile, "versions_after_snapshot": later,
           "ends_checked": ends, "ends_wrong": endbad, "fidelity_mismatch": fid, "examples": examples,
           "ok": not (bad or endbad or fid)}
    say("verify " + json.dumps(out, ensure_ascii=False))
    return out


def verify(a) -> int:
    with gzip.open(a.expected, "rt", encoding="utf-8") as fh:
        results = {k: {"versions": [tuple(x) for x in v["versions"]], "end": v["end"], "fidelity_bad": v["fidelity_bad"]} for k, v in json.load(fh).items()}
    if a.acts:
        keep = set(a.acts.split(","))
        results = {k: v for k, v in results.items() if k in keep}
    t0 = time.time()
    res = verify_ref(Path(a.repo), a.ref, results, a.snapshot, lambda m: print(f"{time.strftime('%H:%M:%S')} {m} ({time.time() - t0:.0f}s)", flush=True))
    if a.record:
        Path(a.record).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if res["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan", "verify"])
    ap.add_argument("--data", default="")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--snapshot", required=True, help="the snapshot's day (the datasets' Last-Modified, Prague)")
    ap.add_argument("--label", default="", help="how messages name the snapshot (default: its day)")
    ap.add_argument("--prev", default="", help="the day of the snapshot the history was last checked against")
    ap.add_argument("--law-to", default="", help="override main's last law day")
    ap.add_argument("--out", default="")
    ap.add_argument("--expected", default="")
    ap.add_argument("--record", default="")
    ap.add_argument("--acts", default="")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    if a.cmd == "plan":
        if not (a.data and a.out and a.prev):
            raise SystemExit("plan needs --data, --out and --prev")
        return plan(a)
    return verify(a)


if __name__ == "__main__":
    sys.exit(main())
