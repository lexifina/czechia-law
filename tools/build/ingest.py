"""Load e-Sbírka's bulk datasets into SQLite, once, in parallel.

    python -I -X utf8 ingest.py --data C:/Users/alany/Documents/czechia-law-data [--workers 8] [--stage meta|vf|fr|all]

Input: DATA/json/<NNN>.json, the datasets decompressed once (`zcat raw/X.json.gz > json/X.json`), so workers can
each parse a byte range (esbirka_stream.slices). Output: DATA/db/
  meta.sqlite   acts (002 + 006), versions (001, without their fragment lists), links (007)
  vf_<k>.sqlite version fragments (003) of the versions in scope, one shard per worker, indexed by version
  fr_<k>.sqlite fragment texts (004), one shard per worker, keyed by fragment id
Each stage writes a done marker, so a rerun skips finished work.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from esbirka_stream import range_records, slices  # noqa: E402

FILES = {
    "001": "001PravniAktZneni.json", "002": "002PravniAkt.json", "003": "003PravniAktZneniFragment.json",
    "004": "004PravniAktFragment.json", "006": "006PravniAktMetadata.json", "007": "007PravniAktKonsolidacniVazba.json",
}
ELI = "esel-esb:eli/cz/"
FRAGLIST = re.compile(rb'"pr\xc3\xa1vn\xc3\xad-akt-zn\xc4\x9bn\xc3\xad-fragment" : \[(?: \]|.*?\n  \} \])', re.S)


def fast(con: sqlite3.Connection) -> sqlite3.Connection:
    con.execute("pragma journal_mode=off")
    con.execute("pragma synchronous=off")
    con.execute("pragma temp_store=memory")
    con.execute("pragma cache_size=-200000")
    return con


def sc(v):
    """A scalar for SQLite: objects and lists as JSON."""
    return json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v


def act_of(iri: str) -> str:
    """esel-esb:eli/cz/sb/1993/1/2013-06-01/dokument/... -> sb/1993/1"""
    return "/".join(iri[len(ELI):].split("/")[:3])


# ---------------------------------------------------------------- meta: 001, 002, 006, 007

def _versions(args):
    path, a, b = args
    out = []
    for raw in range_records(path, a, b):
        r = json.loads(FRAGLIST.sub(b'"x" : []', raw, count=1))
        iri = r["iri"]
        out.append((iri[len(ELI):], act_of(r["akt-iri"] + "/x") if r.get("akt-iri") else act_of(iri), r["znění-dokument-id"],
                    r.get("znění-base-id"), r.get("znění-datum-účinnosti-od"), r.get("znění-datum-účinnosti-do"),
                    r.get("cis-esb-typ-znění-položka"), int(bool(r.get("znění-je-zrušen"))),
                    int(bool(r.get("znění-nikdy-nebyl-účinný"))), r.get("cis-esb-stav-vyhlášení-aktu-položka"),
                    r.get("znění-datum-čas-poslední-změny"), (r.get("znění-částka") or {}).get("částka-datum-čas-vyhlášení")))
    return out


def _links(args):
    path, a, b = args
    out = []
    for raw in range_records(path, a, b):
        r = json.loads(raw)
        cil = (r.get("znění-fragment-cíl") or {})
        nov = (r.get("znění-fragment-novela") or {})
        zdr = (r.get("znění-fragment-zdroj") or {})
        out.append((r["vazba-konsolidační-id"], cil.get("znění-dokument-id"), cil.get("iri", "")[len(ELI):] or None,
                    act_of(nov["iri"]) if nov.get("iri") else None, nov.get("znění-dokument-id"),
                    nov.get("iri", "")[len(ELI):] or None, zdr.get("iri", "")[len(ELI):] or None,
                    r.get("vazba-konsolidační-účinnost-od"), r.get("cis-esb-typ-novelizační-instrukce-položka"),
                    sc(r.get("vazba-konsolidační-účinnost-textem")), json.dumps(r.get("vazba-konsolidační-konflikt"), ensure_ascii=False) if r.get("vazba-konsolidační-konflikt") else None))
    return out


def stage_meta(data: Path, pool: ProcessPoolExecutor, workers: int) -> None:
    db = data / "db" / "meta.sqlite"
    if (data / "db" / "meta.done").exists():
        return
    if db.exists():
        db.unlink()
    con = fast(sqlite3.connect(db))
    con.executescript("""
    create table acts (act text primary key, coll text, year int, num text, citation text, title text, code text,
        first_version text, last_version text, podtyp text, druh text, typ text, approved text, in_force_from text,
        in_force_to text, valid_to text, repealed text, effect_text text, repeal_text text, short_title text, meta text);
    create table versions (v text, act text, doc int, base int, od text, do text, typ text, zrusen int,
        nikdy int, stav text, changed text, published text);
    create table links (id int primary key, doc int, cil text, nact text, ndoc int, nfrag text, zdroj text, od text,
        instr text, od_text text, konflikt text);
    """)
    t = time.time()
    # 002 + 006: small, one process.
    from esbirka_stream import range_records as rr
    p2 = str(data / "json" / FILES["002"])
    for a, b in slices(p2, 1):
        for raw in rr(p2, a, b):
            r = json.loads(raw)
            act = r["iri"][len(ELI):]
            con.execute("insert or replace into acts (act, coll, year, num, citation, title, code, first_version, last_version) values (?,?,?,?,?,?,?,?,?)",
                        (act, r.get("akt-sbírka-kód"), r.get("akt-rok-předpisu"), r.get("akt-číslo-předpisu"), r.get("akt-citace"),
                         r.get("akt-název-vyhlášený"), r.get("akt-kód"), (r.get("právní-akt-znění-první") or {}).get("iri", "")[len(ELI):],
                         (r.get("právní-akt-znění-poslední") or {}).get("iri", "")[len(ELI):]))
    p6 = str(data / "json" / FILES["006"])
    for a, b in slices(p6, 1):
        for raw in rr(p6, a, b):
            r = json.loads(raw)
            act = r["akt-iri"][len(ELI):]
            con.execute("""update acts set podtyp=?, druh=?, typ=?, approved=?, in_force_from=?, in_force_to=?, valid_to=?,
                           repealed=?, effect_text=?, repeal_text=?, short_title=?, meta=? where act=?""",
                        (r.get("cis-esb-podtyp-právní-akt-položka"), r.get("cis-esb-druh-aktu-položka"), r.get("cis-esb-typ-právní-akt-položka"),
                         r.get("metadata-datum-schválení"), r.get("metadata-datum-účinnosti-od"), r.get("metadata-datum-účinnosti-do"),
                         r.get("metadata-datum-platnosti-do"), r.get("metadata-datum-zrušení"), sc(r.get("metadata-účinnost-textem")),
                         sc(r.get("metadata-zrušení-textem")), sc(r.get("metadata-název-zkrácený")),
                         json.dumps({k: v for k, v in r.items() if k in ("metadata-pozastavení-provádění", "metadata-další-název", "cis-esb-územní-platnost-položka")}, ensure_ascii=False, sort_keys=True),
                         act))
    con.commit()
    print(f"acts {con.execute('select count(*) from acts').fetchone()[0]} {time.time()-t:.1f}s", flush=True)
    for key, fn, table, n in (("001", _versions, "versions", 12), ("007", _links, "links", 11)):
        t = time.time()
        p = str(data / "json" / FILES[key])
        jobs = [(p, a, b) for a, b in slices(p, workers * 2)]
        for rows in pool.map(fn, jobs):
            con.executemany(f"insert into {table} values ({','.join('?' * n)})", rows)
        con.commit()
        print(f"{table} {con.execute(f'select count(*) from {table}').fetchone()[0]} {time.time()-t:.1f}s", flush=True)
    con.executescript("create index versions_act on versions(act); create index versions_v on versions(v); create index versions_doc on versions(doc); create index links_doc on links(doc); create index links_nact on links(nact);")
    con.close()
    (data / "db" / "meta.done").write_text("ok")


# ---------------------------------------------------------------- vf: 003, fr: 004

def _vf(args):
    path, a, b, out, docs_file = args
    docs = set(json.loads(Path(docs_file).read_text()))
    if os.path.exists(out):
        os.unlink(out)
    con = fast(sqlite3.connect(out))
    con.execute("create table vf (doc int, h text, fid int, iri text, parent text, cit text, oznac text, odlisna text, vod text, vdo text, vfid int)")
    rows = []
    n = kept = 0
    marker = b'"zn\xc4\x9bn\xc3\xad-dokument-id" : '
    for raw in range_records(path, a, b):
        n += 1
        # Cheap pre-filter on the version id before parsing.
        i = raw.find(marker)
        if i >= 0:
            j = raw.find(b",", i)
            try:
                if int(raw[i + len(marker):j]) not in docs:
                    continue
            except ValueError:
                pass
        r = json.loads(raw)
        if r["znění-dokument-id"] not in docs:
            continue
        kept += 1
        par = r.get("znění-fragment-předek")
        rows.append((r["znění-dokument-id"], r.get("znění-fragment-hierarchie"), (r.get("právní-akt-fragment") or {}).get("fragment-id"),
                     r["iri"][len(ELI):], par["iri"][len(ELI):] if par else None, r.get("znění-fragment-citace-text"),
                     r.get("znění-fragment-označení-uzlu-text"),
                     json.dumps(r.get("znění-fragment-odlišná-účinnost"), ensure_ascii=False) if r.get("znění-fragment-odlišná-účinnost") else None,
                     r.get("znění-fragment-vybrané-od"), r.get("znění-fragment-vybrané-do"), r.get("znění-fragment-id")))
        if len(rows) >= 200000:
            con.executemany("insert into vf values (?,?,?,?,?,?,?,?,?,?,?)", rows)
            rows = []
    con.executemany("insert into vf values (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("create index vf_doc on vf(doc)")
    con.commit()
    con.close()
    return n, kept


def _fr(args):
    path, a, b, out = args
    if os.path.exists(out):
        os.unlink(out)
    con = fast(sqlite3.connect(out))
    con.execute("create table fr (fid integer primary key, typ text, text text, base int)")
    rows = []
    n = 0
    for raw in range_records(path, a, b):
        r = json.loads(raw)
        n += 1
        rows.append((r["fragment-id"], r.get("cis-esb-typ-fragmentu-položka"), r.get("fragment-text"), r.get("fragment-base-id")))
        if len(rows) >= 200000:
            con.executemany("insert or replace into fr values (?,?,?,?)", rows)
            rows = []
    con.executemany("insert or replace into fr values (?,?,?,?)", rows)
    con.commit()
    con.close()
    return n


def scope_docs(data: Path) -> list:
    """Versions to load: every published consolidated version (KONSOL, PUBLIKOV) of every act in the Sbírka zákonů
    that is legislation (PRAVPRED)."""
    con = sqlite3.connect(data / "db" / "meta.sqlite")
    rows = con.execute("""select v.doc from versions v join acts a on a.act=v.act
                          where a.coll='sb' and a.typ='PRAVPRED' and v.typ='KONSOL' and v.stav='PUBLIKOV' order by v.doc""").fetchall()
    return [r[0] for r in rows]


def stage_vf(data: Path, pool: ProcessPoolExecutor, workers: int) -> None:
    if (data / "db" / "vf.done").exists():
        return
    docs = scope_docs(data)
    df = data / "db" / "scope_docs.json"
    df.write_text(json.dumps(docs))
    p = str(data / "json" / FILES["003"])
    t = time.time()
    jobs = [(p, a, b, str(data / "db" / f"vf_{k}.sqlite"), str(df)) for k, (a, b) in enumerate(slices(p, workers))]
    tot = kept = 0
    for n, k in pool.map(_vf, jobs):
        tot += n
        kept += k
    print(f"vf {tot} records, {kept} kept for {len(docs)} versions, {len(jobs)} shards, {time.time()-t:.1f}s", flush=True)
    (data / "db" / "vf.done").write_text(json.dumps({"shards": len(jobs), "records": tot, "kept": kept}))


def stage_fr(data: Path, pool: ProcessPoolExecutor, workers: int) -> None:
    if (data / "db" / "fr.done").exists():
        return
    p = str(data / "json" / FILES["004"])
    t = time.time()
    jobs = [(p, a, b, str(data / "db" / f"fr_{k}.sqlite")) for k, (a, b) in enumerate(slices(p, workers))]
    tot = sum(pool.map(_fr, jobs))
    print(f"fr {tot} fragments, {len(jobs)} shards, {time.time()-t:.1f}s", flush=True)
    (data / "db" / "fr.done").write_text(json.dumps({"shards": len(jobs), "records": tot}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--stage", default="all")
    a = ap.parse_args()
    data = Path(a.data)
    (data / "db").mkdir(exist_ok=True)
    with ProcessPoolExecutor(a.workers) as pool:
        if a.stage in ("meta", "all"):
            stage_meta(data, pool, a.workers)
        if a.stage in ("fr", "all"):
            stage_fr(data, pool, a.workers)
        if a.stage in ("vf", "all"):
            stage_vf(data, pool, a.workers)
    print("ingest done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
