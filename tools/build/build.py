"""Write the Sbírka zákonů's in-force history as git, from the SQLite store made by ingest.py.

    python -I -X utf8 build.py --data DATA --repo NEW_DIR --docs-date 2026-10-28 [--workers 10] [--acts sb/1993/1,...]
                               [--types ZAKON,ZAKONUST,...] [--docs DIR] [--profile]

One file per act, `sb/<year>/<number>.md` (render.py describes the layout). For every day a consolidated version of an
act begins (e-Sbírka's `znění-datum-účinnosti-od`), the change is committed under the act that made it, read from
e-Sbírka's consolidation links (007, `znění-fragment-novela` -> the amending act), one commit per amending act per day,
dated noon Prague time that day:
  - an act's first version: authored by the act itself;
  - a changed provision (§, Čl., příloha, heading) is credited to the act whose links target it in the new version
    (or its source in the old one); if the version's links name one act only, that act (Evidence: version link);
    if the provision carried "účinnost od <that day>" in the old version, the act that inserted it (Evidence: delayed
    effect); on the act's own in-force date with no links, the act itself (Evidence: act in-force date);
    otherwise a commit by "e-Sbírka" labelled as such, with Candidate: trailers when several acts are possible;
  - the day after an act's last version ends, the file is removed (Repeals:), authored by the act whose ZRUSPRED link
    repeals it that day, or by "e-Sbírka" if none or several do.
After the last commit of a day, every act changed that day is exactly e-Sbírka's version for that day (check_repo.py).
Versions in force after --docs-date are committed on the `future` branch, which starts at main's head.
Commits for days before 1970 are dated 1970-01-01T00:00:01Z onwards, one second apart; In-force: holds the real day.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
import render as R  # noqa: E402

PUBLISHER = "~publisher"
PUBLISHER_AUTHOR = ("e-Sbírka", "publisher@esbirka.invalid")
COMMITTER = "Lexifina <czechia-law@lexifina.com>"
EXTRA_ACTS = ("sb/1993/2",)   # Listina základních práv a svobod: an usnesení (DALSIAKT), part of the constitutional order
CONSTITUTIONAL = ("ZAKONUST", "DEKRETUST")
LIMIT = "2100-01-01"          # git cannot read ISO dates from 2100; e-Sbírka uses 3000-01-xx as a placeholder


# ---------------------------------------------------------------- dates

def last_sunday(y: int, m: int) -> dt.date:
    d = dt.date(y, m, 30 if m in (4, 6, 9, 11) else 31)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def summer(day: dt.date) -> bool:
    """Summer time (CEST, UTC+2) in Prague, from tzdata (Europe/Prague, rules Czech and EU), checked by hand: none
    1970-1978; 1979-1980 from the first Sunday of April; from 1981 the last Sunday of March; until the last Sunday of
    September up to 1995, of October from 1996. The switch is at 01:00 UTC, so noon of the start Sunday is summer time
    and noon of the end Sunday is not: start <= day < end."""
    y = day.year
    if y < 1979:
        return False
    if y <= 1980:
        start = dt.date(y, 4, 1) + dt.timedelta(days=(6 - dt.date(y, 4, 1).weekday()) % 7)
    else:
        start = last_sunday(y, 3)
    end = last_sunday(y, 9) if y <= 1995 else last_sunday(y, 10)
    return start <= day < end


def prague_noon(date: str) -> str:
    day = dt.date.fromisoformat(date)
    s = summer(day)
    stamp = dt.datetime(day.year, day.month, day.day, 10 if s else 11, 0, tzinfo=dt.timezone.utc)
    return f"{int(stamp.timestamp())} {'+0200' if s else '+0100'}"


class Clock:
    def __init__(self) -> None:
        self.clamped = 0

    def stamp(self, date: str) -> str:
        if date < "1970-01-01":
            # Prague noon on 1970-01-01 is 11:00 UTC, a valid git date; clamped commits count up from 00:00:01 UTC.
            self.clamped += 1
            return f"{self.clamped} +0000"
        return prague_noon(date)


# ---------------------------------------------------------------- acts and authors

def act_key(act: str):
    coll, year, num = act.split("/")[:3]
    m = re.match(r"^([a-z]*)(\d+)(.*)$", num)
    return (coll != "sb", coll, int(year), m.group(1) if m else "", int(m.group(2)) if m else 0, m.group(3) if m else num)


def cause_key(c: str):
    return (1,) if c == PUBLISHER else (0,) + act_key(c)


def act_name(info: Optional[dict], act: str) -> str:
    if not info:
        coll, year, num = act.split("/")[:3]
        return f"Předpis č. {num}/{year} {'Sb.' if coll == 'sb' else 'Ú. l.'}"
    kind = R.DRUH.get(info.get("druh") or "", None) or R.DRUH.get(info.get("podtyp") or "", "Předpis")
    return f"{kind} č. {info['citation']}"


def act_email(act: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", act.lower()).strip("-") + "@esbirka.invalid"


def short_title(info: dict) -> str:
    t = R.clean(info.get("short_title") or "")
    if t.startswith("\""):
        t = t.strip("\"")
    return t or R.clean(info.get("title") or "")


# ---------------------------------------------------------------- worker

_S: dict = {}


def _init(data: str) -> None:
    db = Path(data) / "db"
    _S["meta"] = sqlite3.connect(f"file:{db / 'meta.sqlite'}?mode=ro", uri=True)
    _S["vf"] = [sqlite3.connect(f"file:{p}?mode=ro", uri=True) for p in sorted(glob.glob(str(db / "vf_*.sqlite")))]
    _S["fr"] = sqlite3.connect(f"file:{db / 'fr.sqlite'}?mode=ro", uri=True)
    for c in [_S["meta"], _S["fr"], *_S["vf"]]:
        c.execute("pragma cache_size=-64000")
        c.execute("pragma mmap_size=268435456")


def versions_of(con: sqlite3.Connection, act: str) -> List[Tuple[int, str, Optional[str], str]]:
    return con.execute("""select doc, od, do, v from versions where act=? and typ='KONSOL' and stav='PUBLIKOV' and nikdy=0
                          and od < ? order by od""", (act, LIMIT)).fetchall()


def version_rows(docs: List[int]) -> Dict[int, List[Tuple]]:
    out: Dict[int, List[Tuple]] = defaultdict(list)
    q = f"select doc, h, fid, iri, odlisna from vf where doc in ({','.join('?' * len(docs))})"
    for c in _S["vf"]:
        for doc, h, fid, iri, odl in c.execute(q, docs):
            path = iri.split("/dokument", 1)[1].lstrip("/") if "/dokument" in iri else ""
            out[doc].append((h, fid, path, odl))
    return out


def fragment_texts(fids: List[int]) -> Dict[int, Tuple[str, Optional[str]]]:
    out = {}
    for i in range(0, len(fids), 900):
        ch = fids[i:i + 900]
        for fid, typ, text in _S["fr"].execute(f"select fid, typ, text from fr where fid in ({','.join('?' * len(ch))})", ch):
            out[fid] = (typ, text)
    return out


def compose(prev_order, prev_units, order, units, applied) -> Tuple[List[str], Dict[str, str]]:
    """The text between two versions when only the units in `applied` have changed: those units as in the new version,
    every other unit as in the old one, in the new order with removed units kept where they were."""
    new_set = set(order)
    prev_pos = {u: i for i, u in enumerate(prev_order)}
    merged: List[str] = []
    flushed = 0
    pending = [u for u in prev_order if u not in new_set]
    pi = 0
    for u in order:
        if u in prev_pos:
            while pi < len(pending) and prev_pos[pending[pi]] < prev_pos[u]:
                merged.append(pending[pi])
                pi += 1
        merged.append(u)
    merged.extend(pending[pi:])
    out_units = {}
    out_order = []
    for u in merged:
        t = units.get(u) if u in applied else prev_units.get(u)
        if t:
            out_units[u] = t
            out_order.append(u)
    return out_order, out_units


def delayed_marker(text: Optional[str], day: str) -> bool:
    return bool(text) and f"*(účinnost od {day})*" in text


def process_act(job: dict) -> dict:
    t0 = time.time()
    act = job["act"]
    info = job["info"]
    con = _S["meta"]
    vers = versions_of(con, act)
    docs = [v[0] for v in vers]
    rows = version_rows(docs) if docs else {}
    fids = sorted({r[1] for rs in rows.values() for r in rs if r[1] is not None})
    texts = fragment_texts(fids)
    links: Dict[int, List[Tuple]] = defaultdict(list)
    if docs:
        for doc, cil, zdroj, nact, instr in con.execute(
                f"select doc, cil, zdroj, nact, instr from links where doc in ({','.join('?' * len(docs))}) order by id", docs):
            links[doc].append((cil, zdroj, nact, instr))
    cache: Dict = {}
    events: List[dict] = []
    stats = defaultdict(int)
    prev = None
    last_cause: Dict[str, str] = {}
    for doc, od, do, v in vers:
        order, units = R.render_units(rows.get(doc, []), texts, od, cache)
        text = R.document(info, order, units)
        eli = f"{R.ESBIRKA}/eli/cz/{v}"
        if prev is None:
            events.append({"date": od, "cause": act, "kind": "first", "text": text, "units": [], "version": eli})
            for u in order:
                last_cause[u] = act
            prev = (order, units, text)
            stats["versions"] += 1
            continue
        stats["versions"] += 1
        p_order, p_units, p_text = prev
        if text == p_text:
            stats["unchanged"] += 1
            prev = (order, units, text)
            continue
        seen = set()
        changed = []
        for u in p_order + order:
            if u not in seen:
                seen.add(u)
                if p_units.get(u) != units.get(u):
                    changed.append(u)
        unit_causes: Dict[str, set] = defaultdict(set)
        vcauses = set()
        for cil, zdroj, nact, instr in links.get(doc, []):
            if not nact:
                continue
            vcauses.add(nact)
            for path in (cil, zdroj):
                if path and "/dokument/" in path:
                    unit_causes[R.unit_of(path.split("/dokument/", 1)[1])].add(nact)
        assign: Dict[str, Tuple[str, Optional[str], Optional[List[str]]]] = {}
        for u in changed:
            ub = u.split("#")[0]
            c = unit_causes.get(ub, set())
            if not c:
                # A link to the provision that holds this unit (a new § inserted whole), or to fragments inside it.
                bits = ub.split("/")
                for k in range(len(bits) - 1, 0, -1):
                    c = unit_causes.get("/".join(bits[:k]), set())
                    if c:
                        break
            if not c:
                c = set().union(*[v for k, v in unit_causes.items() if k.startswith(ub + "/")] or [set()])
            if len(c) == 1:
                assign[u] = (next(iter(c)), None, None)
            elif len(c) > 1:
                assign[u] = (PUBLISHER, None, sorted(c, key=act_key))
            elif delayed_marker(p_units.get(u), od):
                assign[u] = (last_cause.get(u, act), "delayed effect", None)
            elif len(vcauses) == 1:
                assign[u] = (next(iter(vcauses)), "version link", None)
            elif len(vcauses) > 1:
                assign[u] = (PUBLISHER, None, sorted(vcauses, key=act_key))
            elif od == info.get("in_force_from"):
                assign[u] = (act, "act in-force date", None)
            else:
                assign[u] = (PUBLISHER, None, None)
        groups: Dict[str, List[str]] = defaultdict(list)
        for u in changed:
            groups[assign[u][0]].append(u)
        ordered = sorted(groups, key=cause_key)
        applied: set = set()
        for i, cause in enumerate(ordered):
            us = groups[cause]
            applied |= set(us)
            if i == len(ordered) - 1:
                t = text
            else:
                o2, u2 = compose(p_order, p_units, order, units, applied)
                t = R.document(info, o2, u2)
            ev = {"date": od, "cause": cause, "kind": "change", "text": t, "units": [R.unit_label(u) for u in us], "version": eli}
            evid = sorted({assign[u][1] for u in us if assign[u][1]})
            cands = sorted({c for u in us for c in (assign[u][2] or [])}, key=act_key)
            if evid:
                ev["evidence"] = evid
            if cands:
                ev["candidates"] = cands
            events.append(ev)
            stats["by_" + ("publisher" if cause == PUBLISHER else "act" if cause == act else "amending")] += 1
        for u in changed:
            last_cause[u] = assign[u][0]
        prev = (order, units, text)
    # The end of the act: the day after its last version ends.
    if vers and vers[-1][2] and vers[-1][2] < "2099-12-31":
        end = (dt.date.fromisoformat(vers[-1][2]) + dt.timedelta(days=1)).isoformat()
        cands = sorted({n for d, n in job["repeals"] if d == end}, key=act_key)
        ev = {"date": end, "cause": cands[0] if len(cands) == 1 else PUBLISHER, "kind": "end", "text": None, "units": [],
              "version": f"{R.ESBIRKA}/eli/cz/{vers[-1][3]}", "last_to": vers[-1][2]}
        if len(cands) > 1:
            ev["candidates"] = cands
        if not cands:
            other = sorted({f"{n} ({d})" for d, n in job["repeals"]})
            if other:
                ev["other_repeals"] = other
        events.append(ev)
        stats["ends"] += 1
    stats["seconds"] = time.time() - t0
    return {"act": act, "events": events, "stats": dict(stats)}


# ---------------------------------------------------------------- main: blobs, then commits

def load_jobs(data: Path, acts_filter: Optional[List[str]], types: Optional[List[str]]):
    con = sqlite3.connect(data / "db" / "meta.sqlite")
    cols = [d[1] for d in con.execute("pragma table_info(acts)")]
    infos = {r[0]: dict(zip(cols, r)) for r in con.execute("select * from acts")}
    repeals: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for zdroj, od, nact in con.execute("select zdroj, od, nact from links where instr='ZRUSPRED' and zdroj is not null order by id"):
        repeals["/".join(zdroj.split("/")[:3])].append((od, nact))
    rows = con.execute("""select distinct a.act from acts a join versions v on v.act=a.act
                          where v.typ='KONSOL' and v.stav='PUBLIKOV' and v.nikdy=0 and v.od < ?
                          and ((a.coll='sb' and a.typ='PRAVPRED') or a.act in (%s))""" % ",".join("?" * len(EXTRA_ACTS)),
                       (LIMIT, *EXTRA_ACTS)).fetchall()
    acts = sorted((r[0] for r in rows), key=act_key)
    if acts_filter:
        acts = [a for a in acts if a in acts_filter]
    if types:
        acts = [a for a in acts if (infos[a].get("podtyp") in types) or a in EXTRA_ACTS]
    jobs = [{"act": a, "info": infos[a], "repeals": sorted(set(repeals.get(a, [])))} for a in acts]
    return jobs, infos


def describe(date: str, cause: str, evs: List[dict], infos: Dict[str, dict]) -> Tuple[str, str, Tuple[str, str]]:
    if cause == PUBLISHER:
        author = PUBLISHER_AUTHOR
        who = "e-Sbírka"
    else:
        info = infos.get(cause)
        who = act_name(info, cause)
        author = (who, act_email(cause))
    firsts = [e for e in evs if e["kind"] == "first"]
    changes = [e for e in evs if e["kind"] == "change"]
    ends = [e for e in evs if e["kind"] == "end"]
    parts = []
    if firsts:
        parts.append("v účinnosti" if len(firsts) == 1 and firsts[0]["act"] == cause else f"{len(firsts)} předpisů v účinnosti")
    if changes:
        if len(changes) == 1:
            c = changes[0]
            us = c["units"]
            parts.append(f"{infos[c['act']]['citation']} " + (", ".join(us[:3]) + (" a další" if len(us) > 3 else "")))
        else:
            parts.append(f"mění {len(changes)} předpisů")
    if ends:
        parts.append(f"zrušení {infos[ends[0]['act']]['citation']}" if len(ends) == 1 else f"zrušení {len(ends)} předpisů")
    subject = f"{who.replace('Zákon č. ', 'Zákon ').replace('Vyhláška č. ', 'Vyhl. ')}: {'; '.join(parts)}"
    if cause == PUBLISHER:
        subject = f"e-Sbírka (bez odkazu na novelu): {'; '.join(parts)}"
    lines: List[str] = []
    trailers: List[str] = [f"In-force: {date}"]
    if cause != PUBLISHER:
        trailers.append(f"Act: {R.ESBIRKA}/eli/cz/{cause}")
        info = infos.get(cause) or {}
        if info.get("title"):
            lines.append(f"{who}: {R.clean(info['title'])}")
            lines.append("")
    else:
        lines.append("No consolidation link in e-Sbírka names an amending act for these changes, or links name more "
                     "than one act for the same provision. They are e-Sbírka's text for the day, committed under "
                     "e-Sbírka and not credited to any act.")
        lines.append("")
        trailers.append("Explained-by: none (no single consolidation link)")
    versions, repealed, evidence, candidates = [], [], set(), set()
    for e in firsts[:300]:
        i = infos[e["act"]]
        note = ""
        if i.get("in_force_from") and i["in_force_from"] > date:
            note = f"; the act's own in-force date is {i['in_force_from']} (text printed with účinnost marks until then)"
        lines.append(f"{i['citation']} ({short_title(i)[:120]}): first version, as in force from {date}{note}. {e['version']}")
        versions.append(e["version"])
    for e in changes[:300]:
        i = infos[e["act"]]
        us = e["units"]
        lines.append(f"{i['citation']} ({short_title(i)[:120]}): {', '.join(us[:40])}{' ...' if len(us) > 40 else ''}. {e['version']}")
        versions.append(e["version"])
        evidence.update(e.get("evidence", []))
        candidates.update(e.get("candidates", []))
    for e in ends[:300]:
        i = infos[e["act"]]
        how = "repealed" if cause != PUBLISHER else "no longer in force"
        lines.append(f"{i['citation']} ({short_title(i)[:120]}): {how}; its last version ended {e['last_to']}. File removed.")
        if e.get("other_repeals"):
            lines.append(f"  e-Sbírka repeal links for this act on other days: {', '.join(e['other_repeals'][:5])}")
        repealed.append(e["act"])
        candidates.update(e.get("candidates", []))
    more = len(firsts) + len(changes) + len(ends) - min(len(firsts), 300) - min(len(changes), 300) - min(len(ends), 300)
    if more > 0:
        lines.append(f"... and {more} more")
    for v in versions[:200]:
        trailers.append(f"Version: {v}")
    if len(versions) > 200:
        trailers.append(f"Versions-omitted: {len(versions) - 200}")
    for a in repealed[:200]:
        trailers.append(f"Repeals: {R.ESBIRKA}/eli/cz/{a}")
    for ev in sorted(evidence):
        trailers.append({"version link": "Evidence: version link (the version's consolidation links name this act only)",
                         "delayed effect": "Evidence: delayed effect (the text carried this day as its účinnost od date)",
                         "act in-force date": "Evidence: act in-force date (e-Sbírka metadata; no consolidation link)"}[ev])
    for c in sorted(candidates, key=act_key):
        trailers.append(f"Candidate: {act_name(infos.get(c), c)} <{R.ESBIRKA}/eli/cz/{c}>")
    return R_shorten(subject), "\n".join(lines).rstrip() + "\n\n" + "\n".join(trailers) + "\n", author


def R_shorten(s: str, n: int = 72) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def build(a) -> None:
    data = Path(a.data)
    repo = Path(a.repo)
    t_start = time.time()
    log = open(a.log, "a", encoding="utf-8") if a.log else None

    def say(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        if log:
            log.write(line + "\n")
            log.flush()

    if repo.exists() and any(p.name != ".git" for p in repo.iterdir()):
        raise SystemExit(f"{repo} is not empty; the history is written into a new, empty directory")
    if (repo / ".git").exists():
        out = subprocess.run(["git", "rev-list", "--all", "--count"], cwd=repo, capture_output=True, text=True).stdout.strip()
        if out not in ("", "0"):
            raise SystemExit(f"{repo} already has history; write into a new, empty directory")
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=repo, check=True)
    jobs, infos = load_jobs(data, [x for x in a.acts.split(",") if x] or None, [x for x in a.types.split(",") if x] or None)
    say(f"{len(jobs)} acts")
    fi = subprocess.Popen(["git", "fast-import", "--quiet", "--done", "--depth=50", "--active-branches=5"], cwd=repo,
                          stdin=subprocess.PIPE)
    out = fi.stdin
    mark = 0
    blob_of: Dict[str, int] = {}

    def blob(text: str) -> int:
        nonlocal mark
        mark += 1
        data_ = text.encode("utf-8")
        out.write(f"blob\nmark :{mark}\ndata {len(data_)}\n".encode() + data_ + b"\n")
        return mark

    events: List[Tuple] = []
    totals: Dict[str, float] = defaultdict(float)
    slow: List[Tuple[float, str]] = []
    done = 0
    if a.profile:
        import cProfile
        import pstats
        _init(str(data))
        pr = cProfile.Profile()
        pr.enable()
        results = map(process_act, jobs)
    else:
        pool = ProcessPoolExecutor(a.workers, initializer=_init, initargs=(str(data),))
        results = pool.map(process_act, jobs, chunksize=4)
    for res in results:
        for k, v in res["stats"].items():
            totals[k] += v
        slow.append((res["stats"].get("seconds", 0), res["act"]))
        for e in res["events"]:
            m = blob(e.pop("text")) if e.get("text") is not None else None
            e.pop("text", None)
            e["act"] = res["act"]
            events.append((e["date"], cause_key(e["cause"]), act_key(res["act"]), m, e))
        done += 1
        if done % 500 == 0:
            say(f"rendered {done}/{len(jobs)} acts, {len(events)} events, {time.time() - t_start:.0f}s")
    if a.profile:
        pr.disable()
        pstats.Stats(pr).sort_stats("tottime").print_stats(25)
    else:
        pool.shutdown()
    say(f"rendered {done} acts: {dict((k, round(v)) for k, v in totals.items())}; slowest {sorted(slow, reverse=True)[:5]}")
    events.sort(key=lambda x: (x[0], x[1], x[2]))
    # Commits: one per (day, cause).
    clock = Clock()
    commits = 0
    cmark = {}
    branch_last: Dict[str, Optional[int]] = {"main": None, "future": None}
    tags: List[Tuple[str, int]] = []
    authored = defaultdict(int)
    # The commits, before any is written: one per (day, cause). Their counts go into the documentation.
    spans: List[Tuple[int, int]] = []
    i = 0
    while i < len(events):
        j = i
        while j < len(events) and events[j][0] == events[i][0] and events[j][1] == events[i][1]:
            j += 1
        spans.append((i, j))
        i = j
    first_day = events[0][0] if events else None
    main_days = [events[i][0] for i, _ in spans if events[i][0] <= a.docs_date]
    last_main_day = main_days[-1] if main_days else None
    pre = {"acts": len(jobs), "first_day": first_day, "last_main_day": last_main_day,
           "main_law_commits": len(main_days), "future_commits": len(spans) - len(main_days),
           "future": len(spans) > len(main_days),
           "clamped": sum(1 for i, _ in spans if events[i][0] < "1970-01-01"),
           "authored": {"act": sum(1 for i, _ in spans if events[i][4]["cause"] != PUBLISHER),
                        "publisher": sum(1 for i, _ in spans if events[i][4]["cause"] == PUBLISHER)},
           "tags": len({(e[4]["act"], e[0]) for e in events if e[4]["kind"] != "end" and (
               infos[e[4]["act"]].get("podtyp") in CONSTITUTIONAL or e[4]["act"] in ("sb/1993/1",) + EXTRA_ACTS)}),
           "act_types": {}, "totals": {k: round(v) for k, v in totals.items()},
           "commits": len(spans) + 1, "seconds": round(time.time() - t_start)}
    for jb in jobs:
        k = jb["info"].get("podtyp") or "OTHER"
        pre["act_types"][k] = pre["act_types"].get(k, 0) + 1
    con0 = sqlite3.connect(data / "db" / "meta.sqlite")
    pre["never"] = con0.execute("""select count(*) from versions v join acts a using(act) where a.coll='sb' and a.typ='PRAVPRED'
                                   and v.typ='KONSOL' and v.stav='PUBLIKOV' and v.nikdy=1""").fetchone()[0]
    pre["placeholder"] = con0.execute("""select count(*) from versions v join acts a using(act) where a.coll='sb' and a.typ='PRAVPRED'
                                   and v.typ='KONSOL' and v.stav='PUBLIKOV' and v.nikdy=0 and v.od >= ?""", (LIMIT,)).fetchone()[0]
    con0.close()
    future_started = False

    def path_of(act: str) -> str:
        coll, year, num = act.split("/")[:3]
        return f"{coll}/{year}/{num}.md"

    docs_written = False

    def write_docs():
        nonlocal mark, commits, docs_written
        if not a.docs and not a.docs_gen:
            docs_written = True
            return
        files = {}
        if a.docs_gen:
            import release
            files = release.documents(pre, data.resolve(), a.docs_date)
        else:
            root = Path(a.docs)
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    files[p.relative_to(root).as_posix()] = p.read_bytes()
        files = dict(sorted(files.items()))
        mark += 1
        msg = "README, LICENSE, REPRODUCE, corpus.json and tools: how the history is read, built and checked\n".encode()
        when = prague_noon(a.docs_date)
        out.write(f"commit refs/heads/main\nmark :{mark}\n".encode())
        out.write(f"author Lexifina <czechia-law@lexifina.com> {when}\ncommitter {COMMITTER} {when}\n".encode())
        out.write(f"data {len(msg)}\n".encode() + msg + b"\n")
        if branch_last["main"]:
            out.write(f"from :{branch_last['main']}\n".encode())
        for p, b in files.items():
            out.write(f"M 100644 inline {p}\ndata {len(b)}\n".encode() + b + b"\n")
        branch_last["main"] = mark
        commits += 1
        docs_written = True

    for i, j in spans:
        date = events[i][0]
        group = [e[4] for e in events[i:j]]
        marks = [e[3] for e in events[i:j]]
        cause = group[0]["cause"]
        branch = "main" if date <= a.docs_date else "future"
        if branch == "future" and not future_started:
            if branch_last["main"]:
                out.write(f"reset refs/heads/law-head\nfrom :{branch_last['main']}\n\n".encode())
            write_docs()
            future_started = True
            branch_last["future"] = branch_last["main"]
        subject, body, author = describe(date, cause, group, infos)
        mark += 1
        msg = (subject + "\n\n" + body).encode("utf-8")
        when = clock.stamp(date)
        out.write(f"commit refs/heads/{branch}\nmark :{mark}\n".encode())
        out.write(f"author {author[0]} <{author[1]}> {when}\ncommitter {COMMITTER} {when}\n".encode("utf-8"))
        out.write(f"data {len(msg)}\n".encode() + msg + b"\n")
        parent = branch_last[branch]
        if parent:
            out.write(f"from :{parent}\n".encode())
        for e, m in sorted(zip(group, marks), key=lambda x: act_key(x[0]["act"])):
            p = path_of(e["act"])
            if m is None:
                out.write(f"D {p}\n".encode())
            else:
                out.write(f"M 100644 :{m} {p}\n".encode())
        branch_last[branch] = mark
        commits += 1
        authored["publisher" if cause == PUBLISHER else "act"] += 1
        # The last commit of the day for an act is that version's tag, for the constitutional acts.
        for e in group:
            info = infos[e["act"]]
            if e["kind"] != "end" and (info.get("podtyp") in CONSTITUTIONAL or e["act"] in ("sb/1993/1",) + EXTRA_ACTS):
                cmark[(e["act"], date)] = mark
        if branch == "main":
            last_main_day = date
        if commits % 5000 == 0:
            say(f"committed {commits}, at {date}")
    if not future_started:
        if branch_last["main"]:
            out.write(f"reset refs/heads/law-head\nfrom :{branch_last['main']}\n\n".encode())
        write_docs()
    for (act, date), m in sorted(cmark.items()):
        out.write(f"reset refs/tags/{act}/{date}\nfrom :{m}\n\n".encode())
    out.write(b"done\n")
    out.close()
    if fi.wait():
        raise SystemExit("git fast-import failed")
    subprocess.run(["git", "checkout", "-q", "-f", "main"], cwd=repo, check=True)
    if commits != pre["commits"] - (0 if docs_written and (a.docs or a.docs_gen) else 1) or clock.clamped != pre["clamped"]:
        say(f"WARNING: precomputed counts differ: {pre['commits']} {commits} {pre['clamped']} {clock.clamped}")
    summary = {"acts": len(jobs), "events": len(events), "commits": commits, "clamped": clock.clamped,
               "authored": dict(authored), "first_day": first_day, "last_main_day": last_main_day,
               "future": future_started, "tags": len(cmark), "totals": {k: round(v) for k, v in totals.items()},
               "seconds": round(time.time() - t_start)}
    (repo / ".git" / "czechia-build.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    say("built " + json.dumps(summary))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--docs-date", required=True, help="the datasets' Last-Modified day; dates the documentation commit")
    ap.add_argument("--docs", default="", help="folder whose files make the documentation commit")
    ap.add_argument("--docs-gen", action="store_true", help="generate the documentation commit with release.py")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--acts", default="")
    ap.add_argument("--types", default="")
    ap.add_argument("--log", default="")
    ap.add_argument("--profile", action="store_true")
    a = ap.parse_args()
    build(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
