"""Daily e-Sbírka check for czechia-law (scheduled task "czechia-law e-Sbirka daily append" on this laptop: hourly from
05:30 to 13:30 UK time, so a failed or early attempt is retried the same day).

    python -X utf8 daily.py [--force] [--no-publish]

Each attempt that reads the source is one check in the trail (checktrail.py), published by a `Kind: check` commit:
1. HEAD the six datasets the build reads from e-Sbírka's open data; download those whose Last-Modified or
   Content-Length changed since the last run (state/daily.json) into data/raw (to .part, size checked, then renamed).
   If the source has not refreshed yet (its newest Last-Modified day is the one already appended), the check is
   `not-refreshed`; the trail is published only on the last attempt of the day.
2. ingest_gz.py into data/<day>; census.py lists new acts e-Sbírka publishes as promulgated only (published as enacted)
   and every act in scope the repository does not hold, with its reason; append.py plan (verifies the candidate),
   cz_publish.py, then append.py verify on origin/main; the census again on what was published.
3. Flags: mass-change (then audit.py reads a sample of the corrections again from e-Sbírka's portal), flip-flop,
   census-drop, unexplained-gap, source-lag.
4. The record goes to state/checks-pending.jsonl; checktrail's commit appends it to data/checks/ and rewrites the pages.
Every step is resumable: downloads by size, ingest by done markers, a published batch is not planned again.
"""
import datetime as dt
import email.utils
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

LANE = Path(__file__).resolve().parent
ROOT = LANE.parent.parent
RAW = LANE / "data" / "raw"
STATE = LANE / "state" / "daily.json"
PENDING = LANE / "state" / "checks-pending.jsonl"
LOG = LANE / "logs" / "daily.log"
LOCK = LANE / "state" / "daily.lock"
WORK = LANE / "work"
# 2026-11-22: e-Sbírka moved to .gov.cz (robots.txt and llms.txt of e-sbirka.gov.cz name this host for bulk data); the
# old opendata.eselpoint.cz still answered but failed its certificate check on 2026-11-15.
BASE = "https://opendata.eselpoint.gov.cz/datove-sady-esbirka/"
UA = "lexifina-law (+https://lexifina.com)"
FILES = ["001PravniAktZneni.json.gz", "002PravniAkt.json.gz", "003PravniAktZneniFragment.json.gz",
         "004PravniAktFragment.json.gz", "006PravniAktMetadata.json.gz", "007PravniAktKonsolidacniVazba.json.gz"]
PY = sys.executable
CORPUS = "czechia/national/acts"
LAST_ATTEMPT_HOUR = 13          # UTC: the task's last attempt of the day publishes the trail even with nothing appended
MASS = (200, 0.01)              # a check changing more acts than max(200, 1 %) is flagged and audited
TRAIL_ALLOW = ["data/checks/", "data/freshness.json", "monitoring/", "WATCHING", "FRESHNESS"]

sys.path.insert(0, str(LANE))
sys.path.insert(1, str(LANE.parent))   # in the repository: tools/checktrail.py beside tools/build/
import checktrail as T  # noqa: E402
import census as CENSUS  # noqa: E402


def log(m):
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {m}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def runner() -> str:
    h = hashlib.sha256()
    for n in ("daily.py", "append.py", "census.py", "checktrail.py", "ingest_gz.py", "audit.py"):
        h.update((LANE / n).read_bytes())
    return f"czechia-law daily.py ({h.hexdigest()[:10]})"


def head(c, name):
    req = urllib.request.Request(BASE + name, method="HEAD", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        meta = {"last_modified": r.headers["Last-Modified"], "length": int(r.headers["Content-Length"])}
        c.request("HEAD", BASE + name, r.status, last_modified=meta["last_modified"], bytes=meta["length"],
                  etag=(r.headers.get("ETag") or "").strip('"') or None)
    return meta


def download(c, name, meta):
    dst, part = RAW / name, RAW / (name + ".part")
    req = urllib.request.Request(BASE + name, headers={"User-Agent": UA})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=300) as r, open(part, "wb") as f:
        status = r.status
        for b in iter(lambda: r.read(1 << 22), b""):
            f.write(b)
            h.update(b)
    if part.stat().st_size != meta["length"]:
        raise RuntimeError(f"{name}: {part.stat().st_size} bytes, expected {meta['length']}")
    part.replace(dst)
    c.request("GET", BASE + name, status, last_modified=meta["last_modified"], bytes=meta["length"], sha256=h.hexdigest())
    time.sleep(1)


def run(args, logfile):
    with open(logfile, "a", encoding="utf-8") as out:
        r = subprocess.run([PY, "-X", "utf8", *args], stdout=out, stderr=subprocess.STDOUT, cwd=LANE)
    return r.returncode


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=WORK, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def trail_records() -> list:
    """The records already on origin/main (data/checks/*.jsonl)."""
    out = []
    for p in git("ls-tree", "--name-only", "origin/main", "data/checks/").split():
        if p.endswith(".jsonl"):
            out += [json.loads(l) for l in git("show", f"origin/main:{p}").splitlines() if l.strip()]
    return sorted(out, key=lambda r: r["started"])


def publish_trail(no_publish=False) -> bool:
    """One `Kind: check` commit with every pending record, the month files, latest.json, freshness.json and pages."""
    pending = T.read_pending(PENDING)
    if not pending:
        return True
    git("fetch", "-q", "origin")
    sources = json.loads((LANE / "trail" / "sources.json").read_text(encoding="utf-8"))
    have = {r["check_id"] for r in trail_records()}
    pending = [r for r in pending if r["check_id"] not in have]
    if not pending:
        PENDING.unlink(missing_ok=True)
        return True
    now = T.utcnow()
    acts = next((r["census"].get("repo") for r in reversed(pending) if r.get("census")), None)
    if acts is None:
        acts = next((r["census"].get("repo") for r in reversed(trail_records()) if r.get("census")), 0)
    files = T.build_files(trail_records(), pending, sources["sources"], acts, now)
    files["data/checks/sources.json"] = json.dumps(sources, ensure_ascii=False, indent=1) + "\n"
    batch = LANE / "trail" / "batches" / now.replace(":", "").replace("-", "")
    batch.mkdir(parents=True, exist_ok=True)
    commit = {"author": "Lexifina <czechia-law@lexifina.com>", "date": now.replace("Z", "+00:00"),
              "message": T.commit_message(pending, sources["sources"]), "files": files}
    (batch / "commits.jsonl").write_text(json.dumps(commit, ensure_ascii=False) + "\n", encoding="utf-8")
    args = [str(ROOT / "tools" / "cz_publish.py"), "--lane", "tooling"]
    for p in TRAIL_ALLOW:
        args += ["--allow", p]
    args.append(str(batch))
    if no_publish:
        args.insert(1, "--dry-run")
    if run(args, LANE / "logs" / "trail.log"):
        log(f"trail publish failed; see {LANE / 'logs' / 'trail.log'}")
        return False
    if not no_publish:
        PENDING.unlink(missing_ok=True)
        log(f"trail published: {len(pending)} check(s)")
    return True


def flags(c, plan, cen, prev_rec, snap, today):
    r = c.r
    changed = set(r["published"]["changed"]) | set(r["published"]["removed"]) | set(r["published"]["added"])
    if len(changed) > max(MASS[0], MASS[1] * max(cen["repo"], 1)):
        c.flag("mass-change", f"{len(changed)} acts in one check")
    ff = T.flip_flops(trail_records() + T.read_pending(PENDING), "e-sbirka", r)
    if ff:
        c.flag("flip-flop", "e-Sbírka's data alternates for: " + ", ".join(ff[:20]))
    if prev_rec and prev_rec.get("census", {}).get("source_in_scope", 0) > cen["source_in_scope"]:
        c.flag("census-drop", f"{prev_rec['census']['source_in_scope']} -> {cen['source_in_scope']} acts in scope")
    if cen["unexplained"]:
        c.flag("unexplained-gap", f"{cen['unexplained']} acts")
    if (dt.date.fromisoformat(today) - dt.date.fromisoformat(snap)).days > 2:
        c.flag("source-lag", f"newest data of {snap}")


def check(c, force) -> int:
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    files = state.get("files", {})
    metas = {n: head(c, n) for n in FILES}
    changed = [n for n in FILES if files.get(n) != metas[n] or not (RAW / n).exists()]
    for n in changed:
        log(f"download {n} {metas[n]}")
        download(c, n, metas[n])
        files[n] = metas[n]
    state["files"] = files
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    prague = ZoneInfo("Europe/Prague")
    snap = max(email.utils.parsedate_to_datetime(m["last_modified"]).astimezone(prague).date() for m in metas.values()).isoformat()
    c.r["snapshot"] = snap
    last = state.get("snapshot", "")
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    if snap <= last and not force:
        log(f"no new snapshot (data {snap}, appended {last})")
        c.done("not-refreshed")
        if (dt.date.fromisoformat(today) - dt.date.fromisoformat(snap)).days > 2:
            c.flag("source-lag", f"newest data of {snap}")
        return 0
    data = LANE / "data" / snap
    for old in (LANE / "data").iterdir():
        if old.is_dir() and old.name not in ("raw", snap) and old.name[:2] == "20":
            shutil.rmtree(old, ignore_errors=True)
    lf = LANE / "logs" / f"daily-{snap}.log"
    if run(["ingest_gz.py", "--raw", str(RAW), "--data", str(data), "--workers", "12"], lf):
        raise RuntimeError("ingest failed")
    git("fetch", "-q", "origin")
    batch = LANE / "batches" / snap
    if batch.exists() and not any(batch.glob("published-*.jsonl")):
        shutil.rmtree(batch)
    prev = last if last and last < snap else state.get("prev_snapshot", last or "2026-11-13")
    if not batch.exists():
        batch.mkdir(parents=True)
        pre = CENSUS.census(data, WORK, "origin/main", snap)
        (batch / "promulgated.json").write_text(json.dumps(pre["promulgated"]), encoding="utf-8")
        if run(["append.py", "plan", "--data", str(data), "--repo", str(WORK), "--ref", "origin/main",
                "--snapshot", snap, "--prev", prev, "--out", str(batch), "--workers", "12",
                "--promulgated", str(batch / "promulgated.json"), "--check-id", c.r["check_id"]], lf):
            raise RuntimeError("plan or candidate check failed, nothing published")
        plan = json.loads((batch / "plan.json").read_text(encoding="utf-8"))
        if (batch / "commits.jsonl").exists():
            head_before = git("rev-parse", "origin/main").strip()
            if run([str(ROOT / "tools" / "cz_publish.py"), "--lane", "tooling", "--allow", "sb/", "--allow", "tools/build/", str(batch)], lf):
                raise RuntimeError("publish failed")
            git("fetch", "-q", "origin")
            tip = git("rev-parse", "origin/main").strip()
            n = int(git("rev-list", "--count", f"{head_before}..{tip}").strip())
            c.r["commits"] = {"from": head_before, "to": tip, "count": n}
        log(f"{snap}: {plan['law_commits']} law commits ({plan['versions_appended']} versions, {len(plan['new_acts'])} new acts, "
            f"{len(plan['ends'])} ends), {plan['correction_commits']} corrections in {len(plan['corrected_acts'])} acts")
    plan = json.loads((batch / "plan.json").read_text(encoding="utf-8"))
    git("fetch", "-q", "origin")
    if run(["append.py", "verify", "--repo", str(WORK), "--ref", "origin/main", "--snapshot", snap,
            "--expected", str(batch / "expected.json.gz"), "--record", str(batch / "verify-published.json")], lf):
        c.r["verify"] = json.loads((batch / "verify-published.json").read_text(encoding="utf-8"))
        raise RuntimeError("verify of origin/main failed")
    c.r["verify"] = {k: v for k, v in json.loads((batch / "verify-published.json").read_text(encoding="utf-8")).items()
                     if k in ("versions_checked", "versions_differ", "versions_without_file", "ends_checked", "ends_wrong",
                              "fidelity_mismatch", "ok", "sha")}
    # What was seen and what was published.
    cen = CENSUS.census(data, WORK, "origin/main", snap)
    det = plan.get("corrections_detail") or []
    kinds = {}
    for act, kind, *_ in det:
        kinds.setdefault(act, set()).add(kind)
    added = sorted(set(plan["new_acts"]) | set(plan.get("promulgated") or []), key=CENSUS.act_key)   # new acts only
    removed = sorted(set(plan["ends"]) | {a for a, k in kinds.items() if "removed" in k and a not in added}, key=CENSUS.act_key)
    chg = sorted((set(plan.get("changed_acts") or []) | {a for a, k in kinds.items() if k & {"differs", "restate", "added"}})
                 - set(added) - set(removed), key=CENSUS.act_key)
    prev_scope = set(state.get("scope", []))
    new_at_source = sorted((set(cen["scope"]) - prev_scope) if prev_scope else [], key=CENSUS.act_key)
    c.r["seen"] = {"added": sorted(set(added) | set(new_at_source), key=CENSUS.act_key), "changed": chg, "removed": removed}
    c.r["published"] = {"added": added, "changed": chg, "removed": removed}
    c.r["census"] = {k: cen[k] for k in ("source_in_scope", "repo", "newest_at_source", "newest_in_repo")}
    c.r["gap"] = [{k: g[k] for k in ("id", "reason", "detail")} for g in cen["gap"]]
    c.r["unexplained"] = cen["unexplained"]
    c.r["titles"] = {g["id"]: g["title"] for g in cen["gap"]}
    if added:
        con = __import__("sqlite3").connect(f"file:{data / 'db' / 'meta.sqlite'}?mode=ro", uri=True)
        for a in added:
            row = con.execute("select title from acts where act=?", (a,)).fetchone()
            if row and row[0]:
                c.r["titles"][a] = " ".join(row[0].split())[:160]
        con.close()
    prev_rec = next((r for r in reversed(trail_records()) if r["source"] == "e-sbirka" and r.get("census")), None)
    flags(c, plan, cen, prev_rec, snap, today)
    if any(f["flag"] == "mass-change" for f in c.r["flags"]):
        out = batch / "audit.json"
        if run(["audit.py", "--batch", str(batch), "--repo", str(WORK), "--sample", "30", "--seed", snap, "--out", str(out)], lf) == 0:
            au = json.loads(out.read_text(encoding="utf-8"))
            c.r["audit"] = {k: au[k] for k in ("corrections", "sampled", "match_new", "match_old", "match_neither", "unread", "method")}
            if au["match_old"] or au["match_neither"]:
                c.flag("mass-change", f"portal disagrees on {au['match_old'] + au['match_neither']} of {au['sampled']} sampled")
    c.done("anomaly" if any(f["flag"] in ("mass-change", "unexplained-gap", "census-drop") for f in c.r["flags"])
           else "changed" if (added or chg or removed) else "no-change")
    state["prev_snapshot"] = last
    state["snapshot"] = snap
    state["scope"] = cen["scope"]
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    log(f"{snap}: published and verified ({c.r['outcome']}; not published {len(c.r['gap'])}, unexplained {c.r['unexplained']})")
    return 0


def main() -> int:
    force = "--force" in sys.argv
    no_publish = "--no-publish" in sys.argv
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)
    prague_today = now.astimezone(ZoneInfo("Europe/Prague")).date().isoformat()
    if state.get("snapshot", "") >= prague_today and not force:
        return 0                        # today's data is already appended: later attempts of the day do nothing
    attempts = state.setdefault("attempts", {})
    attempts = {k: v for k, v in attempts.items() if k >= (now.date() - dt.timedelta(days=7)).isoformat()}
    attempts[now.date().isoformat()] = attempts.get(now.date().isoformat(), 0) + 1
    state["attempts"] = attempts
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    rc = 0
    c = T.Check("e-sbirka", CORPUS, runner(), attempts[now.date().isoformat()])
    try:
        with c:                         # an exception sets outcome `failed` and `error` (public words only)
            try:
                rc = check(c, force)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                c.r["outcome"] = "source-error"
                c.r["error"] = T.public_error(e)
                raise
    except Exception as e:
        log(f"error: {e!r}")
        rc = 1
    T.save_pending(c.r, PENDING)
    log(f"check {c.r['check_id']}: {c.r['outcome']}")
    final = now.hour >= LAST_ATTEMPT_HOUR
    if c.r["outcome"] in ("changed", "no-change", "anomaly") or final or force:
        publish_trail(no_publish)
    return rc


if __name__ == "__main__":
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 12 * 3600:
        log("another run holds the lock")
        sys.exit(0)
    LOCK.write_text(str(time.time()))
    try:
        rc = main()
    except Exception as e:  # recorded in the trail (pending) and logged; the next attempt retries
        log(f"error: {e!r}")
        rc = 1
    finally:
        LOCK.unlink(missing_ok=True)
    sys.exit(rc)
