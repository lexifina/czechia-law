"""Regenerate PLAN.md from a clone of czechia-law and a targets file.

    python -X utf8 tools/plan.py --repo CLONE [--ref origin/main] --targets targets.json --out PLAN.md [--counts counts.json]

targets.json holds the plan's wording, the weight and official count (target) of each part, and which counters make
its progress (`held`). The counters are read from the history of the ref, not only its tip, so an act that was
repealed (its file removed) still counts, and an act counts as held once its file and its versions are on the ref:
  sb_consolidated   sb/ files of acts with consolidated versions: every sb/ path in the build's history (BASELINE),
                    and later ones touched by e-Sbírka's corrections or by law commits in force after BASELINE_LAW_TO
                    whose Version: trailer names a dated version of that act (tools/build/append.py)
  sb_promulgated    every other sb/ file (items published as promulgated)
  sb_1918_1938      sb/1918 to sb/1938 files, either kind
  changes_total     changes to an existing act's file by law commits (not first versions, not removals, not corrections)
  changes_credited  those whose author is an act, not e-Sbírka
  credits_resolved  rows of data/credits/*.csv whose `act` column (if any) is filled in
  <name>            a path counter from COUNTERS below: distinct matches of a regex among all paths ever on the ref
Progress of a part is held/target (at most 100%); the weighted total is the sum of weight x progress over the parts with
a target, divided by the sum of all weights. Parts without a target count 0. --counts also writes files (at the tip),
files ever and commits per top-level prefix.
"""
import argparse
import csv
import io
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

COUNTERS = {
    "ul": r"^ul/.+",
    "judikatura_us": r"^judikatura/us/.+",
    "judikatura_ns": r"^judikatura/ns/.+",
    "judikatura_nss": r"^judikatura/nss/.+",
    "judikatura_eslp": r"^judikatura/eslp/.+",
    "judikatura_sdeu": r"^judikatura/sdeu/.+",
    "judikatura_bodies": r"^judikatura/(?!us/|ns/|nss/|eslp/|sdeu/)[^/]+/.+",
    "local_regulations": r"^(local/[^/]+/[^/]+/\d{4}/[^/.]+)",
    "local_other": r"^local/[^/]+/[^/]+/(?!\d{4}/)[^/]+$",
    "regulator": r"^regulator/.+",
    "vestnik": r"^vestnik/.+",
    "kolektivni_smlouvy": r"^kolektivni-smlouvy/.+",
    "treaties": r"^(?:sbms|smlouvy)/.+\.md$",
    "eu_acts": r"^(eu/[^/]+/\d{4}/[^/.]+)",
    "bills": r"^(navrhy/(?!vlada/)[^/]+/[^/]+/[^/.]+)",
    "votes": r"^data/votes/[^/]+\.csv$",
    "government_drafts": r"^(navrhy/vlada/\d{4}/[^/.]+)",
    "government_resolutions": r"^usneseni-vlady/.+\.md$",
    "dohled": r"^dohled/.+",
    "tables": r"^data/tables/[^/]+$",
}
CSV_ROWS = {"eu_transposition": "data/eu-transposition.csv"}
PREFIXES = ["sb/", "ul/", "sbms/", "local/", "eu/", "navrhy/", "usneseni-vlady/", "regulator/", "vestnik/",
            "kolektivni-smlouvy/", "historicke/", "data/credits/", "data/tables/"]
BASELINE = "6744361da955327900e0dca50d70e388aafb380b"   # main as the build and its appends left it (2026-11-13)
BASELINE_LAW_TO = "2026-11-06"                            # its last In-force day
VERSION = re.compile(r"/eli/cz/(sb/\d{4}/[^/\s]+)/\d{4}-\d\d-\d\d\s*$")


def git(repo, *a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True).stdout.decode("utf-8", "replace")


def count(repo: Path, ref: str):
    out = git(repo, "log", "--first-parent", "--no-renames", "--name-status",
              "--format=@@%H\x1f%ae\x1f%(trailers:key=Kind,valueonly,separator=,)\x1f%(trailers:key=Version,valueonly,separator=;)\x1f%(trailers:key=In-force,valueonly,separator=)", ref)
    base = set(git(repo, "rev-list", BASELINE).split())
    ever, consolidated = set(), set()
    commits = defaultdict(int)
    total = credited = 0
    cur = None
    touched = set()

    def close():
        for p in {x.split("/")[0] + "/" if not x.startswith("data/") else "/".join(x.split("/")[:2]) + "/" for x in touched}:
            commits[p] += 1

    for line in out.splitlines():
        if line.startswith("@@"):
            close()
            touched = set()
            sha, email, kind, versions, inforce = (line[2:].split("\x1f") + [""] * 5)[:5]
            cur = {"pub": email == "publisher@esbirka.invalid", "corr": kind.strip().lower() == "correction",
                   "law": bool(inforce.strip()), "base": sha in base}
            # consolidated acts: the build's (its history) and the daily append's (corrections, later law days)
            cur["cons"] = cur["base"] or (cur["corr"] and cur["pub"]) or inforce.strip() > BASELINE_LAW_TO
            cur["acts"] = {m.group(1) + ".md" for v in versions.split(";") if (m := VERSION.search(v))}
            continue
        if not line or cur is None:
            continue
        st, path = line.split("\t", 1)
        ever.add(path)
        touched.add(path)
        if path.startswith("sb/") and cur["cons"] and (cur["base"] or cur["corr"] or path in cur["acts"]):
            consolidated.add(path)
        if st == "M" and path.startswith("sb/") and cur["law"] and not cur["corr"]:
            total += 1
            credited += not cur["pub"]
    close()
    tip = set(git(repo, "ls-tree", "-r", "--name-only", ref).split("\n")) - {""}
    sb = {p for p in ever if p.startswith("sb/") and p.endswith(".md")}
    c = {"sb_consolidated": len(sb & consolidated), "sb_promulgated": len(sb - consolidated),
         "sb_1918_1938": sum(1 for p in sb if 1918 <= int(p.split("/")[1][:4] or 0) <= 1938) if sb else 0,
         "changes_total": total, "changes_credited": credited}
    for name, rx in COUNTERS.items():
        r = re.compile(rx)
        c[name] = len({(m.group(1) if m.groups() else m.group(0)) for p in ever if (m := r.match(p))})
    for name, path in CSV_ROWS.items():
        c[name] = len(rows(repo, ref, path)) if path in tip else 0
    resolved = 0
    for p in sorted(x for x in tip if x.startswith("data/credits/") and x.endswith(".csv")):
        rs = rows(repo, ref, p)
        resolved += sum(1 for r in rs if (r.get("act") or "").strip()) if rs and "act" in rs[0] else len(rs)
    c["credits_resolved"] = resolved
    per = {p: {"files": sum(1 for x in tip if x.startswith(p)), "files_ever": sum(1 for x in ever if x.startswith(p)),
               "commits": commits.get(p, 0)} for p in PREFIXES}
    return c, per


def rows(repo, ref, path):
    return list(csv.DictReader(io.StringIO(git(repo, "show", f"{ref}:{path}"))))


def fmt(n):
    return f"{n:,}"


def render(t, c):
    lines = []
    num = den = 0.0
    body = []
    for r in t["rows"]:
        if "section" in r:
            body.append(f"| **{r['section']}** | | | | | |")
            continue
        held = sum(c.get(k, 0) for k in r["held"])
        target = c.get(r["target"], 0) if isinstance(r["target"], str) else r["target"]
        frac = min(1.0, held / target) if target else 0.0
        if r["weight"] is not None:
            den += r["weight"]
            num += r["weight"] * frac
        prog = r["progress"].format(held=fmt(held), target=fmt(target) if target else "", pct=f"{100 * frac:.1f}%")
        w = "–" if r["weight"] is None else f"{r['weight']:.1f}%"
        body.append(f"| {r['part']} | {r['where']} | {w} | {prog} | {r['how']} | {r['status']} |")
    total = f"{100 * num / den:.1f}%" if den else "0.0%"
    lines.append(t["intro"].format(total=total, counted_on=t["counted_on"]))
    lines += t["table_header"] + body
    return "\n".join(lines) + "\n" + t["footer"], total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--targets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--counts", default="")
    a = ap.parse_args()
    t = json.loads(Path(a.targets).read_text(encoding="utf-8"))
    c, per = count(Path(a.repo), a.ref)
    text, total = render(t, c)
    Path(a.out).write_text(text, encoding="utf-8", newline="\n")
    if a.counts:
        Path(a.counts).write_text(json.dumps({"ref": a.ref, "sha": git(Path(a.repo), "rev-parse", a.ref).strip(),
                                              "total": total, "counters": c, "prefixes": per}, indent=1) + "\n", encoding="utf-8")
    print(f"{a.out}: {total} weighted; " + json.dumps(c))


if __name__ == "__main__":
    main()
