"""Functional smoke test of the built Czech law repository: the things a reader does with it work. Standard library only.

    python -X utf8 scripts/czechia-law/test_repo.py [--repo ../czechia-law] [--record]
    python -X utf8 tools/test_repo.py                   # from inside the repository

It asserts that:
1. `git blame` on the Constitution names amending acts as authors of its lines, Ústavní zákon č. 71/2012 Sb. among them;
2. tools/czlaw.py gives the text before and after known amendments, and each equals the file at that version's tag
   (and at the commit before it);
3. `git log --follow` on a file lists its changes in the order they took effect, by acts;
4. every tag resolves to a commit; every commit but the documentation commit has an ISO `In-force:` trailer, and
   every trailer key is ASCII (git parses the trailer block);
5. no commit is authored by Lexifina except the documentation commit (main's head), and the committer is always Lexifina;
6. `main` holds nothing in force after the documentation day, and `future` nothing before it;
7. every git or tool command in the README's table runs and prints something.
With --record the result is written to verification.json next to this script (for REPRODUCE.md).
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAW = re.compile(r'^\S.* č\. [0-9a-z]+/\d{4} (Sb\.|Ú\. l\.)$')
PUBLISHER = 'e-Sbírka'


def default_repo() -> Path:
    if (HERE.parent / '.git').exists():
        return HERE.parent
    return HERE.parents[2] / 'czechia-law'


class Smoke:
    def __init__(self, repo: Path):
        self.repo = repo
        self.results = []

    def git(self, *args: str) -> str:
        out = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
        if out.returncode:
            raise AssertionError(f'git {" ".join(args)}: {out.stderr.strip()}')
        return out.stdout

    def tool(self, *args: str) -> str:
        out = subprocess.run([sys.executable, '-X', 'utf8', 'tools/czlaw.py', *args], cwd=self.repo, capture_output=True,
                             text=True, encoding='utf-8')
        if out.returncode:
            raise AssertionError(f'czlaw {" ".join(args)}: {out.stderr.strip()}')
        return out.stdout

    def check(self, name, fn):
        try:
            detail = fn() or ''
            self.results.append((name, True, detail))
            print(f'PASS {name}: {detail}')
        except AssertionError as exc:
            self.results.append((name, False, str(exc)))
            print(f'FAIL {name}: {exc}')

    def blame(self):
        out = self.git('blame', '--line-porcelain', 'main', '--', 'sb/1993/1.md')
        authors = {l[7:] for l in out.splitlines() if l.startswith('author ')}
        assert all(LAW.match(a) or a == PUBLISHER for a in authors), f'unexpected authors {authors}'
        assert 'Ústavní zákon č. 71/2012 Sb.' in authors, f'71/2012 not among {authors}'
        assert len(authors) >= 5, f'only {authors}'
        return f'sb/1993/1.md lines by {len(authors)} acts'

    def on_date(self):
        done = []
        for path, tag, before, after in [('sb/1993/1.md', 'sb/1993/1/2013-03-08', '2013-03-07', '2013-03-08'),
                                         ('sb/1993/1.md', 'sb/1993/1/2012-10-01', '2012-09-30', '2012-10-01'),
                                         ('sb/1993/2.md', 'sb/1993/2/2021-10-01', '2021-09-30', '2021-10-01')]:
            a, b = self.tool('on', before, path), self.tool(after, path)
            assert a and b and a != b, f'{path}: no change between {before} and {after}'
            assert b == self.git('show', f'{tag}:{path}'), f'{path} on {after} is not the file at {tag}'
            assert a == self.git('show', f'{tag}~1:{path}'), f'{path} on {before} is not the file before {tag}'
            done.append(f'{path} {before} != {after}')
        listing = self.tool('on', '2000-01-01', 'sb/1993')
        assert 'sb/1993/1.md' in listing and 'sb/1993/2.md' in listing, 'acts of 1993 missing on 2000-01-01'
        try:
            self.tool('on', '1992-01-01', 'sb/1993/1.md')
            raise AssertionError('the Constitution should not be in force on 1992-01-01')
        except AssertionError as e:
            if 'should not' in str(e):
                raise
        return '; '.join(done)

    def follow(self):
        checked = []
        for path in ('sb/1993/1.md', 'sb/1993/2.md', 'sb/2012/89.md', 'sb/2009/40.md'):
            out = self.git('log', '--follow', '--format=%an%x09%(trailers:key=In-force,valueonly,separator=)', 'main', '--', path)
            rows = [l.split('\t') for l in out.splitlines() if l]
            assert len(rows) >= 2, f'{path}: {len(rows)} commits'
            days = [d.strip() for _, d in rows]
            assert days == sorted(days, reverse=True), f'{path}: not in date order'
            assert all(LAW.match(a) or a == PUBLISHER for a, _ in rows), f'{path}: authors {[a for a, _ in rows][:5]}'
            assert sum(1 for a, _ in rows if LAW.match(a)) >= 2, f'{path}: fewer than two acts'
            checked.append(f'{path} {len(rows)} commits')
        return '; '.join(checked)

    def tags_and_trailers(self):
        tags = self.git('tag').split()
        assert tags, 'no tags'
        bad = [t for t in tags if subprocess.run(['git', 'rev-parse', '--verify', '-q', f'{t}^{{commit}}'], cwd=self.repo,
                                                 capture_output=True).returncode]
        assert not bad, f'tags that do not resolve: {bad[:3]}'
        rows = self.git('log', '--format=%H%x09%(trailers:key=In-force,valueonly,separator=)', 'main', 'future').splitlines()
        head = self.git('rev-parse', 'main').strip()
        missing = [r for r in rows if not r.split('\t')[1].strip() and r.split('\t')[0] != head]
        assert not missing, f'{len(missing)} commits without In-force'
        assert not [r for r in rows if r.split('\t')[0] == head and r.split('\t')[1].strip()], 'documentation commit has In-force'
        bad = [r for r in rows if r.split('\t')[1].strip() and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', r.split('\t')[1].strip())]
        assert not bad, f'malformed In-force {bad[:2]}'
        keys = set(re.findall(r'^([^:\n]+):', self.git('log', '--format=%(trailers:only,unfold)', 'main', 'future'), re.M))
        assert all(k.isascii() for k in keys), f'non-ASCII trailer keys {keys}'
        return f'{len(tags)} tags resolve; {len(rows) - 1} law commits carry In-force; trailer keys {sorted(keys)}'

    def lexifina(self):
        rows = self.git('log', '--format=%H%x09%an%x09%ae%x09%cn', 'main').splitlines()
        by_lex = [r for r in rows if r.split('\t')[1] == 'Lexifina']
        assert len(by_lex) == 1 and by_lex[0] == rows[0], f'{len(by_lex)} commits by Lexifina'
        assert all(r.split('\t')[3] == 'Lexifina' for r in rows), 'a committer other than Lexifina'
        assert all(r.split('\t')[2].endswith('.invalid') for r in rows[1:]), 'an author address that is not .invalid'
        authors = {r.split('\t')[1] for r in rows[1:]}
        assert all(LAW.match(a) or a == PUBLISHER for a in authors), f'unexpected authors {sorted(authors - {PUBLISHER})[:5]}'
        return f'only the documentation commit {rows[0][:10]} is by Lexifina; {len(authors)} distinct authors'

    def branches(self):
        corpus = json.loads((self.repo / 'corpus.json').read_text(encoding='utf-8'))
        built = corpus['built']
        main = [d for d in self.git('log', '--format=%(trailers:key=In-force,valueonly,separator=)', 'main').split() if d]
        assert max(main) <= built, f'main has {max(main)} after {built}'
        assert max(main) == corpus['record_to'], f"record_to {corpus['record_to']} is not main's last day {max(main)}"
        fut = [d for d in self.git('log', '--format=%(trailers:key=In-force,valueonly,separator=)', 'main..future').split() if d]
        assert all(d > built for d in fut), 'future has a day on or before the build day'
        return f'main to {max(main)}; future {len(fut)} commits from {min(fut) if fut else "-"}'

    def readme(self):
        text = (self.repo / 'README.md').read_text(encoding='utf-8')
        table = text[text.index('## The questions'):text.index('## The dates')]
        cmds = [c for c in re.findall(r'`([^`]+)`', table) if c.startswith(('git ', 'python '))]
        assert len(cmds) >= 8, f'only {len(cmds)} commands found'
        for c in cmds:
            args = shlex.split(c)
            if args[0] == 'python':
                args = [sys.executable, '-X', 'utf8'] + args[1:]
            out = subprocess.run(args, cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
            assert out.returncode == 0, f'{c}: exit {out.returncode} {out.stderr.strip()[:200]}'
            assert out.stdout.strip(), f'{c}: printed nothing'
        return f'{len(cmds)} README commands ran and printed output'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=None)
    ap.add_argument('--record', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    s = Smoke(Path(args.repo) if args.repo else default_repo())
    s.check('blame names acts', s.blame)
    s.check('text before and after an amendment', s.on_date)
    s.check('log --follow in date order', s.follow)
    s.check('tags resolve, In-force on every law commit, ASCII trailer keys', s.tags_and_trailers)
    s.check('only the documentation commit is by Lexifina', s.lexifina)
    s.check('main and future split at the build day', s.branches)
    s.check('README commands run', s.readme)
    ok = all(r[1] for r in s.results)
    print(f'{sum(r[1] for r in s.results)}/{len(s.results)} passed')
    if args.record:
        p = HERE / 'verification.json'
        rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        rec['smoke'] = {'passed': sum(r[1] for r in s.results), 'total': len(s.results),
                        'results': [{'test': n, 'ok': o, 'detail': d} for n, o, d in s.results]}
        p.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
