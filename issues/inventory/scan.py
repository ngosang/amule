#!/usr/bin/env python3
"""Scan src/webapi for API facts: per-function errors, params, body fields,
sort keys, auth gates, and a JSON response skeleton per writer.

Output: facts.json  {"funcs": {name: facts}, "shapes": {name: skeleton}}
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apiscan

FILES = ["Api.cpp", "SearchJson.cpp"]
funcs = apiscan.index(FILES)
code = {}   # name -> comment/literal-blanked body (for structure scanning)
raw = {}    # name -> original body
for n, occ in funcs.items():
    raw[n] = "\n".join(e["body"] for e in occ)
    code[n] = apiscan.blank_noncode(raw[n])

def call_args(text, fname):
    """Yield the argument lists of every `fname(...)` call in `text`.

    Scans with paren depth and quote awareness, so a `;` or `,` inside a
    string literal (or a nested call) does not split an argument.
    """
    out = []
    i = 0
    pat = fname + "("
    while True:
        i = text.find(pat, i)
        if i < 0:
            return out
        j = i + len(pat)
        depth, args, cur, in_str = 1, [], "", False
        while j < len(text):
            c = text[j]
            if in_str:
                cur += c
                if c == "\\":
                    cur += text[j + 1]; j += 2; continue
                if c == '"':
                    in_str = False
                j += 1; continue
            if c == '"':
                in_str = True; cur += c; j += 1; continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    args.append(cur); break
            if depth == 1 and c == ",":
                args.append(cur); cur = ""; j += 1; continue
            cur += c
            j += 1
        out.append([a.strip() for a in args])
        i = j + 1

QMAP = re.compile(r'(?:qmap|qm|q)\.find\("([^"]+)"\)')
BODYF = re.compile(r'obj\.find\("([^"]+)"\)')
COMP = re.compile(r'\{\s*"([a-z_0-9]+)",\s*\n?\s*\[\]')
CALL = re.compile(r'\b([A-Z][A-Za-z0-9_]*)\s*\(')
KEY = re.compile(r'\.Key\("([^"]+)"\)')
ISTYPE = re.compile(r'is<(std::string|bool|double|picojson::array|picojson::object)>')


def clean(s):
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'"\s*"', '', s)          # join adjacent literals
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].replace('\\"', '"')
    return s


def facts(name):
    t = raw[name]
    errs, seen = [], set()
    for args in call_args(t, "ErrorResponse"):
        if len(args) < 3 or not args[0].strip().isdigit():
            continue
        st, c, msg = int(args[0]), args[1].strip().strip('"'), clean(args[2])
        if (st, c, msg) not in seen:
            seen.add((st, c, msg)); errs.append([st, c, msg[:240]])
    for args in call_args(t, "BadRequestPtr"):
        msg = clean(args[0]) if args else ""
        if (400, "bad_request", msg) not in seen:
            seen.add((400, "bad_request", msg)); errs.append([400, "bad_request", msg[:240]])
    bulk = []
    for args in call_args(t, "BulkErr"):
        if len(args) >= 4:
            bulk.append([int(args[1]) if args[1].strip().isdigit() else args[1],
                         args[2].strip().strip('"'), clean(args[3])[:200]])
    seen_b, ub = set(), []
    for b in bulk:
        k = tuple(str(x) for x in b)
        if k not in seen_b:
            seen_b.add(k); ub.append(b)
    return {
        "loc": [f"{e['file']}:{e['start']}-{e['end']}" for e in funcs[name]],
        "lines": sum(e["end"] - e["start"] + 1 for e in funcs[name]),
        "errors": errs,
        "bulk_errors": ub,
        "query": sorted(set(QMAP.findall(t))),
        "body_fields": sorted(set(BODYF.findall(t))),
        "sort_keys": sorted(set(COMP.findall(t))),
        "keys": list(dict.fromkeys(KEY.findall(t))),
        "calls": sorted(c for c in set(CALL.findall(code[name])) if c in funcs and c != name),
        "auth": "Authenticate(req)" in t,
        "admin": "RequireAdmin(" in t,
        "snapshot_gate": "RequireSnapshot(" in t,
        "list_params": "ParseListParams(" in t,
        "json_body": "ParseJsonObjectBody(" in t,
        "status_literals": sorted(set(re.findall(r'\.status\s*=\s*(\d+)', t))),
    }


# ---- response skeletons -------------------------------------------------
TOK = re.compile(
    r'\.Key\("([^"]+)"\)'
    r'|\.(BeginObject|EndObject|BeginArray|EndArray)\(\)'
    r'|\.(ValueString|ValueInt|ValueUInt|ValueBool|ValueDouble|ValueNull|ValueRaw)\('
    # `WriteIntOrNull(w, "key", known, value)` writes the key itself, so the
    # generic Write* recursion below sees only a variable and drops the field.
    r'|\bWrite(Int)OrNull\s*\(\s*w\s*,\s*"([^"]+)"'
    r'|\b(Write[A-Za-z0-9_]*|ToJson[A-Za-z0-9_]*)\s*\(')
VT = {"ValueString": "string", "ValueInt": "int", "ValueUInt": "uint", "ValueBool": "bool",
      "ValueDouble": "number", "ValueNull": "null", "ValueRaw": "raw"}


def events(name, depth=0, stack=()):
    if name in stack or depth > 8:
        return [("val", f"<{name}>")]
    body = raw[name]
    body = body[body.find('{'):]
    ev = []
    for k, st, val, ornull_t, ornull_k, call in TOK.findall(body):
        if k:
            ev.append(("key", k))
        elif st:
            ev.append(("open" if st.startswith("Begin") else "close", "obj" if "Object" in st else "arr"))
        elif val:
            ev.append(("val", VT[val]))
        elif ornull_k:
            ev.append(("key", ornull_k))
            ev.append(("val", VT["Value" + ornull_t] + "|null"))
        elif call in funcs:
            ev.extend(events(call, depth + 1, stack + (name,)))
    return ev


def fold(ev):
    root, stack, pend = None, [], []

    def attach(v):
        nonlocal root
        if not stack:
            if root is None:
                root = v
            return
        cur = stack[-1]
        if isinstance(cur, dict):
            if pend[-1] is not None:
                cur[pend[-1]] = v; pend[-1] = None
        elif not cur:
            cur.append(v)

    for kind, v in ev:
        if kind == "key":
            if not stack:
                # writer that emits keys into the caller's object
                if root is None or not isinstance(root, dict):
                    root = {}
                stack.append(root); pend.append(None)
            if stack and isinstance(stack[-1], dict):
                pend[-1] = v; stack[-1].setdefault(v, "?")
        elif kind == "val":
            attach(v)
        elif kind == "open":
            new = {} if v == "obj" else []
            reuse = None
            if stack:
                cur = stack[-1]
                if isinstance(cur, dict) and pend[-1] is not None:
                    ex = cur.get(pend[-1])
                    if isinstance(ex, (dict, list)) and isinstance(ex, type(new)):
                        reuse = ex
                elif isinstance(cur, list) and cur and isinstance(cur[0], type(new)):
                    reuse = cur[0]
            elif root is not None and isinstance(root, type(new)):
                reuse = root
            if reuse is None:
                attach(new)
            else:
                new = reuse
                if stack and isinstance(stack[-1], dict):
                    pend[-1] = None
            stack.append(new); pend.append(None)
        elif kind == "close":
            # never pop the writer's own root: several writers have an
            # early-return path that emits a duplicate End* token.
            if len(stack) > 1:
                stack.pop(); pend.pop()
    return root if root is not None else {}


out = {"funcs": {n: facts(n) for n in funcs}, "shapes": {}}
for n in funcs:
    ev = events(n)
    if ev:
        out["shapes"][n] = fold(ev)
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(f"funcs {len(out['funcs'])}  shapes {len(out['shapes'])}")
