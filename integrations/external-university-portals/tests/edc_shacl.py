"""A cardinality checker for Europass EDC credentials against the official SHACL shapes (tests/fixtures/edc).

No SHACL engine is on the approved stack, so this reads the shapes file directly (a regular Turtle subset: one NodeShape
per class naming PropertyShapes, each with `sh:path`, `sh:minCount`, `sh:maxCount`) and walks the JSON-LD document: for
every object whose `type` names a class, every property shape of that class must occur between minCount and maxCount
times. Keys are mapped to property IRIs through the official JSON-LD context. It does not check datatypes, `sh:class`
or controlled-vocabulary membership. See tests/fixtures/edc/SOURCE.md.
"""

from __future__ import annotations

import re

# Terms the W3C VC v1 context (https://www.w3.org/2018/credentials/v1) defines; the EDC context does not repeat them.
CRED = "https://www.w3.org/2018/credentials#"
VC_TERMS = (
    "issuer",
    "credentialSubject",
    "issued",
    "issuanceDate",
    "validFrom",
    "validUntil",
    "expirationDate",
    "credentialSchema",
    "credentialStatus",
    "proof",
    "evidence",
    "termsOfUse",
    "holder",
)


def parse(ttl: str):
    """(prefixes, node shapes {name: (target class, [property shape names])}, property shapes {name: (path, min, max)})."""
    prefixes = dict(re.findall(r"@prefix\s+(\w*):\s*<([^>]+)>", ttl))
    body = re.sub(r"#[^\n]*", "", re.sub(r'"[^"\n]*"@\w+|"[^"\n]*"', '""', ttl))  # drop comments and string literals
    nodes: dict[str, tuple[str, list[str]]] = {}
    props: dict[str, tuple[str | None, int, int | None]] = {}
    for block in re.split(r"\n\s*\.\s*(?=\n|$)", body):
        head = re.match(r"\s*([\w:<>/#.-]+)\s+a\s+sh:(NodeShape|PropertyShape)", block)
        if not head:
            continue
        name, kind = head.group(1), head.group(2)
        if kind == "NodeShape":
            target = re.search(r"sh:targetClass\s+([\w:]+)", block)
            if target:
                nodes[name] = (target.group(1), re.findall(r"sh:property\s+([\w:-]+)\s*[;.]?", block))
        else:
            path = re.search(r"sh:path\s+([\w:]+)", block)
            lo, hi = re.search(r"sh:minCount\s+(\d+)", block), re.search(r"sh:maxCount\s+(\d+)", block)
            props[name] = (
                path.group(1) if path else None,
                int(lo.group(1)) if lo else 0,
                int(hi.group(1)) if hi else None,
            )
    return prefixes, nodes, props


def _expand(curie: str, prefixes: dict[str, str]) -> str:
    if ":" in curie and not curie.startswith("http"):
        prefix, local = curie.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + local
    return curie


def check(doc: dict, ttl: str, context: dict, exempt=()) -> list[str]:
    """Violations of the shapes' cardinalities, one string each; empty when the credential conforms."""
    prefixes, nodes, props = parse(ttl)
    prefixes = {
        **prefixes,
        **{k: v for k, v in context["@context"].items() if isinstance(v, str) and v.startswith("http")},
    }
    terms: dict[str, str] = {}
    for term, definition in context["@context"].items():
        iri = definition.get("@id") if isinstance(definition, dict) else definition
        if not term.startswith("@") and isinstance(iri, str):
            terms[term] = _expand(iri, prefixes)
    for name in VC_TERMS:
        terms.setdefault(name, CRED + name)
    terms.setdefault("VerifiableCredential", CRED + "VerifiableCredential")
    by_class: dict[str, list[str]] = {}
    for _name, (cls, plist) in nodes.items():
        by_class.setdefault(_expand(cls, prefixes), []).extend(plist)
    out: list[str] = []

    def count(obj: dict, iri: str) -> int:
        return sum(len(v) if isinstance(v, list) else 1 for k, v in obj.items() if terms.get(k) == iri)

    def walk(obj, where: str) -> None:
        if isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f"{where}[{i}]")
        elif isinstance(obj, dict):
            kinds = obj.get("type", [])
            for kind in [kinds] if isinstance(kinds, str) else kinds:
                for pname in by_class.get(terms.get(kind), []):
                    path, lo, hi = props.get(pname, (None, 0, None))
                    if path is None or (kind, path) in exempt:
                        continue
                    n = count(obj, _expand(path, prefixes))
                    if n < lo or (hi is not None and n > hi):
                        out.append(f"{where} ({kind}): {path} has {n}, shape wants {lo}..{hi}")
            for k, v in obj.items():
                walk(v, f"{where}.{k}")

    walk(doc, "$")
    return out
