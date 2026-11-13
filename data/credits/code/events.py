"""List every change the repository credits to e-Sbírka ("bez odkazu na novelu"), from the git history.

    python -X utf8 events.py --repo CLONE --out events.jsonl

One row per changed act per publisher commit (the build's `by_publisher` count): commit, branches, path, act, in-force
day, the provisions changed (the commit message's unit labels; where the message cut them at 40, completed from the
diff), the commit's Candidate: trailers, and the lines the commit removed and added in that file.
"""
import argparse
import json
import re
import subprocess
from collections import defaultdict

LINE = re.compile(r'^(?P<cit>\S+ (?:Sb\.|Ú\. l\.)) \((?P<rest>.*)\. (?P<url>https://www\.e-sbirka\.cz/eli/cz/(?P<act>[a-z]+/\d+/[0-9a-z]+)/(?P<day>\d{4}-\d\d-\d\d))$')


def git(repo, *a):
    return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, encoding='utf-8', check=True).stdout


def provisions_from_diff(old, new):
    """Unit labels of the changed lines: the enclosing ### provision and, inside it, the (n) paragraph."""
    def label_lines(text):
        out, prov, para = [], None, None
        for l in text.split('\n'):
            if l.startswith('### '):
                prov, para = l[4:].strip(), None
            elif l.startswith('## '):
                prov, para = None, None
            else:
                m = re.match(r'^\((\d+[a-z]*)\) ', l)
                if m and prov:
                    para = m.group(1)
            out.append((l, prov, para))
        return out
    import difflib
    a, b = label_lines(old), label_lines(new)
    sm = difflib.SequenceMatcher(None, [x[0] for x in a], [x[0] for x in b], autojunk=False)
    units = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        for _, prov, para in a[i1:i2] + b[j1:j2]:
            if prov:
                lab = prov.replace('Čl.', 'čl.') + (f' odst. {para}' if para else '')
                if lab not in units:
                    units.append(lab)
    return units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = git(a.repo, 'log', 'main', 'future', '--author=^e-Sbírka <', '--grep=^e-Sbírka (bez odkazu na novelu)',
              '--format=@@%H%x1f%P%x1f%B')
    on_main = set(git(a.repo, 'rev-list', 'main').split())
    rows = []
    for rec in out.split('@@')[1:]:
        sha, parent, body = rec.split('\x1f', 2)
        parent = parent.split()[0]
        lines = body.splitlines()
        if not lines or 'bez odkazu na novelu' not in lines[0]:
            continue
        trailers = [l for l in lines if re.match(r'^[A-Za-z-]+: ', l)]
        inforce = next(l.split(': ', 1)[1] for l in trailers if l.startswith('In-force: '))
        cands = [l.split(': ', 1)[1] for l in trailers if l.startswith('Candidate: ')]
        for l in lines[1:]:
            m = LINE.match(l)
            if not m or 'first version, as in force' in l or l.endswith('File removed.'):
                continue
            rest = m.group('rest')
            i = rest.rfind('): ')
            units_s = rest[i + 3:]
            trunc = units_s.endswith(' ...')
            if trunc:
                units_s = units_s[:-4]
            units = [u.strip() for u in units_s.split(', ') if u.strip()]
            act = m.group('act')
            path = act + '.md'
            rows.append({'commit': sha, 'parent': parent, 'branch': 'main' if sha in on_main else 'future',
                         'path': path, 'act': act, 'citation': m.group('cit'), 'day': m.group('day'),
                         'in_force': inforce, 'units': units, 'units_truncated': trunc, 'version': m.group('url'),
                         'commit_candidates': cands})
    # The lines each commit removed and added in the act's file.
    cat = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=a.repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def show(spec):
        cat.stdin.write(spec.encode('utf-8') + b'\n')
        cat.stdin.flush()
        head = cat.stdout.readline().split()
        if len(head) < 3 or head[1] == b'missing':
            return ''
        data = cat.stdout.read(int(head[2]))
        cat.stdout.read(1)
        return data.decode('utf-8')
    for r in rows:
        old = show(f"{r['parent']}:{r['path']}")
        new = show(f"{r['commit']}:{r['path']}")
        ol, nl = old.split('\n'), new.split('\n')
        so, sn = set(ol), set(nl)
        r['removed'] = [l for l in ol if l not in sn and l.strip()]
        r['added'] = [l for l in nl if l not in so and l.strip()]
        if r['units_truncated']:
            extra = provisions_from_diff(old, new)
            r['units_from_diff'] = extra
            r['units'] = r['units'] + [u for u in extra if u not in r['units']]
    rows.sort(key=lambda r: (r['day'], r['path'], r['commit']))
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    by = defaultdict(int)
    for r in rows:
        by[r['branch']] += 1
    print(len(rows), dict(by), sum(r['units_truncated'] for r in rows), 'truncated')


if __name__ == '__main__':
    main()
