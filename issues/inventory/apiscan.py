#!/usr/bin/env python3
"""Shared slicer: split a C++ file into top-level function definitions.

Comments and string/char literal *contents* are blanked before brace
counting so a `{` inside a comment or a JSON literal cannot desync the
depth tracking. Bodies are returned from the original text.
"""
import os, re

# Repo root is two levels up from this file (issues/inventory/).
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.join(REPO, "src", "webapi")


def blank_noncode(src):
    """Return src with comments and literal contents replaced by spaces
    (newlines preserved, so line numbers and column counts still line up)."""
    out = []
    i, n = 0, len(src)
    state = None  # None | 'line' | 'block' | 'str' | 'chr'
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ''
        if state is None:
            if c == '/' and nxt == '/':
                state = 'line'; out.append('  '); i += 2; continue
            if c == '/' and nxt == '*':
                state = 'block'; out.append('  '); i += 2; continue
            if c == '"':
                state = 'str'; out.append('"'); i += 1; continue
            if c == "'":
                state = 'chr'; out.append("'"); i += 1; continue
            out.append(c); i += 1; continue
        if state in ('line', 'block'):
            if state == 'line' and c == '\n':
                state = None; out.append('\n'); i += 1; continue
            if state == 'block' and c == '*' and nxt == '/':
                state = None; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        # inside a literal
        if c == '\\':
            out.append('  '); i += 2; continue
        if (state == 'str' and c == '"') or (state == 'chr' and c == "'"):
            out.append(c); state = None; i += 1; continue
        out.append('\n' if c == '\n' else ' '); i += 1
    return ''.join(out)


SKIP_PREFIX = ('namespace', 'using', 'struct', 'class', 'enum', 'template',
               'extern', 'typedef', 'static const', 'const char *const', 'constexpr')


def slice_functions(src):
    """{name: [(start_line, end_line, body)]} for definitions starting at column 0."""
    code = blank_noncode(src).split('\n')
    orig = src.split('\n')
    out = {}
    i, n = 0, len(code)
    while i < n:
        l = code[i]
        if l and l[0] not in ' \t#/}' and '(' in l and not l.lstrip().startswith(SKIP_PREFIX):
            j = i
            while j < n and '{' not in code[j] and ';' not in code[j]:
                j += 1
            if j >= n:
                i += 1; continue
            sig = '\n'.join(code[i:j + 1])
            if ';' in code[j] and '{' not in code[j]:
                i = j + 1; continue
            names = re.findall(r'([A-Za-z_]\w*)\s*\(', sig)
            if not names:
                i = j + 1; continue
            head = sig.split('(')[0]
            name = head.strip().split('::')[-1].split()[-1] if '::' in head else names[0]
            name = name.lstrip('&*')
            depth, k, started = 0, j, False
            while k < n:
                depth += code[k].count('{') - code[k].count('}')
                if '{' in code[k]:
                    started = True
                if started and depth <= 0:
                    break
                k += 1
            out.setdefault(name, []).append((i + 1, k + 1, '\n'.join(orig[i:k + 1])))
            i = k + 1
        else:
            i += 1
    return out


def index(files):
    funcs = {}
    for f in files:
        for name, occ in slice_functions(open(os.path.join(ROOT, f)).read()).items():
            for (a, b, body) in occ:
                funcs.setdefault(name, []).append({"file": f, "start": a, "end": b, "body": body})
    return funcs
