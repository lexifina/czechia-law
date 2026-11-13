"""Load e-Sbírka's datasets into the SQLite store that tools/build/build.py and check_repo.py read, straight from the
.json.gz files (no decompressed copies on disk), in parallel.

    python -I -X utf8 ingest_gz.py --raw DIR_WITH_JSON_GZ --data OUT_DIR [--workers 12]

Writes OUT_DIR/db/meta.sqlite, vf_0.sqlite and fr.sqlite with the tables and columns of tools/build/ingest.py, and the
same values in every column build.py and check_repo.py read. To keep the store small (it is rebuilt for every new
snapshot), vf keeps only the columns those scripts read (doc, h, fid, iri, odlisna; the others are NULL, and iri is kept
from "/dokument" on, which version_rows splits on), and fr only the fragments that the versions in scope use.
The record parsing is ingest.py's, line for line; only the reading (gzip stream instead of byte ranges) differs.
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

HERE = Path(__file__).resolve().parent
ELI = "esel-esb:eli/cz/"
FRAGLIST = re.compile(rb'"pr\xc3\xa1vn\xc3\xad-akt-zn\xc4\x9bn\xc3\xad-fragment" : \[(?: \]|.*?\n  \} \])', re.S)
EXTRA_ACTS = ("sb/1993/2",)
FILES = {
    "001": "001PravniAktZneni.json.gz", "002": "002PravniAkt.json.gz", "003": "003PravniAktZneniFragment.json.gz",
    "004": "004PravniAktFragment.json.gz", "006": "006PravniAktMetadata.json.gz", "007": "007PravniAktKonsolidacniVazba.json.gz",
}


def stream_mod(build_dir: str):
    sys.path.insert(0, build_dir)
    import esbirka_stream  # noqa: E402
    return esbirka_stream


def fast(con):
    con.execute("pragma journal_mode=off")
    con.execute("pragma synchronous=off")
    con.execute("pragma temp_store=memory")
    con.execute("pragma cache_size=-200000")
    return con


def sc(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v


def act_of(iri: str) -> str:
    return "/".join(iri[len(ELI):].split("/")[:3])


# ---------------------------------------------------------------- workers (each gets a list of raw records)

_W: dict = {}


def _winit(docs_file: str) -> None:
    if docs_file:
        _W["docs"] = set(json.loads(Path(docs_file).read_text()))


def w_versions(recs):
    out = []
    for raw in recs:
        r = json.loads(FRAGLIST.sub(b'"x" : []', raw, count=1))
        iri = r["iri"]
        out.append((iri[len(ELI):], act_of(r["akt-iri"] + "/x") if r.get("akt-iri") else act_of(iri), r["znění-dokument-id"],
                    r.get("znění-base-id"), r.get("znění-datum-účinnosti-od"), r.get("znění-datum-účinnosti-do"),
                    r.get("cis-esb-typ-znění-položka"), int(bool(r.get("znění-je-zrušen"))),
                    int(bool(r.get("znění-nikdy-nebyl-účinný"))), r.get("cis-esb-stav-vyhlášení-aktu-položka"),
                    r.get("znění-datum-čas-poslední-změny"), (r.get("znění-částka") or {}).get("částka-datum-čas-vyhlášení")))
    return out


def w_links(recs):
    out = []
    for raw in recs:
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


MARKER = b'"zn\xc4\x9bn\xc3\xad-dokument-id" : '


def w_vf(recs):
    docs = _W["docs"]
    rows = []
    for raw in recs:
        i = raw.find(MARKER)
        if i >= 0:
            j = raw.find(b",", i)
            try:
                if int(raw[i + len(MARKER):j]) not in docs:
                    continue
            except ValueError:
                pass
        r = json.loads(raw)
        if r["znění-dokument-id"] not in docs:
            continue
        iri = r["iri"][len(ELI):]
        k = iri.find("/dokument")
        rows.append((r["znění-dokument-id"], r.get("znění-fragment-hierarchie"), (r.get("právní-akt-fragment") or {}).get("fragment-id"),
                     iri[k:] if k >= 0 else "", None, None, None,
                     json.dumps(r.get("znění-fragment-odlišná-účinnost"), ensure_ascii=False) if r.get("znění-fragment-odlišná-účinnost") else None,
                     None, None, None))
    return rows


def w_fr(recs):
    out = []
    for raw in recs:
        r = json.loads(raw)
        out.append((r["fragment-id"], r.get("cis-esb-typ-fragmentu-položka"), r.get("fragment-text"), r.get("fragment-base-id")))
    return out


def batches(es, path: str, n: int = 4000):
    b = []
    for raw in es.raw_records(path):
        b.append(raw)
        if len(b) >= n:
            yield b
            b = []
    if b:
        yield b


def pmap(pool, fn, it, inflight: int):
    """Ordered map with at most `inflight` batches queued (memory stays bounded)."""
    q = []
    for x in it:
        q.append(pool.submit(fn, x))
        if len(q) >= inflight:
            yield q.pop(0).result()
    for f in q:
        yield f.result()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--build-dir", default=str(HERE.parent.parent / "repo" / "tools" / "build"))
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    es = stream_mod(a.build_dir)
    raw = Path(a.raw)
    db = Path(a.data) / "db"
    db.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def say(m):
        print(f"{time.strftime('%H:%M:%S')} {m} ({time.time() - t0:.0f}s)", flush=True)

    # meta
    if not (db / "meta.done").exists():
        (db / "meta.sqlite").unlink(missing_ok=True)
        con = fast(sqlite3.connect(db / "meta.sqlite"))
        con.executescript("""
        create table acts (act text primary key, coll text, year int, num text, citation text, title text, code text,
            first_version text, last_version text, podtyp text, druh text, typ text, approved text, in_force_from text,
            in_force_to text, valid_to text, repealed text, effect_text text, repeal_text text, short_title text, meta text);
        create table versions (v text, act text, doc int, base int, od text, do text, typ text, zrusen int,
            nikdy int, stav text, changed text, published text);
        create table links (id int primary key, doc int, cil text, nact text, ndoc int, nfrag text, zdroj text, od text,
            instr text, od_text text, konflikt text);
        """)
        for raw_r in es.raw_records(str(raw / FILES["002"])):
            r = json.loads(raw_r)
            act = r["iri"][len(ELI):]
            con.execute("insert or replace into acts (act, coll, year, num, citation, title, code, first_version, last_version) values (?,?,?,?,?,?,?,?,?)",
                        (act, r.get("akt-sbírka-kód"), r.get("akt-rok-předpisu"), r.get("akt-číslo-předpisu"), r.get("akt-citace"),
                         r.get("akt-název-vyhlášený"), r.get("akt-kód"), (r.get("právní-akt-znění-první") or {}).get("iri", "")[len(ELI):],
                         (r.get("právní-akt-znění-poslední") or {}).get("iri", "")[len(ELI):]))
        for raw_r in es.raw_records(str(raw / FILES["006"])):
            r = json.loads(raw_r)
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
        say(f"acts {con.execute('select count(*) from acts').fetchone()[0]}")
        with ProcessPoolExecutor(a.workers) as pool:
            for key, fn, table, n in (("001", w_versions, "versions", 12), ("007", w_links, "links", 11)):
                for rows in pmap(pool, fn, batches(es, str(raw / FILES[key]), 2000), a.workers * 3):
                    con.executemany(f"insert into {table} values ({','.join('?' * n)})", rows)
                con.commit()
                say(f"{table} {con.execute(f'select count(*) from {table}').fetchone()[0]}")
        con.executescript("create index versions_act on versions(act); create index versions_v on versions(v); create index versions_doc on versions(doc); create index links_doc on links(doc); create index links_nact on links(nact);")
        con.close()
        (db / "meta.done").write_text("ok")

    # vf: version fragments of the versions in scope (ingest.scope_docs, plus the Charter)
    if not (db / "vf.done").exists():
        con = sqlite3.connect(db / "meta.sqlite")
        docs = [r[0] for r in con.execute("""select v.doc from versions v join acts a on a.act=v.act
                          where ((a.coll='sb' and a.typ='PRAVPRED') or a.act in (%s)) and v.typ='KONSOL' and v.stav='PUBLIKOV'
                          order by v.doc""" % ",".join("?" * len(EXTRA_ACTS)), EXTRA_ACTS)]
        con.close()
        df = db / "scope_docs.json"
        df.write_text(json.dumps(docs))
        for p in db.glob("vf_*.sqlite"):
            p.unlink()
        out = fast(sqlite3.connect(db / "vf_0.sqlite"))
        out.execute("create table vf (doc int, h text, fid int, iri text, parent text, cit text, oznac text, odlisna text, vod text, vdo text, vfid int)")
        fids = bytearray(1 << 20)
        kept = 0
        with ProcessPoolExecutor(a.workers, initializer=_winit, initargs=(str(df),)) as pool:
            for rows in pmap(pool, w_vf, batches(es, str(raw / FILES["003"]), 4000), a.workers * 3):
                out.executemany("insert into vf values (?,?,?,?,?,?,?,?,?,?,?)", rows)
                kept += len(rows)
                for r in rows:
                    f = r[2]
                    if f is not None:
                        if (f >> 3) >= len(fids):
                            fids.extend(bytearray(max(len(fids), (f >> 3) + 1 - len(fids))))
                        fids[f >> 3] |= 1 << (f & 7)
        out.execute("create index vf_doc on vf(doc)")
        out.commit()
        out.close()
        (db / "fids.bin").write_bytes(bytes(fids))
        say(f"vf {kept} rows for {len(docs)} versions")
        (db / "vf.done").write_text(json.dumps({"kept": kept, "versions": len(docs)}))

    # fr: texts of the fragments those versions use
    if not (db / "fr.done").exists():
        fids = (db / "fids.bin").read_bytes()
        (db / "fr.sqlite").unlink(missing_ok=True)
        out = fast(sqlite3.connect(db / "fr.sqlite"))
        out.execute("create table fr (fid integer primary key, typ text, text text, base int)")
        n = kept = 0
        with ProcessPoolExecutor(a.workers) as pool:
            for rows in pmap(pool, w_fr, batches(es, str(raw / FILES["004"]), 4000), a.workers * 3):
                n += len(rows)
                sel = [r for r in rows if (r[0] >> 3) < len(fids) and fids[r[0] >> 3] & (1 << (r[0] & 7))]
                kept += len(sel)
                out.executemany("insert or replace into fr values (?,?,?,?)", sel)
        out.commit()
        out.close()
        say(f"fr {kept} of {n} fragments")
        (db / "fr.done").write_text(json.dumps({"records": n, "kept": kept}))
        (db / "fids.bin").unlink(missing_ok=True)
    say("ingest done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
