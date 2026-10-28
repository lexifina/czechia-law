"""Fast streaming of e-Sbírka's bulk JSON datasets.

The files are one object {"položky": [ {...}, {...} ]}, pretty-printed so that each record starts with "{" and ends
with "}" at column 0 ("},\n{" between records). Reading 16 MB chunks, splitting on that boundary with bytes.find and
handing each record to the C json decoder is far faster than ijson or line iteration (measured in PROGRESS.md).
"""
from __future__ import annotations

import gzip
import json
import zlib
from typing import Iterator

SEP = b"\n},\n{"


def raw_records(path: str, chunk: int = 1 << 24) -> Iterator[bytes]:
    """Yield each record's JSON bytes."""
    with open(path, "rb") as fh:
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        buf = b""
        started = False
        while True:
            comp = fh.read(chunk // 4)
            if not comp:
                data = d.flush()
                eof = True
            else:
                data = d.decompress(comp)
                eof = False
                # Concatenated gzip members.
                while d.unused_data:
                    rest = d.unused_data
                    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    data += d.decompress(rest)
            buf += data
            if not started:
                i = buf.find(b"[\n{")
                if i < 0:
                    if eof:
                        return
                    continue
                buf = buf[i + 2:]
                started = True
            start = 0
            while True:
                j = buf.find(SEP, start)
                if j < 0:
                    break
                yield buf[start:j + 2]
                start = j + 4
            buf = buf[start:]
            if eof:
                # The last record, then the array's "]" and the outer object's "}".
                t = buf.rstrip()
                if t.endswith(b"}"):
                    t = t[:-1].rstrip()
                if t.endswith(b"]"):
                    t = t[:-1].rstrip()
                if t:
                    yield t
                return


def slices(path: str, n: int) -> list:
    """Split a decompressed dataset into n byte ranges that each start at a record's "{"."""
    import os
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = fh.read(1 << 16)
        first = head.find(b"[\n{") + 2
        cuts = [first]
        for k in range(1, n):
            pos = max(cuts[-1], size * k // n)
            fh.seek(pos)
            blk = fh.read(1 << 22)
            j = blk.find(SEP)
            if j < 0:
                continue
            cuts.append(pos + j + 4)
        cuts.append(size)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


def range_records(path: str, start: int, end: int, chunk: int = 1 << 25) -> Iterator[bytes]:
    """Records whose "{" lies in [start, end) of a decompressed dataset (see slices)."""
    with open(path, "rb") as fh:
        fh.seek(start)
        buf = b""
        pos = start          # file offset of buf[0]
        done = False
        while not done:
            data = fh.read(chunk)
            if not data:
                done = True
            buf += data
            s = 0
            while True:
                if pos + s >= end:
                    return
                j = buf.find(SEP, s)
                if j < 0:
                    break
                yield buf[s:j + 2]
                s = j + 4
            buf = buf[s:]
            pos += s
            if done:
                if pos < end:
                    t = buf.rstrip()
                    if t.endswith(b"}"):
                        t = t[:-1].rstrip()
                    if t.endswith(b"]"):
                        t = t[:-1].rstrip()
                    if t:
                        yield t
                return


def records(path: str) -> Iterator[dict]:
    loads = json.loads
    for b in raw_records(path):
        yield loads(b)
