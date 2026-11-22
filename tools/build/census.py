"""The census of a check: every act in scope at e-Sbírka against every act this repository has ever held.

    python -I -X utf8 census.py --data DATA --repo CLONE --ref origin/main --snapshot 2026-11-22 [--json]

In scope: the acts build.py writes (Sbírka zákonů, `PRAVPRED`, plus the Charter). An act counts as held when its file
has any commit on the ref (a repealed act's file is gone at the tip, but its history is here). Every act in scope that
is not held is a gap, with a reason:
  in-force-later  its first version applies after the snapshot day: it is on `main` from that day
  awaiting-text   e-Sbírka has only its "being digitised" notice (Act 222/2016 § 12 allows 30 days)
  (none)          unexplained: an act this check should have published
`promulgated` lists the new acts e-Sbírka publishes with their promulgated text but no consolidated version yet, in
force on or before the snapshot day: they are published as enacted (append.py --promulgated) and corrected to the
consolidated text when e-Sbírka adds it.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

EXTRA_ACTS = ("sb/1993/2",)
LIMIT = "2100-01-01"
PLACEHOLDER = re.compile(r"právě digitalizujeme|digitalizace dokončena", re.I)


def act_key(act: str):
    coll, year, num = act.split("/")[:3]
    m = re.match(r"^([a-z]*)(\d+)(.*)$", num)
    return (coll, int(year), int(m.group(2)) if m else 0, num)


def repo_acts(repo: Path, ref: str) -> set:
    out = subprocess.run(["git", "log", ref, "--format=", "--name-only", "--no-renames", "--", "sb/"], cwd=repo,
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return {p[:-3] for p in set(out.split("\n")) if p.endswith(".md") and p.count("/") == 2}


def doc_texts(db: Path, doc: int):
    """The fragment texts of a version, or None when the store does not hold its fragments."""
    import glob
    fids = []
    for p in sorted(glob.glob(str(db / "vf_*.sqlite"))):
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        fids += [r[0] for r in c.execute("select fid from vf where doc=? and fid is not null", (doc,))]
        c.close()
    if not fids:
        return None
    c = sqlite3.connect(f"file:{db / 'fr.sqlite'}?mode=ro", uri=True)
    out = [r[0] or "" for r in c.execute(f"select text from fr where fid in ({','.join('?' * len(fids))})", fids)]
    c.close()
    return out


def census(data: Path, repo: Path, ref: str, snapshot: str, held: set | None = None) -> dict:
    db = data / "db"
    con = sqlite3.connect(f"file:{db / 'meta.sqlite'}?mode=ro", uri=True)
    acts = {r[0]: {"title": r[1], "iff": r[2], "ito": r[3], "approved": r[4]} for r in con.execute(
        "select act, title, in_force_from, in_force_to, approved from acts where (coll='sb' and typ='PRAVPRED') or act in (%s)"
        % ",".join("?" * len(EXTRA_ACTS)), EXTRA_ACTS)}
    kon, vyh, live = {}, {}, set()
    for act, typ, stav, nikdy, od, do, doc, v, pub in con.execute(
            "select act, typ, stav, nikdy, od, do, doc, v, published from versions"):
        if act not in acts:
            continue
        if stav == "PUBLIKOV":
            live.add(act)
        if typ == "KONSOL" and stav == "PUBLIKOV" and not nikdy and od and od < LIMIT:
            kon[act] = min(kon.get(act, od), od)
        elif typ == "VYHLZNE" and stav == "PUBLIKOV":
            vyh[act] = (doc, v, (pub or "")[:10])
    con.close()
    here = repo_acts(repo, ref)
    scope = sorted((a for a in acts if a in live), key=act_key)
    gap, promulgated, unexplained = [], {}, 0
    for a in scope:
        if a in here:
            continue
        i = acts[a]
        title = re.sub(r"\s+", " ", i["title"] or "")[:160]
        if a in kon:
            if kon[a] > snapshot:
                gap.append({"id": a, "reason": "in-force-later", "detail": f"účinnost / in force {kon[a]}", "title": title})
                continue
            gap.append({"id": a, "reason": "", "detail": f"consolidated version from {kon[a]} not on main", "title": title})
            unexplained += 1
            continue
        doc = vyh.get(a)
        texts = doc_texts(db, doc[0]) if doc else None
        pub = doc[2] if doc else ""
        if texts is None or any(PLACEHOLDER.search(t) for t in texts):
            gap.append({"id": a, "reason": "awaiting-text",
                        "detail": f"vyhlášeno / promulgated {pub or '?'}, účinnost / in force {i['iff'] or '?'}", "title": title})
            continue
        iff = i["iff"] if i["iff"] and i["iff"] < LIMIT else None
        if not iff:
            gap.append({"id": a, "reason": "", "detail": "promulgated text but no in-force day", "title": title})
            unexplained += 1
        elif iff > snapshot:
            gap.append({"id": a, "reason": "in-force-later", "detail": f"účinnost / in force {iff}", "title": title})
        elif held and a in held:
            gap.append({"id": a, "reason": "held", "detail": "", "title": title})
        else:
            ito = i["ito"] if i["ito"] and i["ito"] < LIMIT else None
            promulgated[a] = [[doc[0], iff, ito, doc[1]]]
            gap.append({"id": a, "reason": "", "detail": "promulgated text to publish as enacted", "title": title,
                        "promulgated": True})
    newest = lambda xs: max(xs, key=act_key) if xs else None
    return {"snapshot": snapshot, "source_in_scope": len(scope), "repo": len([a for a in scope if a in here]),
            "repo_files_ever": len(here), "newest_at_source": newest(scope),
            "newest_in_repo": newest([a for a in scope if a in here]), "gap": gap, "promulgated": promulgated,
            "unexplained": unexplained, "scope": scope}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = census(Path(a.data), Path(a.repo), a.ref, a.snapshot)
    if a.json:
        print(json.dumps({k: v for k, v in c.items() if k != "scope"}, ensure_ascii=False, indent=1))
    else:
        print({k: v for k, v in c.items() if k not in ("gap", "scope", "promulgated")})
        for g in c["gap"]:
            print(f"  {g['id']:<14} {g['reason'] or 'UNEXPLAINED':<15} {g['detail']}  {g['title'][:70]}")
        print("promulgated to publish:", sorted(c["promulgated"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
