"""Hand-check helper: for each empty-period flag that survived the rebuttal, the lines of the extending commit's diff
that hold the old or the new date (Czech or numeric format)."""
import json, re, subprocess, sys
G = "gl/vulnerabilities/scripts/sources/corpus/czechia-law.git"; PIN = "aa02aa05dc66bdff595c04995523e3955feed005"
MON = "ledna února března dubna května června července srpna září října listopadu prosince".split()
def forms(d):
    y, m, dd = d.split("-"); m, dd = int(m), int(dd)
    return [f"{dd}. {MON[m-1]} {y}", f"{dd}.{m}.{y}", f"{dd}. {m}. {y}", f"{dd:02d}.{m:02d}.{y}", d]
def git(*a): return subprocess.run(["git", "-C", G, *a], capture_output=True).stdout.decode("utf-8", "replace")
seen = set()
for x in map(json.loads, open("gl/vulnerabilities/scripts/findings/run/late_extension_triage.jsonl", encoding="utf-8")):
    if not x.get("rebut", {}).get("survives"): continue
    r = x["row"]; k = (r["path"], r["old_until"], r["new_until"], r["law"])
    if k in seen: continue
    seen.add(k)
    c = [l.split()[0] for l in git("log", "--format=%h %an", PIN, "--", r["path"]).splitlines() if l.split(" ", 1)[1] == r["law"]]
    hits = []
    for cc in c:
        d = git("diff", "-U0", "--word-diff", f"{cc}^", cc, "--", r["path"])
        for line in d.splitlines():
            if any(f in line for f in forms(r["old_until"]) + forms(r["new_until"])) and ("{+" in line or "[-" in line):
                hits.append(line.strip()[:330])
    title = next((l[7:120] for l in git("show", f"{PIN}:{r['path']}").splitlines() if l.startswith("nazev:")), "")
    print(f"## {r['path']} {title}\n   {r['old_until']} -> {r['new_until']} by {r['law']} in force {r['extended_in_force']} ({r['gap_days']} d)")
    for h in hits[:3]: print("     ", h)
    if not hits: print("      (no diff line holds both dates)")
