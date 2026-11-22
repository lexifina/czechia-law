"""Read a sample of a check's corrections again from e-Sbírka's portal: does the portal agree with the new text?

    python -I -X utf8 audit.py --batch BATCH --repo CLONE [--sample 30] [--seed X] [--out audit.json]

BATCH is a published batch (published-<sha>.jsonl or commits.jsonl): every `Kind: correction` commit names the act and
day it corrects (Corrects:), the version it sets (Version:, an ELI) and the commit it supersedes (Supersedes:). For a
sample of them, the same version is read from e-Sbírka's portal (its fragments API, one request a second, as its
robots.txt and llms.txt allow for single documents) and the letters and digits of its text are compared with those of
the new text and of the superseded one, as check_repo.py compares a version with e-Sbírka's fragment texts:
  match_new      the portal has the corrected text: the correction is right
  match_old      the portal still has the text the correction replaced
  match_neither  the portal has a third text
  unread         the portal did not answer
For a removal (no version in force on the day), the portal is asked which version is in force on that day.
This is a second path to the same publisher (its live portal, not the nightly open data the check read).
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pub" / "tools" / "build"))
import check_repo as C  # noqa: E402
import render as R  # noqa: E402

PORTAL = "https://e-sbirka.gov.cz/sbr-cache/dokumenty-sbirky/"
UA = "lexifina-law (+https://lexifina.com)"
CACHE = HERE / "cache" / "portal"
_last = [0.0]


def get(url: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / (re.sub(r"[^A-Za-z0-9._-]+", "_", url[len(PORTAL):])[:180] + ".json")
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    wait = 1.1 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        data = {"_status": e.code}
    key.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def portal_stream(version: str):
    """The letters and digits of a version's text on the portal (all pages of its fragments), or None."""
    q = urllib.parse.quote("/" + version, safe="")
    out, page, pages = [], 0, 1
    while page < pages:
        d = get(f"{PORTAL}{q}/fragmenty?cisloStranky={page}")
        if "seznam" not in d:
            return None
        pages = d.get("pocetStranek") or 1
        for f in d["seznam"]:
            t = R.DOWNLEVEL.sub("", R.COMMENT.sub("", f.get("xhtml") or ""))
            out.append(C.SUPSUB.sub("", "".join(R._math(x) if m else html.unescape(C.ANYTAG.sub(" ", x))
                                                for m, x in R.math_split(t))))
        page += 1
    return "".join(C.ALNUM.findall(R.INVISIBLE.sub("", " ".join(out))))


def in_force_on(act: str, day: str):
    """Whether the portal has the act in force on a day: (True/False, what it says), or (None, status) unread. The
    act's own record gives its last version's end (datumUcinnostiZneniDo) and its repeal day (datumZruseni)."""
    d = get(PORTAL + urllib.parse.quote(f"/{act}", safe=""))
    if "_status" in d:
        return None, f"HTTP {d['_status']}"
    end, rep = d.get("datumUcinnostiZneniDo"), d.get("datumZruseni")
    gone = bool((rep and rep <= day) or (end and end < day and d.get("typZneni") == "MINULE"))
    return (not gone), f"zrušeno / repealed {rep or '-'}, last version to {end or '-'}"


def trailers(msg: str) -> dict:
    out = {}
    for line in msg.rstrip().split("\n\n")[-1].splitlines():
        k, sep, v = line.partition(": ")
        if sep:
            out.setdefault(k, v)
    return out


def corrections(batch: Path):
    files = sorted(batch.glob("published-*.jsonl")) or [batch / "commits.jsonl"]
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            t = trailers(c["message"])
            if t.get("Kind") != "correction" or "Corrects" not in t:
                continue
            act, _, rng = t["Corrects"].partition(" ")
            path, text = next(iter(c["files"].items()))
            ver = t.get("Version", "").split("/eli/cz/", 1)[-1] if t.get("Version") else None
            kind = "removed" if text is None else "text"
            yield {"act": act, "from": rng.split("..")[0], "path": path, "new": text, "version": ver,
                   "supersedes": t.get("Supersedes"), "kind": kind, "subject": c["message"].split("\n", 1)[0]}


def audit(batch: Path, repo: Path, sample: int, seed: str) -> dict:
    cs = list(corrections(batch))
    rnd = random.Random(seed)
    pick = rnd.sample(cs, min(sample, len(cs)))
    rows, n = [], {"match_new": 0, "match_old": 0, "match_neither": 0, "unread": 0}
    for c in pick:
        row = {k: c[k] for k in ("act", "from", "version", "kind")}
        if c["kind"] == "removed":
            eff, says = in_force_on(c["act"], c["from"])
            row["portal"] = says
            verdict = "unread" if eff is None else "match_old" if eff else "match_new"
        else:
            p = portal_stream(c["version"]) if c["version"] else None
            if p is None:
                verdict = "unread"
            else:
                new = C.stream_rendered(c["new"])
                old = None
                if c["supersedes"]:
                    r = subprocess.run(["git", "show", f"{c['supersedes']}:{c['path']}"], cwd=repo, capture_output=True)
                    old = C.stream_rendered(r.stdout.decode("utf-8")) if r.returncode == 0 else None
                verdict = "match_new" if p == new else "match_old" if old is not None and p == old else "match_neither"
        row["verdict"] = verdict
        n[verdict] += 1
        rows.append(row)
    return {"corrections": len(cs), "sampled": len(pick), **n, "rows": rows,
            "method": "e-Sbírka portal fragments API, letters and digits compared as check_repo.py does"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--sample", type=int, default=30)
    ap.add_argument("--seed", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    res = audit(Path(a.batch), Path(a.repo), a.sample, a.seed or a.batch)
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, ensure_ascii=False))
    for r in res["rows"]:
        print(f"  {r['verdict']:<14} {r['kind']:<8} {r['act']} {r['from']} {r.get('version') or r.get('portal')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
