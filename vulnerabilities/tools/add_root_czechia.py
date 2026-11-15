"""global-law replays czechia-law only up to its pinned commit (d3d91966f, 2026-11-12), so the history detectors would
miss everything appended since. This replaces Czechia's rows in index/root.parquet with the same rows global-law's replay
gives (law = the commit's author, the act that made the change; In-force; kind), from czechia-law's own history at the pin.
Commits without a Kind: trailer, and items published only as promulgated, are law; drafts, case law, records,
corrections and documentation keep their own kind, so the history detectors (which read kind = 'law') leave them out."""
import json, os, subprocess
import duckdb, pyarrow as pa

HERE = os.path.dirname(os.path.abspath(__file__))
pin = json.load(open(os.path.join(HERE, "pins.json"), encoding="utf-8"))["corpora"][0]
out = subprocess.run(["git", "log", "--format=%H%x1f%an", pin["sha"]], cwd=os.path.join(HERE, "sources", "corpus", "czechia-law.git"),
                     capture_output=True, check=True).stdout.decode("utf-8")
authors = pa.table({"commit": [l.split("\x1f")[0] for l in out.splitlines()], "author": [l.split("\x1f")[1] for l in out.splitlines()]})
con = duckdb.connect()
con.register("authors", authors)
con.sql(r"""
create table s as
select c.commit as root, 'czechia/national/acts' as corpus, c.commit as corpus_commit, a.author as law,
       regexp_extract(json_extract_string(c.trailers, '$."In-force"[0]'), '\d{4}-\d{2}-\d{2}') as in_force,
       case when json_extract_string(c.trailers, '$.Kind[0]') is null
              or json_extract_string(c.trailers, '$.Kind[0]') = 'as-promulgated' then 'law'
            else json_extract_string(c.trailers, '$.Kind[0]') end as kind,
       'Czechia: ' || c.subject as subject
from 'index/commits/czechia-law.parquet' c join authors a using (commit)
where json_extract_string(c.trailers, '$."In-force"[0]') is not null""")
print(con.sql("select kind, count(*) from s group by 1 order by 2 desc").fetchall())
con.sql("""copy (select * from 'index/root.parquet' where corpus <> 'czechia/national/acts' union all select * from s)
           to 'index/root.new.parquet' (format parquet, compression zstd)""")
con.close()
os.replace(os.path.join(HERE, "index", "root.new.parquet"), os.path.join(HERE, "index", "root.parquet"))
print("root.parquet: Czechia rows replaced")
