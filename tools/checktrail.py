"""The check trail of czechia-law: every time an official source is read, what was read, when, and what it led to.

    python tools/checktrail.py                      the latest check of every source, and the sources not watched
    python tools/checktrail.py --day 2026-11-21     every check made on a day (UTC)
    python tools/checktrail.py --act sb/2026/220    every check that saw, published or did not publish an act
    python tools/checktrail.py --source e-sbirka    the checks of one source
    python tools/checktrail.py --json ...           the same records as JSON lines
    python tools/checktrail.py --pages DIR          write the pages (monitoring/, WATCHING*.md, FRESHNESS*.md) from data/

Records (schema `lexifina-check/1`) are JSON lines in data/checks/<YYYY-MM>.jsonl, one per check, failed checks
included; data/checks/sources.json lists every official source and whether it is watched; data/checks/latest.json is
the newest record per source. They are appended by a `Kind: check` commit (no In-force: trailer, so readers of the law
ignore it), which also rewrites the pages: monitoring/README.md (Czech) and README.en.md (English), the monthly log
monitoring/checks/<YYYY-MM>.md, WATCHING.md and FRESHNESS.md. Every law or correction commit a check publishes carries
`Check: <check_id>`.

A record:
  check_id, source, corpus, runner (tool and its commit), attempt, started, finished (UTC),
  outcome: no-change | changed | not-refreshed | source-error | failed | anomaly,
  requests: [{method, url, at, status, last_modified, etag, bytes, sha256}],
  snapshot: the source's data day,
  census: {source_in_scope, repo, newest_at_source, newest_in_repo},
  seen / published: {added, changed, removed}: act ids (seen: what the source shows as new, changed or gone since the
      last check; published: what was committed for it),
  gap: [{id, reason, detail, title}]: every in-scope item at the source that the repository does not hold, each with a
      reason from REASONS; unexplained: how many have none (must be 0),
  flags: [{flag, detail}] (FLAGS), audit: a sample of changed texts read again from e-Sbírka's portal,
  verify: the check of the published history against the snapshot, commits: {from, to, count}, error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = "lexifina-check/1"
REPO_URL = "https://github.com/lexifina/czechia-law"
GL = "https://github.com/lexifina/global-law/blob/main"
REASONS = {
    "in-force-later": ("účinnost později: na větvi `future`, na `main` v den účinnosti",
                       "in force later: on the `future` branch, on `main` from the day it applies"),
    "awaiting-text": ("e-Sbírka zatím zveřejnila jen oznámení, že text digitalizuje (§ 12 zákona č. 222/2016 Sb. dává 30 dní)",
                      "e-Sbírka has published only a notice that it is digitising the text (§ 12 of Act 222/2016 allows 30 days)"),
    "out-of-scope": ("mimo rozsah tohoto repozitáře", "outside this repository's scope"),
    "held": ("zadrženo kontrolou", "held by a check"),
    "failed": ("krok selhal", "a step failed"),
}
FLAGS = {
    "mass-change": ("hromadná změna: více než 200 předpisů nebo 1 % v jedné kontrole; vzorek ověřen na portálu e-Sbírky",
                    "mass change: over 200 acts or 1% in one check; a sample was read again on e-Sbírka's portal"),
    "flip-flop": ("předpis opravený ve 2 z posledních 7 kontrol", "an act corrected in 2 of the last 7 checks"),
    "census-drop": ("zdroj uvádí méně předpisů než minule", "the source lists fewer acts than last time"),
    "unexplained-gap": ("rozdíl mezi zdrojem a repozitářem bez důvodu", "a gap between the source and the repository with no reason"),
    "source-lag": ("data zdroje nebyla obnovena déle než 2 dny", "the source's data was not refreshed for over 2 days"),
}
OUTCOME = {
    "no-change": ("beze změny", "no change"), "changed": ("změny zveřejněny", "changes published"),
    "not-refreshed": ("data zdroje ještě nebyla obnovena", "the source had not refreshed its data yet"),
    "source-error": ("zdroj neodpověděl", "the source did not answer"), "failed": ("kontrola selhala", "the check failed"),
    "anomaly": ("změny zveřejněny, s příznakem", "changes published, flagged"),
}
STATE = {"watched": ("sledován", "watched"), "not-yet-watched": ("zatím nesledován", "not watched yet"),
         "paused": ("pozastaven", "paused"), "closed": ("uzavřený zdroj", "closed source")}
SCHEDULE = {"daily": ("denně", "daily"), "weekly": ("týdně", "weekly"), "none": ("—", "—")}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- writing a record

class Check:
    """One check of one source. `with Check(...) as c:` sets outcome `failed` (and `error`) if the body raises."""

    def __init__(self, source: str, corpus: str, runner: str, attempt: int = 1):
        self.r = {"schema": SCHEMA, "check_id": "", "source": source, "corpus": corpus, "runner": runner,
                  "attempt": attempt, "started": utcnow(), "finished": None, "outcome": None, "requests": [],
                  "snapshot": None, "census": {}, "seen": {"added": [], "changed": [], "removed": []},
                  "published": {"added": [], "changed": [], "removed": []}, "gap": [], "unexplained": 0,
                  "flags": [], "audit": None, "verify": None, "commits": None, "titles": {}, "error": None}
        self.r["check_id"] = f"cz-{source}-{self.r['started'].replace('-', '').replace(':', '')}"

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if ev is not None and not self.r["outcome"]:
            self.r["outcome"] = "failed"
            self.r["error"] = public_error(ev)
        self.r["finished"] = self.r["finished"] or utcnow()
        return False

    def request(self, method: str, url: str, status, **meta):
        row = {"method": method, "url": url, "at": utcnow(), "status": status}
        row.update({k: v for k, v in meta.items() if v is not None})
        self.r["requests"].append(row)
        return row

    def flag(self, flag: str, detail: str):
        self.r["flags"].append({"flag": flag, "detail": detail})

    def done(self, outcome: str):
        self.r["outcome"] = outcome
        self.r["finished"] = utcnow()


def public_error(e) -> str:
    """An error without machine names or local paths (the trail is public)."""
    s = f"{type(e).__name__}: {e}"
    s = re.sub(r"[A-Za-z]:[\\/][^\s'\"]*", "<path>", s)
    s = re.sub(r"/(?:home|Users|tmp|var)/[^\s'\"]*", "<path>", s)
    return s[:300]


def save_pending(record: dict, pending: Path):
    pending.parent.mkdir(parents=True, exist_ok=True)
    with open(pending, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_pending(pending: Path) -> list:
    if not pending.exists():
        return []
    return [json.loads(l) for l in pending.read_text(encoding="utf-8").splitlines() if l.strip()]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- reading the trail

def month_of(ts: str) -> str:
    return ts[:7]


def load_records(root: Path) -> list:
    out = []
    for p in sorted((root / "data" / "checks").glob("20??-??.jsonl")):
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.strip():
                out.append(json.loads(l))
    out.sort(key=lambda r: r["started"])
    return out


def load_sources(root: Path) -> list:
    return json.loads((root / "data" / "checks" / "sources.json").read_text(encoding="utf-8"))["sources"]


def latest(records: list) -> dict:
    out = {}
    for r in records:
        out[r["source"]] = r
    return out


def last_success(records: list, source: str):
    ok = [r for r in records if r["source"] == source and r["outcome"] in ("no-change", "changed", "anomaly")]
    return ok[-1] if ok else None


def flip_flops(records: list, source: str, current: dict, n: int = 7) -> list:
    """Acts changed (corrected) in at least 2 of the last n checks of a source that changed something, counting
    `current` (not yet in records)."""
    rs = [r for r in records if r["source"] == source and r["outcome"] in ("changed", "anomaly")][-(n - 1):] + [current]
    c = Counter(a for r in rs for a in set(r.get("published", {}).get("changed", [])))
    return sorted(a for a, k in c.items() if k >= 2 and a in set(current.get("published", {}).get("changed", [])))


# ---------------------------------------------------------------- pages

def _d(ts):
    return (ts or "")[:16].replace("T", " ")


def _n(x):
    return f"{x:,}".replace(",", " ") if isinstance(x, int) else (x or "0")


def _counts(r, part="published"):
    p = r.get(part) or {}
    return len(p.get("added", [])), len(p.get("changed", [])), len(p.get("removed", []))


def _act_link(a: str, titles: dict, lang: int, here: bool = True) -> str:
    """An act: its file here, or (not held here) its page on e-Sbírka."""
    t = titles.get(a)
    if not a.startswith(("sb/", "sbms/")):
        link = f"`{a}`"
    elif here:
        link = f"[`{a}`]({REPO_URL}/blob/main/{a}.md)"
    else:
        link = f"[`{a}`](https://e-sbirka.gov.cz/eli/cz/{a})"
    return f"{link} {t}" if t else link


def _commits(r) -> str:
    c = r.get("commits") or {}
    if not c.get("count"):
        return "—"
    return f"[{c['count']}]({REPO_URL}/compare/{c['from'][:12]}...{c['to'][:12]})"


def headline(r: dict, src: dict, lang: int) -> str:
    a, ch, rm = _counts(r)
    name = src["name"][["cs", "en"][lang]] if src else r["source"]
    reqs = len(r.get("requests") or [])
    if lang == 0:
        s = (f"**Poslední kontrola:** {_d(r['finished'] or r['started'])} UTC, {name}: přečteno {reqs} adres; "
             f"{a} nových, {ch} změněných, {rm} zrušených; {OUTCOME[r['outcome']][0]}; "
             f"nezveřejněno {len(r.get('gap', []))}, z toho bez důvodu {r.get('unexplained', 0)}.")
    else:
        s = (f"**Last check:** {_d(r['finished'] or r['started'])} UTC, {name}: {reqs} addresses read; "
             f"{a} added, {ch} changed, {rm} removed; {OUTCOME[r['outcome']][1]}; "
             f"{len(r.get('gap', []))} not published, {r.get('unexplained', 0)} of them with no reason.")
    if r.get("flags"):
        s += (" Příznaky: " if lang == 0 else " Flags: ") + ", ".join(f"`{f['flag']}`" for f in r["flags"]) + "."
    return s


def monitoring_page(records, sources, lang: int, now: str) -> str:
    L = lang
    srcs = {s["id"]: s for s in sources}
    lat = latest(records)
    other = "README.en.md" if L == 0 else "README.md"
    out = []
    if L == 0:
        out += ["# Monitoring: co se čte a co z toho vzešlo", "", f"[English]({other})", "",
                f"Jak global-law sleduje všechny země: [global-law monitoring/]({GL.replace('/blob/', '/tree/')}/monitoring). "
                "Tato stránka je totéž jen pro Česko: každé čtení oficiálního zdroje, kdy proběhlo a co z něj vzešlo "
                "(nové, změněné a zrušené předpisy). Strojově čitelná podoba je v [data/checks/](../data/checks/) "
                "(JSON Lines, schéma `lexifina-check/1`), v `git log` jako commity `Kind: check` a po měsících v "
                "[checks/](checks/)."]
    else:
        out += ["# Monitoring: what is read and what came of it", "", f"[Čeština]({other})", "",
                f"How global-law monitors every country: [global-law monitoring/]({GL.replace('/blob/', '/tree/')}/monitoring). "
                "This page is the same for Czechia only: every time an official source is read, when, and what came of "
                "it (acts added, changed and removed). The machine-readable form is [data/checks/](../data/checks/) "
                "(JSON Lines, schema `lexifina-check/1`), in `git log` as `Kind: check` commits, and month by month in "
                "[checks/](checks/)."]
    main = lat.get("e-sbirka")
    if main:
        out += ["", headline(main, srcs.get("e-sbirka"), L)]
    out += ["", "## Zdroje" if L == 0 else "## Sources", ""]
    out += ["| Zdroj | Složky | Jak často | Poslední úspěšná kontrola | Poslední výsledek | Stav |" if L == 0 else
            "| Source | Folders | How often | Last successful check | Last result | State |", "| --- | --- | --- | --- | --- | --- |"]
    for s in sources:
        r = lat.get(s["id"])
        ok = last_success(records, s["id"])
        res = OUTCOME[r["outcome"]][L] if r else "—"
        out.append(f"| [{s['name'][['cs', 'en'][L]]}]({s['url']}) | {', '.join(f'`{x}`' for x in s['folders'])} | "
                   f"{SCHEDULE[s['schedule']][L]} | {(_d(ok['finished']) + ' UTC') if ok else '—'} | {res} | "
                   f"{STATE[s['state']][L]}{(': ' + s['note'][['cs', 'en'][L]]) if s.get('note') else ''} |")
    cut = (dt.datetime.fromisoformat(now.replace("Z", "+00:00")) - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [r for r in records if r["started"] >= cut]
    out += ["", "## Posledních 30 dní" if L == 0 else "## The last 30 days", ""]
    if not recent:
        out.append("Zatím žádná kontrola." if L == 0 else "No check yet.")
    else:
        out += ["| Začátek (UTC) | Zdroj | Přečteno | Nové | Změněné | Zrušené | Nezveřejněno (bez důvodu) | Výsledek | Commity |" if L == 0 else
                "| Started (UTC) | Source | Read | Added | Changed | Removed | Not published (no reason) | Result | Commits |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |"]
        for r in reversed(recent):
            a, ch, rm = _counts(r)
            res = OUTCOME[r["outcome"]][L] + ("".join(f" `{f['flag']}`" for f in r.get("flags", [])))
            m = month_of(r["started"])
            bf = r.get("backfilled")
            gapcol = "—" if bf else f"{len(r.get('gap', []))} ({r.get('unexplained', 0)})"
            out.append(f"| [{_d(r['started'])}](checks/{m}.md#{r['check_id'].lower()}) | {r['source']} | "
                       f"{len(r.get('requests') or [])}{'†' if bf else ''} | {a} | {ch} | {rm} | {gapcol} | "
                       f"{res} | {_commits(r)} |")
        if any(r.get("backfilled") for r in recent):
            out += ["", ("† Doplněno 22. 11. 2026 ze záznamu běhu: dotazy HEAD a sčítání (census) se tehdy nezapisovaly, "
                         "uvedena jsou jen stažení." if L == 0 else
                         "† Backfilled on 2026-11-22 from the run's log: its HEAD requests and census were not recorded, "
                         "so only the downloads are listed.")]
    out += ["", "## Jak to ověřit sami" if L == 0 else "## Check it yourself", "", "```",
            "python tools/checktrail.py                      # " + ("poslední kontrola každého zdroje" if L == 0 else "the latest check of every source"),
            "python tools/checktrail.py --day 2026-11-21     # " + ("všechny kontroly jednoho dne" if L == 0 else "every check of a day"),
            "python tools/checktrail.py --act sb/2026/220    # " + ("kdy byl předpis viděn a zveřejněn" if L == 0 else "when an act was seen and published"),
            "git log --grep='^Kind: check' --format='%ci %s'  # " + ("kontroly v historii" if L == 0 else "the checks in the history"),
            "```", "",
            ("Právně závazné je jen znění vyhlášené ve Sbírce zákonů a mezinárodních smluv (e-Sbírka, Ministerstvo vnitra ČR); "
             "konsolidovaná znění e-Sbírky jsou informativní." if L == 0 else
             "Only the text promulgated in the Collection of Laws and International Treaties (e-Sbírka, Ministry of the "
             "Interior of the Czech Republic) is legally binding; e-Sbírka's consolidated versions are informative."), ""]
    return "\n".join(out)


def month_page(records, sources, month: str) -> str:
    srcs = {s["id"]: s for s in sources}
    rs = [r for r in records if month_of(r["started"]) == month]
    out = [f"# Kontroly / Checks {month}", "",
           "Každé čtení oficiálního zdroje v tomto měsíci, nejnovější první. / Every read of an official source this "
           f"month, newest first. Záznamy / Records: [data/checks/{month}.jsonl](../../data/checks/{month}.jsonl).", ""]
    for r in reversed(rs):
        s = srcs.get(r["source"]) or {"name": {"cs": r["source"], "en": r["source"]}}
        out += [f"## {_d(r['started'])} UTC · {s['name']['cs']} · {OUTCOME[r['outcome']][0]} / {OUTCOME[r['outcome']][1]}",
                f"<a id=\"{r['check_id'].lower()}\"></a>", "",
                f"- Kontrola / Check: `{r['check_id']}` (pokus / attempt {r.get('attempt', 1)}), "
                f"{_d(r['started'])}–{_d(r['finished'])[11:]} UTC, `{r.get('runner', '')}`"]
        if r.get("backfilled"):
            out.append("- Doplněno ze záznamu běhu / Backfilled from the run's log (2026-11-22): dotazy HEAD a census "
                       "se nezapisovaly / HEAD requests and the census were not recorded")
        if r.get("snapshot"):
            out.append(f"- Snímek zdroje / Source's data of: {r['snapshot']}")
        c = r.get("census") or {}
        if c:
            out.append(f"- Ve zdroji / At the source: {_n(c.get('source_in_scope'))} předpisů / acts "
                       f"(nejnovější / newest `{c.get('newest_at_source')}`); v repozitáři / here: {_n(c.get('repo'))} "
                       f"(nejnovější / newest `{c.get('newest_in_repo')}`)")
        titles = r.get("titles") or {}
        for key, cs, en in (("added", "Nové", "Added"), ("changed", "Změněné", "Changed"), ("removed", "Zrušené", "Removed")):
            seen, pub = r["seen"].get(key, []), r["published"].get(key, [])
            if seen or pub:
                shown = ", ".join(_act_link(a, titles, 0) for a in pub[:40])
                more = f" a dalších / and {len(pub) - 40} more" if len(pub) > 40 else ""
                out.append(f"- {cs} / {en}: viděno / seen {len(seen)}, zveřejněno / published {len(pub)}" +
                           (f": {shown}{more}" if pub else ""))
        if r.get("gap"):
            out.append(f"- Nezveřejněno / Not published: {len(r['gap'])}, bez důvodu / with no reason: {r.get('unexplained', 0)}")
            out += ["", "  | Předpis / Act | Důvod / Reason | Podrobnosti / Detail |", "  | --- | --- | --- |"]
            for g in r["gap"][:60]:
                why = REASONS.get(g["reason"], ("?", "?"))
                out.append(f"  | {_act_link(g['id'], titles, 0, here=False)} | `{g['reason']}`: {why[1]} | {g.get('detail', '')} |")
            if len(r["gap"]) > 60:
                out.append(f"  | … | | a dalších / and {len(r['gap']) - 60} more |")
            out.append("")
        if r.get("verify"):
            v = r["verify"]
            out.append(f"- Ověření / Verified: {_n(v.get('versions_checked'))} znění / versions, "
                       f"{v.get('versions_differ', 0)} se liší / differ, konce / ends {_n(v.get('ends_checked'))} "
                       f"({v.get('ends_wrong', 0)} chybně / wrong): {'OK' if v.get('ok') else 'CHYBA / FAILED'}")
        for f in r.get("flags", []):
            out.append(f"- Příznak / Flag `{f['flag']}`: {FLAGS.get(f['flag'], ('', ''))[1]}. {f.get('detail', '')}")
        if r.get("audit"):
            au = r["audit"]
            out.append(f"- Ověření na portálu / Read again on the portal: {au.get('sampled', 0)} znění / versions, "
                       f"shoda s novým textem / match the new text {au.get('match_new', 0)}, se starým / the old "
                       f"{au.get('match_old', 0)}, s žádným / neither {au.get('match_neither', 0)}, nečitelné / unread {au.get('unread', 0)}")
        if r.get("commits") and r["commits"].get("count"):
            out.append(f"- Commity / Commits: {_commits(r)}")
        if r.get("error"):
            out.append(f"- Chyba / Error: `{r['error']}`")
        if r.get("requests"):
            out += ["", "  | Čas / At (UTC) | Metoda | Adresa / Address | Stav / Status | Last-Modified | Bajtů / Bytes |",
                    "  | --- | --- | --- | --- | --- | ---: |"]
            for q in r["requests"]:
                out.append(f"  | {q['at'][11:19]} | {q['method']} | {q['url']} | {q.get('status')} | "
                           f"{q.get('last_modified', '')} | {_n(q.get('bytes'))} |")
        out.append("")
    return "\n".join(out)


def watching_page(records, sources, lang: int) -> str:
    L = lang
    other = "WATCHING.en.md" if L == 0 else "WATCHING.md"
    out = (["# Sledování zdrojů: co se sleduje pro Česko", "", f"[English]({other})", "",
            f"Jak global-law sleduje zdroje všech zemí: [global-law WATCHING.md]({GL}/WATCHING.md). Tato stránka je totéž "
            "jen pro Česko: každý oficiální zdroj, ze kterého tento repozitář bere text, co se na něm čte, jak často a "
            "kdy naposledy. Každé čtení a jeho výsledek: [monitoring/](monitoring/README.md).", ""]
           if L == 0 else
           ["# Watching the sources: what is watched for Czechia", "", f"[Čeština]({other})", "",
            f"How global-law watches every country's sources: [global-law WATCHING.md]({GL}/WATCHING.md). This page is the "
            "same for Czechia only: every official source this repository takes text from, what is read on it, how "
            "often and when it was last read. Every read and what came of it: [monitoring/](monitoring/README.en.md).", ""])
    out += ["| Zdroj | Co se čte | Složky | Jak často | Naposledy přečteno | Stav |" if L == 0 else
            "| Source | What is read | Folders | How often | Last read | State |", "| --- | --- | --- | --- | --- | --- |"]
    lat = latest(records)
    for s in sources:
        r = lat.get(s["id"])
        out.append(f"| [{s['name'][['cs', 'en'][L]]}]({s['url']}) | {s['reads'][['cs', 'en'][L]]} | "
                   f"{', '.join(f'`{x}`' for x in s['folders'])} | {SCHEDULE[s['schedule']][L]} | "
                   f"{(_d(r['started']) + ' UTC') if r else '—'} | {STATE[s['state']][L]}"
                   f"{(': ' + s['note'][['cs', 'en'][L]]) if s.get('note') else ''} |")
    out += ["", ("Zdroje se čtou podle jejich robots.txt a pokynů, s pauzami mezi dotazy; e-Sbírku z jejích denních "
                 "otevřených dat, ne procházením portálu." if L == 0 else
                 "Sources are read within their robots.txt and guidance, with pauses between requests; e-Sbírka from its "
                 "daily open data, not by crawling the portal."), ""]
    return "\n".join(out)


def freshness_doc(records, sources, repo_acts: int, now: str) -> dict:
    """data/freshness.json in the per-act schema global-law's tools/freshness.py reads (own_freshness)."""
    today = now[:10]
    ok = last_success(records, "e-sbirka")
    day = ok["finished"][:10] if ok else None
    age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(day)).days if day else None
    st = "current" if age is not None and age <= 7 else "stale" if day else "unverified"
    lat = latest(records)
    srcs = []
    for s in sources:
        if s["state"] != "watched":
            continue
        r, good = lat.get(s["id"]), last_success(records, s["id"])
        down = r and r["outcome"] == "source-error"
        first_bad = None
        if down:
            bad = [x for x in records if x["source"] == s["id"] and (not good or x["started"] > good["started"])]
            first_bad = bad[0]["started"][:10] if bad else None
        row = {"source": s["id"], "name": s["name"]["en"], "state": "unavailable" if down else "available",
               "last_successful_check": good["finished"][:10] if good else None,
               "last_successful_contact": good["finished"][:10] if good else None}
        if first_bad:
            row["unavailable_since"] = first_bad
        srcs.append(row)
    return {"schema": "cz-freshness/1", "as_of": today,
            "note": "How current czechia-law is, from its check trail (data/checks/): the day e-Sbírka's open data was "
                    "last read and every act checked against it. tools/checktrail.py reads the trail.",
            "checked_against_official_source": day,
            "totals": {"acts": repo_acts, "by_status": {"current": repo_acts if st == "current" else 0,
                                                        "pending-change": 0, "stale": repo_acts if st == "stale" else 0,
                                                        "unverified": repo_acts if st == "unverified" else 0,
                                                        "source-unavailable": 0}},
            "sources": srcs}


def freshness_page(records, sources, repo_acts: int, lang: int, now: str) -> str:
    L = lang
    other = "FRESHNESS.en.md" if L == 0 else "FRESHNESS.md"
    ok = last_success(records, "e-sbirka")
    lat = latest(records).get("e-sbirka")
    c = (lat or {}).get("census") or {}
    gap = (lat or {}).get("gap") or []
    by = Counter(g["reason"] for g in gap)
    if L == 0:
        out = ["# Aktuálnost: platí to právě teď?", "", f"[English]({other})", "",
               f"Jak global-law měří aktuálnost všech zemí: [global-law FRESHNESS.md]({GL}/FRESHNESS.md). Pro Česko:", "",
               f"- Otevřená data e-Sbírky naposledy přečtena a celá historie s nimi porovnána: **{_d(ok['finished']) + ' UTC' if ok else 'zatím ne'}**.",
               f"- Předpisů v rozsahu ve zdroji: {_n(c.get('source_in_scope'))}; v tomto repozitáři: {_n(c.get('repo'))}; "
               f"nejnovější ve zdroji `{c.get('newest_at_source')}`, zde `{c.get('newest_in_repo')}`.",
               f"- Nezveřejněno: {len(gap)} (" + ", ".join(f"{REASONS[k][0]}: {v}" for k, v in by.items()) +
               f"); bez důvodu: {(lat or {}).get('unexplained', 0)}.",
               "", "Podrobně: [monitoring/](monitoring/README.md). Strojově: [data/freshness.json](data/freshness.json).", ""]
    else:
        out = ["# Freshness: is it true right now?", "", f"[Čeština]({other})", "",
               f"How global-law measures how current every country is: [global-law FRESHNESS.md]({GL}/FRESHNESS.md). For Czechia:", "",
               f"- e-Sbírka's open data last read and the whole history compared with it: **{_d(ok['finished']) + ' UTC' if ok else 'not yet'}**.",
               f"- In-scope acts at the source: {_n(c.get('source_in_scope'))}; in this repository: {_n(c.get('repo'))}; "
               f"newest at the source `{c.get('newest_at_source')}`, here `{c.get('newest_in_repo')}`.",
               f"- Not published: {len(gap)} (" + ", ".join(f"{REASONS[k][1]}: {v}" for k, v in by.items()) +
               f"); with no reason: {(lat or {}).get('unexplained', 0)}.",
               "", "In detail: [monitoring/](monitoring/README.en.md). For programs: [data/freshness.json](data/freshness.json).", ""]
    return "\n".join(out)


def build_files(root_records: list, pending: list, sources: list, repo_acts: int, now: str) -> dict:
    """{path: text} for the trail commit: the month files with the pending records appended, latest.json,
    freshness.json and every page."""
    records = sorted(root_records + pending, key=lambda r: r["started"])
    files = {}
    months = sorted({month_of(r["started"]) for r in pending})
    for m in months:
        rows = [r for r in records if month_of(r["started"]) == m]
        files[f"data/checks/{m}.jsonl"] = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        files[f"monitoring/checks/{m}.md"] = month_page(records, sources, m)
    files["data/checks/latest.json"] = json.dumps({"schema": SCHEMA, "generated": now, "latest": latest(records),
                                                   "last_success": {s["id"]: (last_success(records, s["id"]) or {}).get("finished")
                                                                    for s in sources}},
                                                  ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    files["data/freshness.json"] = json.dumps(freshness_doc(records, sources, repo_acts, now), ensure_ascii=False, indent=1) + "\n"
    files["monitoring/README.md"] = monitoring_page(records, sources, 0, now)
    files["monitoring/README.en.md"] = monitoring_page(records, sources, 1, now)
    files["WATCHING.md"] = watching_page(records, sources, 0)
    files["WATCHING.en.md"] = watching_page(records, sources, 1)
    files["FRESHNESS.md"] = freshness_page(records, sources, repo_acts, 0, now)
    files["FRESHNESS.en.md"] = freshness_page(records, sources, repo_acts, 1, now)
    return files


def commit_message(pending: list, sources: list) -> str:
    srcs = {s["id"]: s for s in sources}
    day = pending[-1]["started"][:10]
    a = sum(len(r["published"]["added"]) for r in pending)
    ch = sum(len(r["published"]["changed"]) for r in pending)
    rm = sum(len(r["published"]["removed"]) for r in pending)
    names = sorted({srcs.get(r["source"], {"name": {"cs": r["source"]}})["name"]["cs"].split(" – ")[0] for r in pending})
    subject = (f"Kontrola / Check {day}: {', '.join(names)}: {a} nových, {ch} změněných, {rm} zrušených / "
               f"{a} added, {ch} changed, {rm} removed")
    body = []
    for r in pending:
        s = srcs.get(r["source"])
        body.append(headline(r, s, 1).replace("**", ""))
    tr = ["Kind: check"]
    for r in pending:
        tr += [f"Check: {r['check_id']}", f"Checked: {r['started']}", f"Outcome: {r['outcome']}"]
    for u in sorted({q["url"].rsplit("/", 1)[0] + "/" for r in pending for q in r.get("requests", []) if q.get("url")}):
        tr.append(f"Source: {u}")
    tr += [f"Read: {sum(len(r.get('requests') or []) for r in pending)}", f"Added: {a}", f"Changed: {ch}",
           f"Removed: {rm}", f"Not-published: {sum(len(r.get('gap') or []) for r in pending)}",
           f"Unexplained: {sum(r.get('unexplained', 0) for r in pending)}"]
    for r in pending:
        for f in r.get("flags", []):
            tr.append(f"Flag: {f['flag']}")
    return subject + "\n\n" + "\n\n".join(body) + "\n\n" + "\n".join(tr) + "\n"


# ---------------------------------------------------------------- CLI

def show(r: dict, sources: dict):
    a, ch, rm = _counts(r)
    print(f"{r['started']}  {r['source']:<18} {r['outcome']:<13} read {len(r.get('requests') or []):>3}  "
          f"+{a} ~{ch} -{rm}  not published {len(r.get('gap') or [])} (no reason {r.get('unexplained', 0)})  "
          f"{' '.join(f['flag'] for f in r.get('flags', []))}  {r['check_id']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--day")
    ap.add_argument("--act")
    ap.add_argument("--source")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pages", help="write the pages into this directory")
    a = ap.parse_args(argv)
    root = Path(a.root)
    records = load_records(root)
    sources = load_sources(root)
    if a.pages:
        out = Path(a.pages)
        acts = (latest(records).get("e-sbirka") or {}).get("census", {}).get("repo", 0)
        for p, t in build_files(records, [], sources, acts, utcnow()).items():
            if p.startswith("data/"):
                continue
            (out / p).parent.mkdir(parents=True, exist_ok=True)
            (out / p).write_text(t, encoding="utf-8", newline="\n")
        return 0
    rs = records
    if a.day:
        rs = [r for r in rs if r["started"].startswith(a.day)]
    if a.source:
        rs = [r for r in rs if r["source"] == a.source]
    if a.act:
        rs = [r for r in rs if a.act in json.dumps([r["seen"], r["published"], [g["id"] for g in r.get("gap", [])]])]
    if not (a.day or a.source or a.act):
        rs = list(latest(rs).values())
        watched = {r["source"] for r in rs}
        for s in sources:
            if s["id"] not in watched:
                print(f"{'':20}  {s['id']:<18} {s['state']}")
    for r in rs:
        if a.json:
            print(json.dumps(r, ensure_ascii=False, sort_keys=True))
        else:
            show(r, {})
            if a.act:
                for part in ("seen", "published"):
                    for k, v in r[part].items():
                        if a.act in v:
                            print(f"    {part} {k}")
                for g in r.get("gap", []):
                    if g["id"] == a.act:
                        print(f"    not published: {g['reason']} ({g.get('detail', '')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
