"""Rebuild visualisations/ceske-pravo-ve-20-grafech.html from this repository.

    python visualisations/src/make.py [--repo PATH] [--ref REF]

Steps (all read-only on the repository; scratch output goes to visualisations/src/.build/):
  1. git log of REF with author dates and full messages        -> .build/commits.json
  2. git log --name-status: the files each commit adds/changes  -> .build/paths.json
  3. git archive of navrhy/data/ and data/                      -> .build/repo/
  4. prep.py turns those into .build/data.json; build.py fills page.tpl.html with it.
Works in a blobless or --no-checkout clone, because everything is read from git objects.
"""
import argparse, io, json, os, re, subprocess, sys, tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--repo', default=os.path.abspath(os.path.join(HERE, '..', '..')))
ap.add_argument('--ref', default=None, help='default: origin/main if present, else HEAD')
ap.add_argument('--out', default=os.path.join(HERE, '..', 'ceske-pravo-ve-20-grafech.html'))
a = ap.parse_args()
B = os.path.join(HERE, '.build')
os.makedirs(B, exist_ok=True)


def git(*args):
    return subprocess.run(['git', '-C', a.repo, *args], check=True, capture_output=True).stdout


ref = a.ref
if not ref:
    ref = 'origin/main' if subprocess.run(['git', '-C', a.repo, 'rev-parse', '--verify', '-q', 'origin/main'], capture_output=True).returncode == 0 else 'HEAD'
sha = git('rev-parse', ref).decode().strip()
print('ref', ref, sha)

# 1. commits with trailers
rows, cur = [], None
for line in git('log', ref, '--format=@@C %H|%ad|%cd|%an%n%B', '--date=iso-strict').decode('utf-8', 'replace').split('\n'):
    if line.startswith('@@C '):
        if cur: rows.append(cur)
        h, ad, cd, an = line[4:].split('|', 3)
        cur = {'h': h, 'ad': ad, 'cd': cd, 'an': an, 'subj': None, 'body': [], 't': {}}
        continue
    if cur is None: continue
    if cur['subj'] is None:
        cur['subj'] = line; continue
    m = re.match(r'^([A-Z][A-Za-z-]+): (.*)$', line)
    if m: cur['t'].setdefault(m.group(1), []).append(m.group(2))
    else: cur['body'].append(line)
if cur: rows.append(cur)
for r in rows: r['body'] = '\n'.join(r['body']).strip()[:600]
json.dump(rows, open(os.path.join(B, 'commits.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('commits', len(rows))

# 2. files per commit, with their status (A, M, D)
out, cur = {}, None
for l in git('log', ref, '--format=@@C %H', '--name-status', '--no-renames').decode('utf-8', 'replace').split('\n'):
    if l.startswith('@@C '): cur = l[4:]; out[cur] = []; continue
    if l and cur: out[cur].append(l)
json.dump(out, open(os.path.join(B, 'paths.json'), 'w', encoding='utf-8'), ensure_ascii=False)

# 3. data tables
with tarfile.open(fileobj=io.BytesIO(git('archive', ref, 'navrhy/data', 'data'))) as tf:
    tf.extractall(os.path.join(B, 'repo'), filter='data')

# 4. prep + build
env = dict(os.environ, HEAD_SHA=sha)
subprocess.run([sys.executable, '-X', 'utf8', os.path.join(HERE, 'prep.py'), B], check=True, env=env)
subprocess.run([sys.executable, '-X', 'utf8', os.path.join(HERE, 'build.py'), os.path.join(B, 'data.json'), os.path.abspath(a.out)], check=True)
