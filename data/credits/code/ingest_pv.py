"""Load the promulgated text (VYHLZNE, ".../0000-00-00/") of every act from e-Sbírka's datasets 003 and 004.

    python -X utf8 ingest_pv.py --src C:/Users/alany/law8/czechia/esbirka --db C:/Users/alany/law8/czechia/lanes/credits/db

pv.sqlite:
  pvf (doc, act, path, fid, hier, odl, cit, oznac)   003 records of promulgated versions (path below /dokument/)
  fr  (fid, typ, text)                               004 texts of those fragments
Each stage writes a done marker (pv.003.done, pv.004.done); a rerun skips finished stages.
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in (Path(__file__).resolve().parents[3] / 'tools' / 'build',
                                    Path(__file__).resolve().parents[1] / 'clone' / 'tools' / 'build') if p.exists())))
from esbirka_stream import raw_records  # noqa: E402

ELI = 'esel-esb:eli/cz/'
FID = re.compile(rb'"fragment-id" : (\d+)')


def fast(con):
    for p in ('journal_mode=off', 'synchronous=off', 'temp_store=memory', 'cache_size=-200000'):
        con.execute('pragma ' + p)
    return con


def stage003(src, db):
    if (db / 'pv.003.done').exists():
        return
    con = fast(sqlite3.connect(db / 'pv.sqlite'))
    con.execute('drop table if exists pvf')
    con.execute('create table pvf (doc int, act text, path text, fid int, hier text, odl text, cit text, oznac text)')
    rows, n, kept, t = [], 0, 0, time.time()
    for raw in raw_records(str(src / '003PravniAktZneniFragment.json.gz')):
        n += 1
        if b'/0000-00-00/' not in raw[:400]:
            continue
        r = json.loads(raw)
        iri = r['iri'][len(ELI):]
        act = '/'.join(iri.split('/')[:3])
        path = iri.split('/dokument', 1)[1].lstrip('/') if '/dokument' in iri else ''
        rows.append((r['znění-dokument-id'], act, path, (r.get('právní-akt-fragment') or {}).get('fragment-id'),
                     r.get('znění-fragment-hierarchie'), r.get('znění-fragment-odlišná-účinnost'),
                     r.get('znění-fragment-citace-text'), r.get('znění-fragment-označení-uzlu-text')))
        kept += 1
        if len(rows) >= 200000:
            con.executemany('insert into pvf values (?,?,?,?,?,?,?,?)', rows)
            con.commit()
            rows = []
            print(f'003 {n} read, {kept} kept, {time.time()-t:.0f}s', flush=True)
    con.executemany('insert into pvf values (?,?,?,?,?,?,?,?)', rows)
    con.execute('create index pvf_act on pvf(act)')
    con.execute('create index pvf_fid on pvf(fid)')
    con.commit()
    con.close()
    (db / 'pv.003.done').write_text(json.dumps({'read': n, 'kept': kept}))
    print(f'003 done {n} read, {kept} kept, {time.time()-t:.0f}s', flush=True)


def stage004(src, db):
    if (db / 'pv.004.done').exists():
        return
    con = fast(sqlite3.connect(db / 'pv.sqlite'))
    want = {r[0] for r in con.execute('select fid from pvf where fid is not null')}
    con.execute('drop table if exists fr')
    con.execute('create table fr (fid integer primary key, typ text, text text)')
    rows, n, kept, t = [], 0, 0, time.time()
    for raw in raw_records(str(src / '004PravniAktFragment.json.gz')):
        n += 1
        m = FID.search(raw, 0, 400)
        if not m or int(m.group(1)) not in want:
            continue
        r = json.loads(raw)
        rows.append((r['fragment-id'], r.get('cis-esb-typ-fragmentu-položka'), r.get('fragment-text')))
        kept += 1
        if len(rows) >= 200000:
            con.executemany('insert or replace into fr values (?,?,?)', rows)
            con.commit()
            rows = []
            print(f'004 {n} read, {kept} kept, {time.time()-t:.0f}s', flush=True)
    con.executemany('insert or replace into fr values (?,?,?)', rows)
    con.commit()
    con.close()
    (db / 'pv.004.done').write_text(json.dumps({'read': n, 'kept': kept, 'wanted': len(want)}))
    print(f'004 done {n} read, {kept} kept of {len(want)}, {time.time()-t:.0f}s', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--db', required=True)
    a = ap.parse_args()
    src, db = Path(a.src), Path(a.db)
    stage003(src, db)
    stage004(src, db)
    print('ingest_pv done', flush=True)


if __name__ == '__main__':
    main()
