"""
Minimal STEP (ISO 10303-21) entity scanner.

Handles both simple entities (#id = TYPE(args)) and the complex-entity
lookup needed for assembly instance transforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ENTITY_START_RE = re.compile(r"#(\d+)\s*=\s*([A-Za-z_][A-Za-z_0-9]*)\s*\(")


@dataclass(frozen=True)
class Entity:
    """One STEP DATA-section instance: `#id = NAME ( raw_params ) ;`"""
    id: int
    name: str          # always uppercased for easy comparison
    raw_params: str    # text between the outer parens, not yet split


def parse_step(path: Path) -> dict[int, Entity]:
    """
    Parse a STEP file and return every simple entity in its DATA section, keyed by id.

    Entities are not interpreted here — callers walk the returned dict and pick
    out the types they care about.  Complex entities (``#id =( ... );``) are
    skipped; use :func:`parse_step_full` + :func:`scan_rr_transforms` when you
    also need the assembly-instance transform links.
    """
    entities, _ = parse_step_full(path)
    return entities


def parse_step_full(path: Path) -> tuple[dict[int, Entity], str]:
    """
    Like :func:`parse_step` but also returns the raw DATA-section text.

    The raw text is needed by :func:`scan_rr_transforms` to extract complex
    entities (REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION) that the main
    scanner skips because they use the ``#id =( ... )`` compound syntax.
    """
    # Try UTF-8 first (the nominal ISO 10303-21 charset). SolidWorks installs
    # on Chinese Windows commonly dump raw GBK bytes for Chinese characters
    # instead of the standard \X2\...\X0\ escapes, so fall back to GBK when
    # strict UTF-8 fails. replace-mode catches any truly stray bytes.
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    del raw

    data_start = text.find("DATA;")
    data_end = text.find("ENDSEC;", data_start if data_start >= 0 else 0)
    if data_start < 0 or data_end < 0:
        raise ValueError(f"{path} is not a valid STEP file (missing DATA/ENDSEC)")

    body = text[data_start + len("DATA;"):data_end]
    return _scan_entities(body), body


# Matches lines like:
#   #1521017 =( REPRESENTATION_RELATIONSHIP ('NONE','NONE', ...) \
#               REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION ( #5316216 ) ... );
# We only care about the compound-entity id and the IDT reference it contains.
_RR_TRANSFORM_RE = re.compile(
    r"#(\d+)\s*=\s*\("               # compound entity opening
    r"[^;]*?"                         # any content up to ';' — crosses newlines, stops at entity boundary
    r"REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION\s*\(\s*#(\d+)\s*\)",
    re.DOTALL,
)


def scan_rr_transforms(data_text: str) -> dict[int, int]:
    """
    Return ``{compound_entity_id: idt_ref}`` for every compound entity in the
    DATA section that embeds a REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION.

    These are the per-instance placement links that the main scanner misses.
    Each compound entity id matches a CONTEXT_DEPENDENT_SHAPE_REPRESENTATION
    field[0]; the idt_ref points to an ITEM_DEFINED_TRANSFORMATION whose
    field[2] holds the AXIS2_PLACEMENT_3D for the instance in world space.
    """
    return {int(m.group(1)): int(m.group(2)) for m in _RR_TRANSFORM_RE.finditer(data_text)}


def _scan_entities(body: str) -> dict[int, Entity]:
    """Walk the DATA section, parenthesis-aware, and collect entities."""
    entities: dict[int, Entity] = {}
    i = 0
    while True:
        m = ENTITY_START_RE.search(body, i)
        if not m:
            break
        eid = int(m.group(1))
        ename = m.group(2).upper()
        end = _find_matching_paren(body, m.end())
        raw = body[m.end():end]
        entities[eid] = Entity(id=eid, name=ename, raw_params=raw)
        i = end + 1  # step past the closing ')'
    return entities


def _find_matching_paren(body: str, start: int) -> int:
    """
    Given a position just after a `(`, return the index of the matching `)`.
    Respects nested parens and STEP string literals (single-quoted, with ''
    as the escape for an embedded quote).
    """
    depth = 1
    in_str = False
    i = start
    n = len(body)
    while i < n:
        c = body[i]
        if c == "'":
            # STEP escape: two single quotes mean a literal quote inside a string
            if in_str and i + 1 < n and body[i + 1] == "'":
                i += 2
                continue
            in_str = not in_str
        elif not in_str:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("Unterminated entity — no matching ')'")


def split_args(raw: str) -> list[str]:
    """
    Split a STEP entity's raw parameter string on top-level commas, preserving
    nested parens and string contents.
    """
    args: list[str] = []
    buf: list[str] = []
    depth = 0
    in_str = False
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if c == "'":
            if in_str and i + 1 < n and raw[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_str = not in_str
            buf.append(c)
        elif not in_str:
            if c == "(":
                depth += 1
                buf.append(c)
            elif c == ")":
                depth -= 1
                buf.append(c)
            elif c == "," and depth == 0:
                args.append("".join(buf).strip())
                buf = []
            else:
                buf.append(c)
        else:
            buf.append(c)
        i += 1
    if buf or args:
        args.append("".join(buf).strip())
    return args


_STEP_ESCAPE_RE = re.compile(
    r"\\X2\\([0-9A-Fa-f]+)\\X0\\"   # UTF-16BE run
    r"|\\X4\\([0-9A-Fa-f]+)\\X0\\"  # UTF-32BE run
    r"|\\X\\([0-9A-Fa-f]{2})"       # single ISO 8859-1 byte
)


def _decode_step_escapes(inner: str) -> str:
    """
    Decode ISO 10303-21 control-directive escapes inside a STEP string literal.

    Handles the non-ASCII escape forms emitted by standards-compliant exporters:
      * ``\\X2\\hhhh...\\X0\\`` — one or more UTF-16BE code units (4 hex each)
      * ``\\X4\\hhhhhhhh...\\X0\\`` — one or more UTF-32BE code points (8 hex each)
      * ``\\X\\hh`` — one ISO 8859-1 byte

    Files from Chinese SolidWorks installs often skip these escapes and dump
    raw GBK bytes; those are handled at the file-read level in parse_step_full.
    Both fixes together give us correct decoding for both styles.
    """
    if "\\X" not in inner:
        return inner

    def repl(m: re.Match[str]) -> str:
        utf16_hex, utf32_hex, byte_hex = m.group(1), m.group(2), m.group(3)
        if utf16_hex is not None:
            # Every 4 hex digits = one UTF-16 code unit (handles surrogate pairs).
            return bytes.fromhex(utf16_hex).decode("utf-16-be", errors="replace")
        if utf32_hex is not None:
            return bytes.fromhex(utf32_hex).decode("utf-32-be", errors="replace")
        # \X\hh — single ISO 8859-1 byte
        return bytes.fromhex(byte_hex).decode("latin-1")

    return _STEP_ESCAPE_RE.sub(repl, inner)


def unquote(s: str) -> str:
    """Strip STEP string quoting. Returns the input unchanged if not quoted."""
    s = s.strip()
    if len(s) >= 2 and s.startswith("'") and s.endswith("'"):
        return _decode_step_escapes(s[1:-1].replace("''", "'"))
    return s


def as_ref(s: str) -> int | None:
    """Parse a STEP reference like `#42` into 42. Returns None if not a ref."""
    s = s.strip()
    if s.startswith("#") and s[1:].isdigit():
        return int(s[1:])
    return None
