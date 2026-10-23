"""
Turn raw STEP entities into a part hierarchy + instance counts.

STEP walk used here (AP214/AP242 both follow this shape):

  NEXT_ASSEMBLY_USAGE_OCCURRENCE (NAUO)
      .relating_product_definition  --> PRODUCT_DEFINITION (the parent)
      .related_product_definition   --> PRODUCT_DEFINITION (the child)

  PRODUCT_DEFINITION
      .formation  --> PRODUCT_DEFINITION_FORMATION

  PRODUCT_DEFINITION_FORMATION
      .of_product --> PRODUCT  (the unique part: id, name, description)

So each NAUO is one *instance* of a child product under a parent product, and
the quantity of a given part in the assembly = number of NAUOs whose "related"
product resolves to that product.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .parser import Entity, as_ref, split_args, unquote


# Entity field positions (0-indexed) per ISO 10303-41 / AP214 / AP242.
# PRODUCT(id, name, description, frame_of_reference)
_PRODUCT_ID = 0
_PRODUCT_NAME = 1
_PRODUCT_DESC = 2

# PRODUCT_DEFINITION(id, description, formation, frame_of_reference)
_PD_FORMATION = 2

# PRODUCT_DEFINITION_FORMATION(id, description, of_product)
_PDF_OF_PRODUCT = 2

# NEXT_ASSEMBLY_USAGE_OCCURRENCE(id, name, description, relating_pd, related_pd, ref_designator)
_NAUO_RELATING = 3
_NAUO_RELATED = 4


@dataclass
class Product:
    """A unique part as declared by a PRODUCT entity."""
    product_ref: int       # the #N id of the PRODUCT entity
    id: str                # PRODUCT.id    (often the engineering part number)
    name: str              # PRODUCT.name  (often the display name)
    description: str       # PRODUCT.description


@dataclass
class Hierarchy:
    """Everything needed to compute stats and do BOM matching."""
    products: dict[int, Product] = field(default_factory=dict)
    # parent_product_ref -> list of child product_refs (one entry per NAUO, so
    # duplicates represent multiple instances of the same child under the parent)
    children: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    # product_ref -> how many times this product appears as a child across the
    # whole assembly (i.e. total instance count / qty)
    instance_count: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    # product_refs that never appear as a child *and* have at least one child —
    # the true assembly roots
    roots: list[int] = field(default_factory=list)
    # product_refs that never appear as a child *and* have no children of their
    # own — declared in the STEP PRODUCT table but unused by any NAUO. Typically
    # SolidWorks "dummy" placeholder parts that got exported alongside the
    # assembly. Dropped from BOM / parts list per task #6.
    orphans: list[int] = field(default_factory=list)
    # One entry per resolved NAUO: (parent_product_ref, child_product_ref, nauo_id).
    # Lets the emitter produce per-NAUO HAS_MODULE / HAS_COMPONENT /
    # HAS_SUBCOMPONENT edges without re-walking the entity table. h.children
    # flattens these into a parent->[children] map and loses the NAUO id;
    # h.nauo_edges keeps them.
    nauo_edges: list[tuple[int, int, int]] = field(default_factory=list)
    # number of NAUOs we couldn't resolve (missing refs, malformed entities)
    unresolved_nauos: int = 0


def build_hierarchy(entities: dict[int, Entity]) -> Hierarchy:
    """Resolve NAUO -> PD -> PDF -> PRODUCT and build the hierarchy object."""
    # Index by entity type once so we don't re-scan.
    by_type: dict[str, list[Entity]] = defaultdict(list)
    for e in entities.values():
        by_type[e.name].append(e)

    # Products: product_ref -> Product
    products: dict[int, Product] = {}
    for e in by_type.get("PRODUCT", []):
        args = split_args(e.raw_params)
        if len(args) <= _PRODUCT_DESC:
            continue
        products[e.id] = Product(
            product_ref=e.id,
            id=unquote(args[_PRODUCT_ID]),
            name=unquote(args[_PRODUCT_NAME]),
            description=unquote(args[_PRODUCT_DESC]),
        )

    # Resolver: PRODUCT_DEFINITION ref -> PRODUCT ref
    pd_to_product: dict[int, int] = {}
    pdf_to_product: dict[int, int] = {}
    # AP203 CONFIG_CONTROL_DESIGN uses the _WITH_SPECIFIED_SOURCE subtype, which
    # adds a trailing .source field but keeps arg positions 0..2 identical.
    for pdf_type in (
        "PRODUCT_DEFINITION_FORMATION",
        "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE",
    ):
        for e in by_type.get(pdf_type, []):
            args = split_args(e.raw_params)
            if len(args) <= _PDF_OF_PRODUCT:
                continue
            prod_ref = as_ref(args[_PDF_OF_PRODUCT])
            if prod_ref is not None:
                pdf_to_product[e.id] = prod_ref
    for e in by_type.get("PRODUCT_DEFINITION", []):
        args = split_args(e.raw_params)
        if len(args) <= _PD_FORMATION:
            continue
        pdf_ref = as_ref(args[_PD_FORMATION])
        if pdf_ref is not None and pdf_ref in pdf_to_product:
            pd_to_product[e.id] = pdf_to_product[pdf_ref]

    h = Hierarchy(products=products)

    # Walk NAUOs — each one is an instance edge parent-child.
    all_children: set[int] = set()
    for e in by_type.get("NEXT_ASSEMBLY_USAGE_OCCURRENCE", []):
        args = split_args(e.raw_params)
        if len(args) <= _NAUO_RELATED:
            h.unresolved_nauos += 1
            continue
        relating_pd = as_ref(args[_NAUO_RELATING])
        related_pd = as_ref(args[_NAUO_RELATED])
        if relating_pd is None or related_pd is None:
            h.unresolved_nauos += 1
            continue
        parent_prod = pd_to_product.get(relating_pd)
        child_prod = pd_to_product.get(related_pd)
        if parent_prod is None or child_prod is None:
            h.unresolved_nauos += 1
            continue
        h.children[parent_prod].append(child_prod)
        h.instance_count[child_prod] += 1
        all_children.add(child_prod)
        h.nauo_edges.append((parent_prod, child_prod, e.id))

    # Split products with no parent into two buckets:
    #   roots   — also a parent of something (real assembly root)
    #   orphans — also has no children (unused PRODUCT declaration)
    # `h.children` is a defaultdict(list); `key in defaultdict` does not
    # auto-create, so this read is safe.
    no_parent = (pref for pref in products if pref not in all_children)
    roots: list[int] = []
    orphans: list[int] = []
    for pref in no_parent:
        (roots if pref in h.children else orphans).append(pref)
    h.roots = sorted(roots)
    h.orphans = sorted(orphans)
    return h


def find_product_by_name_or_id(h: Hierarchy, query: str) -> list[int]:
    """Return product refs whose name or id matches query (case-insensitive)."""
    q = query.strip().lower()
    return [
        ref for ref, p in h.products.items()
        if p.name.strip().lower() == q or p.id.strip().lower() == q
    ]


def subtree_product_refs(h: Hierarchy, root_ref: int) -> set[int]:
    """
    Return all product refs reachable from root_ref (inclusive).

    Used to scope geometry extraction and mate inference to a single
    sub-assembly so the O(N²) sibling loop only sees parts within that scope.
    """
    visited: set[int] = set()
    queue = [root_ref]
    while queue:
        node = queue.pop()
        if node in visited:
            continue
        visited.add(node)
        # h.children values are lists with duplicates (one entry per NAUO);
        # use a set to avoid queuing the same child multiple times.
        queue.extend(set(h.children.get(node, [])))
    return visited


def max_depth(h: Hierarchy) -> int:
    """
    Longest root-to-leaf path in the assembly tree. Cycles shouldn't occur in
    well-formed STEP but we guard against them anyway.
    """
    memo: dict[int, int] = {}

    def depth(node: int, seen: frozenset[int]) -> int:
        if node in seen:
            return 0  # cycle guard
        if node in memo:
            return memo[node]
        kids = h.children.get(node, [])
        if not kids:
            memo[node] = 1
            return 1
        d = 1 + max(depth(c, seen | {node}) for c in kids)
        memo[node] = d
        return d

    if not h.roots:
        return 0
    return max(depth(r, frozenset()) for r in h.roots)
