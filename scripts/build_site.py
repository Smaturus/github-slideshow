#!/usr/bin/env python3
"""Generate family archive website from GEDCOM export and content/content.yaml."""

from __future__ import annotations

import html
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from collections import Counter

from parse_gedcom import (
    Family,
    Person,
    canonical_place,
    counted,
    direct_lines,
    format_date,
    genitive_given_name,
    parse_gedcom,
    plural,
    stats,
    year_only,
)

ROOT_ID = "@I1@"
ROOT = Path(__file__).resolve().parents[1]
GEDCOM_PATH = ROOT / "data" / "skiba.ged"
CONTENT_PATH = ROOT / "content" / "content.yaml"
OUTPUT_PATH = ROOT / "index.html"
CSS = ROOT / "assets" / "site.css"

STATUS_BADGE_W = {"ok": 100, "hyp": 74, "q": 86}
BADGE_H = 16

BOX_W = 214
BOX_H = 78
COL_W = 242
ROW_H = 92
TOP_PAD = 56
LEFT_PAD = 18

# Hero constellation: an ethereal branching crystal on a near-black field.
# The silhouette is hand-authored as primary ridges (luminous polylines that
# braid and fork like lightning); everything else — twigs, facets, the far
# lattice — is grown procedurally around those ridges from a fixed seed.
HERO_VIEW_W = 780
HERO_VIEW_H = 720
# Fixed seed keeps the generated crystal identical between builds.
HERO_SEED = 1834
# Primary ridges. Each polyline starts on an earlier ridge, so the structure
# reads as one growing body: A is the trunk, B/C/D/E/F fork off it, G braids
# across the top, H/I close loops, and the short arms fray the outline.
HERO_RIDGES = [
    # A — trunk, from the lower left up to the newest generation top right
    [(352, 690), (378, 628), (340, 564), (392, 498), (372, 432), (436, 372),
     (470, 306), (508, 240), (556, 176), (612, 132), (686, 96)],
    # B — upper-left limb
    [(436, 372), (398, 330), (356, 300), (322, 246), (300, 196), (268, 150)],
    # C — long left reach down to the documentary anchor
    [(392, 498), (344, 478), (296, 462), (232, 486), (176, 516), (124, 556),
     (86, 588)],
    # D — right limb
    [(508, 240), (566, 262), (620, 272), (676, 306), (722, 346)],
    # E — right descent
    [(470, 306), (516, 352), (556, 404), (612, 468), (654, 522), (692, 570)],
    # F — lower limb
    [(378, 628), (428, 646), (486, 664), (548, 672), (596, 690)],
    # G — braid across the top
    [(556, 176), (508, 152), (452, 148), (404, 122), (352, 96), (312, 66)],
    # H — braid closing the lower-left loop
    [(232, 486), (286, 552), (352, 592), (428, 646)],
    # I — braid closing the right loop
    [(722, 346), (702, 402), (656, 438), (612, 468)],
    # short frayed arms
    [(268, 150), (222, 116), (198, 70)],
    [(340, 564), (282, 596), (238, 640), (208, 686)],
    [(620, 272), (650, 214), (694, 178), (734, 136)],
    [(556, 404), (600, 388), (652, 372)],
    [(296, 462), (262, 408), (246, 356)],
]
# Birth-year labels of the paternal line, newest first, pinned to points on the
# ridges and scattered around the crystal. The third value is the label side
# (1 = right of the node, -1 = left).
HERO_YEAR_ANCHORS = [
    (686, 96, 1),
    (452, 148, -1),
    (676, 306, 1),
    (322, 246, -1),
    (612, 468, 1),
    (296, 462, -1),
    (486, 664, 1),
]
# Documentary anchor: the 1834 revision list of Mokroe (not a birth year) sits
# at the far end of the oldest reach — Fedot, Grigory and Ilya.
HERO_ANCHOR = (124, 556, -1)
HERO_ANCHOR_LABEL = "1834"
# Nebula blooms behind the densest junctions: (cx, cy, r, opacity tier).
HERO_BLOOMS = [
    (392, 498, 168, 1),
    (470, 306, 152, 1),
    (300, 462, 132, 2),
    (556, 176, 138, 2),
    (620, 272, 120, 2),
    (428, 646, 126, 2),
    (640, 486, 108, 3),
    (330, 250, 104, 3),
]


def load_content() -> dict[str, Any]:
    """Load editorial texts from content/content.yaml."""
    with CONTENT_PATH.open(encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    validate_content(content)
    return content


def require_keys(data: dict[str, Any], path: str, keys: list[str]) -> None:
    """Fail fast with a clear error when editable YAML misses required keys."""
    missing = [key for key in keys if key not in data]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Missing required key(s) in content/content.yaml at {path}: {missing_list}")


def require_mapping(data: Any, path: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in content/content.yaml at {path}")
    return data


def require_list(data: Any, path: str, min_len: int = 0) -> list[Any]:
    if not isinstance(data, list):
        raise ValueError(f"Expected list in content/content.yaml at {path}")
    if len(data) < min_len:
        raise ValueError(
            f"Expected at least {min_len} item(s) in content/content.yaml at {path}, got {len(data)}"
        )
    return data


def require_str(data: Any, path: str) -> str:
    if not isinstance(data, str):
        raise ValueError(f"Expected string in content/content.yaml at {path}")
    return data


def validate_branch(branch: Any, path: str) -> None:
    branch = require_mapping(branch, path)
    require_keys(branch, path, ["tag", "title", "paragraphs", "mini"])
    require_list(branch["paragraphs"], f"{path}.paragraphs", min_len=1)
    require_str(branch["tag"], f"{path}.tag")
    require_str(branch["title"], f"{path}.title")
    require_str(branch["mini"], f"{path}.mini")


def validate_content(content: Any) -> None:
    """Schema checks for editor-facing YAML used by the generator."""
    content = require_mapping(content, "root")
    require_keys(
        content,
        "root",
        [
            "meta",
            "hero",
            "lines",
            "alekseevs",
            "timeline",
            "surnames",
            "places",
            "meeting",
            "sources",
            "tree",
            "footer",
        ],
    )

    meta = require_mapping(content["meta"], "meta")
    require_keys(meta, "meta", ["title", "brand", "nav_chronicle", "nav_tree"])

    hero = require_mapping(content["hero"], "hero")
    require_keys(
        hero,
        "hero",
        [
            "label_prefix",
            "h1",
            "sub",
            "cta",
            "facts_line",
            "privacy_note",
            "graph_caption_prefix",
            "stats",
        ],
    )
    hero_stats = require_mapping(hero["stats"], "hero.stats")
    require_keys(
        hero_stats,
        "hero.stats",
        ["generations", "people", "surnames", "earliest_birth", "earliest_fallback"],
    )

    lines = require_mapping(content["lines"], "lines")
    require_keys(lines, "lines", ["label", "title", "lead", "branches"])
    branches = require_mapping(lines["branches"], "lines.branches")
    for key in ("matyukhin_father", "astafyev_mother", "skiba_father", "potashkin_mother"):
        validate_branch(branches.get(key), f"lines.branches.{key}")

    alekseevs = require_mapping(content["alekseevs"], "alekseevs")
    require_keys(alekseevs, "alekseevs", ["label", "title", "lead", "tatar", "donbass"])
    validate_branch(alekseevs["tatar"], "alekseevs.tatar")
    validate_branch(alekseevs["donbass"], "alekseevs.donbass")

    timeline = require_mapping(content["timeline"], "timeline")
    require_keys(
        timeline,
        "timeline",
        ["label", "title", "lead", "generation_prefix", "generation_suffix", "place_fallback"],
    )

    surnames = require_mapping(content["surnames"], "surnames")
    require_keys(surnames, "surnames", ["label", "title", "lead", "count_suffix", "default_note", "notes"])
    require_mapping(surnames["notes"], "surnames.notes")

    places = require_mapping(content["places"], "places")
    require_keys(
        places,
        "places",
        ["label", "title", "lead", "card_tag_prefix", "default_note", "notes"],
    )
    require_mapping(places["notes"], "places.notes")

    meeting = require_mapping(content["meeting"], "meeting")
    require_keys(
        meeting,
        "meeting",
        ["label", "title", "lead_prefix", "lead_suffix", "child_fallback", "living", "source"],
    )
    require_keys(require_mapping(meeting["living"], "meeting.living"), "meeting.living", ["tag", "title", "body"])
    require_keys(
        require_mapping(meeting["source"], "meeting.source"),
        "meeting.source",
        ["tag", "title", "intro_prefix", "intro_suffix"],
    )

    sources = require_mapping(content["sources"], "sources")
    require_keys(sources, "sources", ["label", "title", "lead", "provenance", "missing", "legend", "archives"])

    provenance = require_mapping(sources["provenance"], "sources.provenance")
    require_keys(
        provenance,
        "sources.provenance",
        [
            "title",
            "gedcom_item",
            "copy_item",
            "birth_intro_prefix",
            "birth_intro_middle",
            "birth_intro_suffix",
            "birth_buckets",
        ],
    )
    require_keys(
        require_mapping(provenance["birth_buckets"], "sources.provenance.birth_buckets"),
        "sources.provenance.birth_buckets",
        ["full", "year_only", "month_year", "qualified", "qualified_note", "missing"],
    )

    missing = require_mapping(sources["missing"], "sources.missing")
    require_keys(
        missing,
        "sources.missing",
        ["title", "intro", "smart_match_suffix", "smart_match_caveat", "no_archives"],
    )

    legend = require_mapping(sources["legend"], "sources.legend")
    require_keys(legend, "sources.legend", ["title", "hypothesis", "calculated_dates", "dashed_card"])

    archives = require_mapping(sources["archives"], "sources.archives")
    require_keys(
        archives,
        "sources.archives",
        ["title", "mokroe", "valday", "chistopol", "slavyanoserbsk", "khimki"],
    )

    tree = require_mapping(content["tree"], "tree")
    require_keys(
        tree,
        "tree",
        [
            "label",
            "h1",
            "lead",
            "stats",
            "column_titles",
            "status",
            "missing_father",
            "missing_mother",
            "legend",
            "goals",
            "generation_names",
            "generation_fallback_suffix",
        ],
    )
    require_keys(require_mapping(tree["stats"], "tree.stats"), "tree.stats", ["with_parents", "search_goals"])
    require_list(tree["column_titles"], "tree.column_titles", min_len=6)
    require_keys(require_mapping(tree["status"], "tree.status"), "tree.status", ["ok", "hyp", "q"])
    require_keys(
        require_mapping(tree["legend"], "tree.legend"),
        "tree.legend",
        ["ok", "hyp", "q", "anchor"],
    )
    goals = require_mapping(tree["goals"], "tree.goals")
    require_keys(
        goals,
        "tree.goals",
        [
            "label",
            "title",
            "lead",
            "title_prefix",
            "line_suffix",
            "hint_known_place_prefix",
            "hint_known_place_suffix",
            "hint_unknown_place",
            "status_suffix",
        ],
    )
    require_mapping(tree["generation_names"], "tree.generation_names")
    require_str(tree["generation_fallback_suffix"], "tree.generation_fallback_suffix")

    footer = require_mapping(content["footer"], "footer")
    require_keys(footer, "footer", ["brand", "middle", "suffix"])


def esc(text: str) -> str:
    return html.escape((text or "").rstrip(), quote=True)


def rich(text: str) -> str:
    """Trusted HTML from content.yaml (bold tags, spans)."""
    return (text or "").strip()


def paragraphs_html(paragraphs: list[str]) -> str:
    return "".join(f"<p>{rich(paragraph)}</p>" for paragraph in paragraphs)


def chain_text(people: list[Person]) -> str:
    return " → ".join(
        f"<b>{esc(p.surname)} {esc(p.name.split()[0] if p.name else '')}</b> ({esc(p.public_years)})"
        for p in people
    )


def count_generations(pid: str, people: dict[str, Person], families: dict[str, Family]) -> int:
    depth = 0
    current = pid
    while current in people and people[current].famc in families:
        depth += 1
        family = families[people[current].famc]
        parent = family.husb or family.wife
        if not parent:
            break
        current = parent
    return depth


def missing_parent_goals(
    root_ids: list[str],
    people: dict[str, Person],
    families: dict[str, Family],
    limit: int = 9,
) -> list[tuple[Person, int]]:
    """Gaps in the direct ancestor line only — closest generations first.

    One entry per person, whether the father, the mother or both are unknown.
    """
    goals: list[tuple[Person, int]] = []
    seen: set[str] = set()

    def walk(pid: str, depth: int) -> None:
        if pid in seen or pid not in people:
            return
        seen.add(pid)
        person = people[pid]
        family = families.get(person.famc) if person.famc else None

        if family is None:
            if depth > 0:
                goals.append((person, depth))
            return

        if not family.husb or not family.wife:
            goals.append((person, depth))

        for parent in (family.husb, family.wife):
            if parent:
                walk(parent, depth + 1)

    for root_id in root_ids:
        walk(root_id, 0)

    goals.sort(key=lambda item: (item[1], item[0].surname))
    return goals[:limit]


def generation_names(content: dict[str, Any]) -> dict[int, str]:
    raw = content["tree"]["generation_names"]
    return {int(key): value for key, value in raw.items()}


def status_labels(content: dict[str, Any]) -> dict[str, str]:
    return content["tree"]["status"]


def column_titles(content: dict[str, Any]) -> list[str]:
    return content["tree"]["column_titles"]


class TreeNode:
    """One slot in the ancestor chart; person is None when the ancestor is unknown."""

    def __init__(self, person: Person | None, gen: int, placeholder: str = ""):
        self.person = person
        self.gen = gen
        self.placeholder = placeholder
        self.children: list[TreeNode] = []
        self.y: float = 0.0

    @property
    def is_missing(self) -> bool:
        return self.person is None


def build_ancestor_tree(
    pid: str | None,
    people: dict[str, Person],
    families: dict[str, Family],
    content: dict[str, Any],
    max_gen: int,
    gen: int = 0,
    placeholder: str = "",
) -> TreeNode:
    person = people.get(pid) if pid else None
    node = TreeNode(person, gen, placeholder)

    if gen >= max_gen or person is None:
        return node

    family = families.get(person.famc) if person.famc else None
    if family is None:
        return node

    # Only draw an unknown-parent slot when at least one parent is known,
    # otherwise the chart fills up with empty pairs.
    if not family.husb and not family.wife:
        return node

    node.children.append(
        build_ancestor_tree(
            family.husb, people, families, content, max_gen, gen + 1, content["tree"]["missing_father"]
        )
    )
    node.children.append(
        build_ancestor_tree(
            family.wife, people, families, content, max_gen, gen + 1, content["tree"]["missing_mother"]
        )
    )
    return node


def assign_positions(node: TreeNode, cursor: list[float]) -> float:
    """Leaves stack top-down; parents centre on their children."""
    if not node.children:
        node.y = cursor[0]
        cursor[0] += ROW_H
        return node.y

    child_ys = [assign_positions(child, cursor) for child in node.children]
    node.y = (child_ys[0] + child_ys[-1]) / 2
    return node.y


def collect_nodes(node: TreeNode, acc: list[TreeNode]) -> None:
    acc.append(node)
    for child in node.children:
        collect_nodes(child, acc)


def render_connectors(node: TreeNode, max_gen: int) -> list[str]:
    """Draw the bracket between a person and their two parents."""
    if not node.children:
        return []

    out: list[str] = []
    x_right = LEFT_PAD + node.gen * COL_W + BOX_W
    x_mid = x_right + (COL_W - BOX_W) / 2
    x_parent = LEFT_PAD + (node.gen + 1) * COL_W
    tops = [child.y for child in node.children]

    out.append(f'<path class="ln" d="M{x_right} {node.y:.1f} H{x_mid:.1f}"/>')
    out.append(f'<path class="ln" d="M{x_mid:.1f} {min(tops):.1f} V{max(tops):.1f}"/>')
    for child in node.children:
        out.append(f'<path class="ln" d="M{x_mid:.1f} {child.y:.1f} H{x_parent}"/>')
        out.extend(render_connectors(child, max_gen))
    return out


def render_badge(x: float, cy: float, status: str, labels: dict[str, str]) -> str:
    """Status pill in the lower-left corner of a tree card."""
    width = STATUS_BADGE_W[status]
    return (
        f'<rect class="bg" x="{x + 12}" y="{cy + 18:.1f}" width="{width}" '
        f'height="{BADGE_H}" rx="{BADGE_H / 2}"/>'
        f'<text class="bdg" x="{x + 12 + width / 2:.1f}" y="{cy + 29.4:.1f}" '
        f'text-anchor="middle">{esc(labels[status])}</text>'
    )


def render_person_box(x: float, cy: float, person: Person, extra: list[str], labels: dict[str, str]) -> str:
    status = "hyp" if person.is_reconstructed else "ok"
    surname = person.surname or person.name
    given = person.name if person.surname else ""
    years = person.public_years.replace("р. ", "").replace("ум. ", "† ")
    if years == "? – ?":
        years = ""

    return (
        f'<g class="{" ".join(["bx", status, *extra])}">'
        f'<rect class="fr" x="{x}" y="{cy - BOX_H / 2:.1f}" width="{BOX_W}" height="{BOX_H}" rx="10"/>'
        f'<text class="t1" x="{x + 12}" y="{cy - 22:.1f}">{esc(surname)}</text>'
        f'<text class="t2" x="{x + 12}" y="{cy - 5:.1f}">{esc(given)}</text>'
        f'<text class="t3" x="{x + 12}" y="{cy + 13:.1f}">{esc(years)}</text>'
        f'{render_badge(x, cy, status, labels)}</g>'
    )


def render_box(node: TreeNode, labels: dict[str, str]) -> str:
    x = LEFT_PAD + node.gen * COL_W

    if node.is_missing:
        return (
            f'<g class="bx q">'
            f'<rect class="fr" x="{x}" y="{node.y - BOX_H / 2:.1f}" '
            f'width="{BOX_W}" height="{BOX_H}" rx="10"/>'
            f'<text class="t1" x="{x + 12}" y="{node.y - 22:.1f}">—</text>'
            f'<text class="t2" x="{x + 12}" y="{node.y - 5:.1f}">{esc(node.placeholder)}</text>'
            f'{render_badge(x, node.y, "q", labels)}</g>'
        )

    person = node.person
    assert person is not None
    extra: list[str] = []
    if node.gen == 0:
        extra.append("me")
    elif not node.children and person.birt and not person.is_reconstructed:
        extra.append("deep")

    return render_person_box(x, node.y, person, extra, labels)


def render_pedigree_svg(
    root: Person,
    spouse: Person,
    child: Person | None,
    people: dict[str, Person],
    families: dict[str, Family],
    content: dict[str, Any],
    max_gen: int = 4,
) -> str:
    """Two stacked ancestor charts: the husband's line above, the wife's below."""
    labels = status_labels(content)
    titles = column_titles(content)
    father_tree = build_ancestor_tree(root.id, people, families, content, max_gen)
    mother_tree = build_ancestor_tree(spouse.id, people, families, content, max_gen)

    cursor = [TOP_PAD + BOX_H / 2]
    assign_positions(father_tree, cursor)
    cursor[0] += ROW_H * 1.5
    assign_positions(mother_tree, cursor)

    nodes: list[TreeNode] = []
    collect_nodes(father_tree, nodes)
    collect_nodes(mother_tree, nodes)

    parts: list[str] = []
    for index, title in enumerate(titles[: max_gen + 1]):
        parts.append(f'<text x="{LEFT_PAD + index * COL_W}" y="26" class="colhead">{esc(title)}</text>')

    parts.extend(render_connectors(father_tree, max_gen))
    parts.extend(render_connectors(mother_tree, max_gen))

    # Marriage bracket joining the two root people.
    x_mid = LEFT_PAD - 6
    parts.append(
        f'<path class="ln" d="M{x_mid} {father_tree.y:.1f} V{mother_tree.y:.1f}"/>'
        f'<path class="ln" d="M{x_mid} {father_tree.y:.1f} H{LEFT_PAD}"/>'
        f'<path class="ln" d="M{x_mid} {mother_tree.y:.1f} H{LEFT_PAD}"/>'
    )
    if child:
        y_child = (father_tree.y + mother_tree.y) / 2
        parts.append(f'<path class="ln" d="M{x_mid} {y_child:.1f} H{LEFT_PAD}"/>')
        parts.append(render_person_box(LEFT_PAD, y_child, child, ["me"], labels))

    for node in nodes:
        parts.append(render_box(node, labels))

    width = LEFT_PAD * 2 + (max_gen + 1) * COL_W
    height = max(node.y for node in nodes) + ROW_H

    return (
        f'<svg class="pedigree" viewBox="0 0 {width} {height:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg" style="min-width:{width}px">'
        + "".join(parts)
        + "</svg>"
    )


def line_branch_card(branch: dict[str, Any], chain: str) -> str:
    body = paragraphs_html(branch["paragraphs"])
    return (
        f'<div class="card"><div class="tag">{esc(branch["tag"])}</div>'
        f'<h3>{esc(branch["title"])}</h3>'
        f'<p>{chain}</p>{body}'
        f'<div class="mini">{esc(branch["mini"])}</div></div>\n      '
    )


def alekseev_card(branch: dict[str, Any]) -> str:
    body = paragraphs_html(branch["paragraphs"])
    return (
        f'<div class="card"><div class="tag">{esc(branch["tag"])}</div>'
        f'<h3>{esc(branch["title"])}</h3>{body}'
        f'<div class="mini">{esc(branch["mini"])}</div></div>'
    )


@dataclass(frozen=True)
class FamilyContext:
    """Root person, spouse and first child used across page sections."""

    root: Person
    spouse: Person
    child: Person | None


def resolve_family_context(
    people: dict[str, Person],
    families: dict[str, Family],
) -> FamilyContext:
    """Resolve the focal family from ROOT_ID."""
    root = people[ROOT_ID]
    spouse_fam = families[root.fams[0]]
    spouse_id = spouse_fam.wife if spouse_fam.husb == ROOT_ID else spouse_fam.husb
    spouse = people[spouse_id]
    children = [people[c] for c in spouse_fam.chil if c in people]
    child = children[0] if children else None
    return FamilyContext(root=root, spouse=spouse, child=child)


def merged_places(people: dict[str, Person]) -> Counter[str]:
    """Aggregate canonical place names from deceased persons."""
    counts: Counter[str] = Counter()
    for person in people.values():
        if person.is_living:
            continue
        for raw_place in (person.birt_plac, person.deat_plac):
            raw_place = raw_place.strip()
            if raw_place and raw_place not in {"Россия", "Украина"}:
                counts[canonical_place(raw_place)] += 1
    return counts


def build_places_html(places_content: dict[str, Any], place_counts: Counter[str]) -> str:
    """Render geography cards from aggregated place counts."""
    place_notes = places_content["notes"]
    place_default = places_content["default_note"]
    return "".join(
        f'<div class="card"><div class="tag">{esc(places_content["card_tag_prefix"])} '
        f'{counted(count, ("запись", "записи", "записей"))}</div><h4>{esc(place)}</h4>'
        f'<p>{esc(place_notes.get(place, place_default))}</p></div>'
        for place, count in place_counts.most_common(9)
    )


def build_surnames_html(surnames_content: dict[str, Any], top_surnames: list[tuple[str, int]]) -> str:
    """Render surname frequency cards."""
    surname_notes = surnames_content["notes"]
    surname_default = surnames_content["default_note"]
    return "".join(
        f'<div class="card"><h4>{esc(name)}</h4>'
        f'<p>{esc(surname_notes.get(name, surname_default))}</p>'
        f'<div class="mini">{counted(count, ("носитель", "носителя", "носителей"))} {esc(surnames_content["count_suffix"])}</div></div>'
        for name, count in top_surnames[:10]
    )


def build_timeline_html(
    timeline_content: dict[str, Any],
    timeline_people: list[Person],
    root_id: str,
) -> str:
    """Render generation timeline items."""
    timeline_html = ""
    for i, person in enumerate(timeline_people):
        me = " me" if person.id == root_id else ""
        timeline_html += f"""
      <div class="tl-item{me}">
        <div class="tl-gen">{esc(timeline_content["generation_prefix"])} {len(timeline_people) - i} {esc(timeline_content["generation_suffix"])}</div>
        <h3>{esc(person.label)}</h3>
        <div class="yrs">{esc(person.public_years)}</div>
        <p>{esc(person.public_place or timeline_content["place_fallback"])}</p>
      </div>"""
    return timeline_html


def build_goals_html(
    tree: dict[str, Any],
    goals: list[tuple[Person, int]],
    gen_names: dict[int, str],
) -> str:
    """Render search-goal rows for missing ancestors."""
    goals_text = tree["goals"]
    goals_html = ""
    for i, (person, depth) in enumerate(goals, 1):
        generation = gen_names.get(depth, f"{depth}{tree['generation_fallback_suffix']}")
        place = person.public_place
        if place:
            hint = (
                f'{goals_text["hint_known_place_prefix"]} {place}: '
                f'{goals_text["hint_known_place_suffix"]}'
            )
        else:
            hint = goals_text["hint_unknown_place"]
        goals_html += f"""
        <div class="goalrow"><div class="n">{i}</div><div>
          <b>{esc(goals_text["title_prefix"])} {esc(person.display_name)}</b>
          <p>{esc(person.public_years)} · {esc(generation)} {esc(goals_text["line_suffix"])} {esc(hint)}</p>
          <div class="st">{esc(generation.capitalize())} {esc(goals_text["status_suffix"])}</div>
        </div></div>"""
    return goals_html


def hero_graph_years(line: list[Person]) -> list[tuple[str, bool]]:
    """Birth years of the paternal line for the hero lattice: (year, is_approximate).

    Only year precision is used, so the entry for a living root person stays
    within the privacy policy (same as public_years).
    """
    years: list[tuple[str, bool]] = []
    for person in line:
        year = year_only(person.birt)
        if not year:
            continue
        years.append((year, person.has_derived_date))
        if len(years) == len(HERO_YEAR_ANCHORS):
            break
    return years


def hero_graph_caption(hero: dict[str, Any], years: list[tuple[str, bool]]) -> str:
    """Factual caption under the lattice: 'Отцовская линия…, ок. 1768 — 1971'."""
    prefix = hero["graph_caption_prefix"]
    if not years:
        return prefix
    newest = years[0][0]
    oldest_year, oldest_approx = years[-1]
    oldest = f"ок. {oldest_year}" if oldest_approx else oldest_year
    return f"{prefix} {oldest} — {newest}"


Limb = tuple[list[tuple[float, float]], int]


def _reflect_inside(
    x: float, y: float, angle: float, margin: float = 22.0
) -> tuple[float, float, float]:
    """Bounce a growth direction off the viewBox margins so twigs stay inside."""
    if x < margin:
        x, angle = margin, math.pi - angle
    elif x > HERO_VIEW_W - margin:
        x, angle = HERO_VIEW_W - margin, math.pi - angle
    if y < margin:
        y, angle = margin, -angle
    elif y > HERO_VIEW_H - margin:
        y, angle = HERO_VIEW_H - margin, -angle
    return x, y, angle


def _grow_branch(
    rng: random.Random,
    x: float,
    y: float,
    angle: float,
    length: float,
    depth: int,
    out: list[Limb],
) -> None:
    """Grow one kinked branch off the skeleton and fork it recursively.
    Depth 1 sits directly on a primary ridge, deeper levels are twigs."""
    steps = 3 if depth == 1 else 2
    pts = [(round(x, 1), round(y, 1))]
    for _ in range(steps):
        angle += rng.uniform(-0.3, 0.3)
        step = length / steps
        x, y, angle = _reflect_inside(
            x + math.cos(angle) * step, y + math.sin(angle) * step, angle
        )
        pts.append((round(x, 1), round(y, 1)))
    out.append((pts, depth))
    if depth >= 2:
        return
    for _ in range(2 if rng.random() < 0.4 else 1):
        if rng.random() < 0.24:
            continue
        side = 1 if rng.random() < 0.5 else -1
        _grow_branch(
            rng,
            x,
            y,
            angle + side * rng.uniform(0.4, 1.05),
            length * rng.uniform(0.52, 0.74),
            depth + 1,
            out,
        )


def _hero_limbs(rng: random.Random) -> list[Limb]:
    """Full skeleton of the crystal: the hand-authored primary ridges (depth 0)
    plus the branches and twigs grown off them (depth 1–3)."""
    limbs: list[Limb] = [(list(ridge), 0) for ridge in HERO_RIDGES]
    for ridge in HERO_RIDGES:
        for (x1, y1), (x2, y2) in zip(ridge, ridge[1:]):
            base = math.atan2(y2 - y1, x2 - x1)
            for _ in range(2):
                if rng.random() > 0.58:
                    continue
                t = rng.uniform(0.12, 0.9)
                side = 1 if rng.random() < 0.5 else -1
                _grow_branch(
                    rng,
                    x1 + (x2 - x1) * t,
                    y1 + (y2 - y1) * t,
                    base + side * rng.uniform(0.45, 1.25),
                    rng.uniform(34, 82),
                    1,
                    limbs,
                )
    return limbs


class _SkeletonField:
    """Grid of samples along the skeleton, for fast approximate distance from
    any point to the nearest ridge or twig. Drives every density decision:
    which facets survive, how bright an edge is, where the veil thins out."""

    CELL = 22.0

    def __init__(self, limbs: list[Limb]) -> None:
        self.grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
        for pts, _ in limbs:
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / 6))
                for i in range(steps + 1):
                    t = i / steps
                    sx, sy = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    key = (int(sx // self.CELL), int(sy // self.CELL))
                    self.grid.setdefault(key, []).append((sx, sy))

    def dist(self, x: float, y: float, rings: int = 4) -> float:
        cx, cy = int(x // self.CELL), int(y // self.CELL)
        best = math.inf
        for ring in range(rings + 1):
            for gx in range(cx - ring, cx + ring + 1):
                for gy in range(cy - ring, cy + ring + 1):
                    if ring and max(abs(gx - cx), abs(gy - cy)) != ring:
                        continue
                    for px, py in self.grid.get((gx, gy), ()):
                        best = min(best, (px - x) ** 2 + (py - y) ** 2)
            if best <= (ring * self.CELL) ** 2:
                break
        return math.sqrt(best) if best < math.inf else math.inf


def _hero_facet_points(rng: random.Random, limbs: list[Limb]) -> list[tuple[float, float]]:
    """Facet vertices sown along the skeleton — never over the whole frame — so
    the triangulated body follows the branching silhouette instead of filling a
    hull. Reach falls with branch depth: wide panes hug the trunk, fine chips
    cling to the twigs."""
    cell = 18.0
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    pts: list[tuple[float, float]] = []

    def place(x: float, y: float, min_d: float) -> None:
        if not (14 <= x <= HERO_VIEW_W - 14 and 18 <= y <= HERO_VIEW_H - 14):
            return
        gx, gy = int(x // cell), int(y // cell)
        for ax in range(gx - 1, gx + 2):
            for ay in range(gy - 1, gy + 2):
                for px, py in grid.get((ax, ay), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < min_d**2:
                        return
        grid.setdefault((gx, gy), []).append((x, y))
        pts.append((round(x, 1), round(y, 1)))

    reach_by_depth = (25.0, 17.0, 11.0, 9.0)
    for poly, depth in limbs:
        for px, py in poly:
            place(px, py, 10.0)
        # Per-limb jitter keeps facet size uneven: chunky panes along one limb,
        # fine chips along the next.
        reach = reach_by_depth[min(depth, 3)] * rng.uniform(0.72, 1.3)
        min_d = rng.uniform(12.0, 18.0)
        for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
            seg = math.hypot(x2 - x1, y2 - y1) or 1.0
            nx, ny = -(y2 - y1) / seg, (x2 - x1) / seg
            stations = max(1, int(seg / 13))
            for i in range(stations):
                t = (i + rng.uniform(0.2, 0.8)) / stations
                bx, by = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                for _ in range(2):
                    off = rng.uniform(6, reach) * (1 if rng.random() < 0.5 else -1)
                    place(bx + nx * off + rng.uniform(-3, 3), by + ny * off + rng.uniform(-3, 3), min_d)
    return pts


def _hero_veil(
    rng: random.Random, field: _SkeletonField
) -> tuple[list[tuple[float, float, int]], list[tuple[float, float, float, float, bool]]]:
    """Far field: a dotted micro-lattice and long hairline edges that fade out
    of the black. Density decays exponentially with distance from the skeleton,
    so the crystal keeps an atmosphere instead of a hard edge."""
    dots: list[tuple[float, float, int]] = []
    for _ in range(4200):
        if len(dots) >= 420:
            break
        x = rng.uniform(24, HERO_VIEW_W - 20)
        y = rng.uniform(22, HERO_VIEW_H - 18)
        dist = field.dist(x, y, rings=7)
        if dist > 170 or rng.random() > math.exp(-dist / 74):
            continue
        dots.append((round(x, 1), round(y, 1), 1 if dist < 62 else 2))

    lines: list[tuple[float, float, float, float, bool]] = []
    attempts = 0
    while len(lines) < 96 and attempts < 2600:
        attempts += 1
        (x1, y1, _), (x2, y2, _) = rng.choice(dots), rng.choice(dots)
        span = math.hypot(x2 - x1, y2 - y1)
        if not 58 <= span <= 210:
            continue
        lines.append((x1, y1, x2, y2, rng.random() < 0.45))
    return dots, lines


def _delaunay(points: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    """Deterministic Bowyer–Watson Delaunay triangulation (pure Python,
    O(n²) insertion — fine for the ~150 hero vertices). Returns sorted
    vertex-index triples with super-triangle faces removed."""
    n = len(points)
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    span = max(max_x - min_x, max_y - min_y) or 1.0
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    verts = list(points) + [
        (mid_x - 20 * span, mid_y - 10 * span),
        (mid_x + 20 * span, mid_y - 10 * span),
        (mid_x, mid_y + 20 * span),
    ]

    def circumcircle(tri: tuple[int, int, int]) -> tuple[float, float, float]:
        (ax, ay), (bx, by), (cx, cy) = (verts[v] for v in tri)
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-9:  # collinear: infinite circle, always invalidated
            return (0.0, 0.0, float("inf"))
        a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
        ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
        uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
        return (ux, uy, (ax - ux) ** 2 + (ay - uy) ** 2)

    first = (n, n + 1, n + 2)
    tris: dict[tuple[int, int, int], tuple[float, float, float]] = {first: circumcircle(first)}
    for i in range(n):
        px, py = verts[i]
        bad = [t for t, (ux, uy, r2) in tris.items() if (px - ux) ** 2 + (py - uy) ** 2 <= r2]
        boundary: Counter = Counter()
        for a, b, c in bad:
            for edge in ((a, b), (b, c), (a, c)):
                boundary[edge] += 1
            del tris[(a, b, c)]
        for (a, b), count in boundary.items():
            if count == 1:
                tri = tuple(sorted((a, b, i)))
                tris[tri] = circumcircle(tri)
    return sorted(t for t in tris if all(v < n for v in t))


def _hero_defs() -> str:
    """Gradients and blur filters for the blooms and the ridge glow."""
    return (
        "<defs>"
        '<radialGradient id="lat-bloom">'
        '<stop offset="0" stop-color="#9A8CD8" stop-opacity=".42"/>'
        '<stop offset=".45" stop-color="#7466B4" stop-opacity=".16"/>'
        '<stop offset="1" stop-color="#5B4E96" stop-opacity="0"/>'
        "</radialGradient>"
        '<linearGradient id="lat-pane" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#DCD5FF" stop-opacity=".17"/>'
        '<stop offset="1" stop-color="#A497DE" stop-opacity=".015"/>'
        "</linearGradient>"
        '<filter id="lat-soft" x="-70%" y="-70%" width="240%" height="240%">'
        '<feGaussianBlur stdDeviation="3.2"/>'
        "</filter>"
        '<filter id="lat-wide" x="-90%" y="-90%" width="280%" height="280%">'
        '<feGaussianBlur stdDeviation="13"/>'
        "</filter>"
        # The mesh and the far field dissolve towards the periphery, so the
        # crystal has no hard outline — only the ridges stay crisp to the tips.
        '<radialGradient id="lat-fade">'
        '<stop offset=".42" stop-color="#fff" stop-opacity="1"/>'
        '<stop offset=".74" stop-color="#fff" stop-opacity=".62"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        "</radialGradient>"
        '<mask id="lat-mask">'
        f'<ellipse cx="{HERO_VIEW_W * 0.52:.0f}" cy="{HERO_VIEW_H * 0.53:.0f}" '
        f'rx="{HERO_VIEW_W * 0.62:.0f}" ry="{HERO_VIEW_H * 0.58:.0f}" fill="url(#lat-fade)"/>'
        "</mask>"
        "</defs>"
    )


def _path_d(poly: list[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x} {y}" for x, y in poly)


def render_hero_graph(years: list[tuple[str, bool]], caption: str) -> str:
    """Ethereal crystalline constellation. Four layers of depth on the black
    field: nebula blooms, a dotted far lattice fading out, a mid layer of
    mostly unfilled glass facets with interrupted edges, and near luminous
    ridges braiding through the structure — with pinpoint lights at the
    junctions and the documented years of the paternal line floating around
    the periphery."""
    rng = random.Random(HERO_SEED)
    limbs = _hero_limbs(rng)
    field = _SkeletonField(limbs)
    points = _hero_facet_points(rng, limbs)
    veil_dots, veil_lines = _hero_veil(rng, field)

    # Facets survive only near the skeleton, and only if they are compact —
    # so the mesh is a branching crystal, not a triangulated hull.
    faces: list[tuple[tuple[int, int, int], float]] = []
    for tri in _delaunay(points):
        (x1, y1), (x2, y2), (x3, y3) = (points[v] for v in tri)
        longest = max(
            math.hypot(x1 - x2, y1 - y2),
            math.hypot(x2 - x3, y2 - y3),
            math.hypot(x1 - x3, y1 - y3),
        )
        area = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2
        dist = field.dist((x1 + x2 + x3) / 3, (y1 + y2 + y3) / 3)
        if dist > 24 or longest > 54 or area < 28:
            continue
        faces.append((tri, dist))

    blooms: list[str] = []
    veil: list[str] = []
    facets: list[str] = []
    filaments: list[str] = []
    ridges: list[str] = []
    sparks: list[str] = []
    labels: list[str] = []

    # 1. Atmosphere: nebula blooms behind the densest junctions.
    for cx, cy, radius, tier in HERO_BLOOMS:
        blooms.append(f'<circle class="bloom b{tier}" cx="{cx}" cy="{cy}" r="{radius}"/>')

    # 2. Far field: hairline edges and a dotted micro-lattice, barely there.
    for x1, y1, x2, y2, dashed in veil_lines:
        cls = "vl vl-dash" if dashed else "vl"
        veil.append(f'<line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
    for x, y, tier in veil_dots:
        veil.append(f'<circle class="vp p{tier}" cx="{x}" cy="{y}" r="{0.9 if tier == 1 else 0.7}"/>')

    # 3. Mid field: glass panes. Most facets stay void — only a minority get a
    # wash, in three intensity tiers, brightest close to the ridges.
    fills: dict[str, list[str]] = {"f3": [], "f2": [], "f1": [], "pane": []}
    for tri, dist in faces:
        roll = rng.random()
        if dist < 10:
            cls = "pane" if roll < 0.1 else "f1" if roll < 0.28 else None
        elif dist < 18:
            cls = "f1" if roll < 0.04 else "f2" if roll < 0.2 else None
        else:
            cls = "f3" if roll < 0.14 else None
        if cls is None:
            continue
        pts_attr = " ".join(f"{points[v][0]},{points[v][1]}" for v in tri)
        fills[cls].append(f'<polygon class="face {cls}" points="{pts_attr}"/>')
    for key in ("f3", "f2", "f1", "pane"):
        facets.extend(fills[key])

    # 4. Facet edges. Brightness follows the distance from the ridges and a
    # large share is interrupted, so the mesh flickers instead of reading as
    # a continuous wireframe.
    edge_dist: dict[tuple[int, int], float] = {}
    for tri, dist in faces:
        a, b, c = tri
        for edge in ((a, b), (b, c), (a, c)):
            edge_dist[edge] = min(edge_dist.get(edge, math.inf), dist)
    edges: dict[str, list[str]] = {"e3": [], "e2": [], "e1": []}
    for (i, j), dist in edge_dist.items():
        tier = "e1" if dist < 9 else "e2" if dist < 17 else "e3"
        # Whole edges go missing, so the facets read as chipped glass rather
        # than a complete wireframe net.
        keep = 0.9 if tier == "e1" else 0.66 if tier == "e2" else 0.44
        if rng.random() > keep:
            continue
        (x1, y1), (x2, y2) = points[i], points[j]
        cls = f"eg {tier}"
        if rng.random() < (0.24 if tier == "e1" else 0.5):
            cls += " d1" if rng.random() < 0.55 else " d2"
        edges[tier].append(f'<line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
    for tier in ("e3", "e2", "e1"):
        facets.extend(edges[tier])

    # 5. Twigs and branches: thin filaments, many of them interrupted.
    for poly, depth in limbs:
        if depth == 0:
            continue
        cls = "br b-near" if depth == 1 else "br b-far"
        if rng.random() < (0.3 if depth == 1 else 0.5):
            cls += " d1" if rng.random() < 0.5 else " d2"
        filaments.append(f'<path class="{cls}" d="{_path_d(poly)}"/>')

    # 6. Near field: the luminous ridges — a wide bloom, a tight glow and a
    # crisp near-white core, so the paths braid through the crystal. The trunk
    # and its main limbs (k1) burn brightest, the braids (k2) and the frayed
    # arms (k3) fall back into the mesh.
    ridge_tiers = [(i, 1 if i < 6 else 2 if i < 9 else 3) for i in range(len(HERO_RIDGES))]
    ridge_paths = [_path_d(list(ridge)) for ridge in HERO_RIDGES]
    # Part of the fainter ridges is interrupted, like a light path breaking up.
    dashed_ridges = {i for i, tier in ridge_tiers if tier > 1 and rng.random() < 0.5}
    for layer, extra in (
        ("rg-wide", ' filter="url(#lat-wide)"'),
        ("rg-soft", ' filter="url(#lat-soft)"'),
        ("rg-core", ""),
    ):
        for i, tier in ridge_tiers:
            cls = f"rg {layer} k{tier}"
            attrs = extra
            if layer == "rg-core":
                if i in dashed_ridges:
                    cls += " rg-dash"
                else:
                    attrs = ' pathLength="1"'
            ridges.append(f'<path class="{cls}" d="{ridge_paths[i]}"{attrs}/>')

    # 7. Pinpoint lights: dim sparks on the twigs, brighter ones on the ridge
    # junctions, a handful of hot cores with a bloom.
    label_pts = {(x, y) for x, y, _ in HERO_YEAR_ANCHORS} | {HERO_ANCHOR[:2]}
    twig_tips = [poly[-1] for poly, depth in limbs if depth >= 2]
    for x, y in rng.sample(twig_tips, min(46, len(twig_tips))):
        sparks.append(f'<circle class="nd dim" cx="{x}" cy="{y}" r="0.9"/>')
    # Pinpoint lights strung along the ridges themselves, between the junctions.
    for ridge in HERO_RIDGES:
        for (x1, y1), (x2, y2) in zip(ridge, ridge[1:]):
            span = math.hypot(x2 - x1, y2 - y1)
            for _ in range(max(1, int(span / 34))):
                if rng.random() < 0.32:
                    continue
                t = rng.uniform(0.18, 0.82)
                sx, sy = round(x1 + (x2 - x1) * t, 1), round(y1 + (y2 - y1) * t, 1)
                radius = 1.5 if rng.random() < 0.3 else 1.0
                sparks.append(f'<circle class="nd" cx="{sx}" cy="{sy}" r="{radius}"/>')
    ridge_verts = sorted({p for ridge in HERO_RIDGES for p in ridge if p not in label_pts})
    hot = set(rng.sample(ridge_verts, min(13, len(ridge_verts))))
    # Soft halos sit in the bloom layer under the brightest junctions.
    for x, y in sorted(hot | label_pts):
        blooms.append(f'<circle class="bloom bn" cx="{x}" cy="{y}" r="{rng.choice((28, 34, 42))}"/>')
    for x, y in ridge_verts:
        if (x, y) in hot:
            sparks.append(f'<circle class="nd hot" cx="{x}" cy="{y}" r="2.5"/>')
        else:
            sparks.append(f'<circle class="nd" cx="{x}" cy="{y}" r="1.5"/>')

    # 8. Year labels floating around the periphery of the crystal, each pinned
    # to a ridge junction by a hairline tick. Approximate years keep a hollow
    # node; the 1834 revision list is a dashed documentary ring.
    def pin(x: float, y: float, side: int, text: str, node_class: str, radius: float) -> None:
        labels.append(f'<circle class="{node_class}" cx="{x}" cy="{y}" r="{radius}"/>')
        labels.append(
            f'<line class="tick" x1="{x + side * (radius + 3)}" y1="{y}" '
            f'x2="{x + side * (radius + 10)}" y2="{y}"/>'
        )
        labels.append(
            f'<text class="yr" x="{x + side * (radius + 15)}" y="{y + 4.6}" '
            f'text-anchor="{"start" if side > 0 else "end"}">{esc(text)}</text>'
        )

    for (x, y, side), year in zip(HERO_YEAR_ANCHORS, years):
        value, approximate = year
        pin(
            x,
            y,
            side,
            f"ок. {value}" if approximate else value,
            "nd key approx" if approximate else "nd key",
            3.6,
        )
    ax, ay, aside = HERO_ANCHOR
    pin(ax, ay, aside, HERO_ANCHOR_LABEL, "nd key doc", 3.6)

    layers = (
        ("blooms", blooms, False),
        ("veil", veil, True),
        ("facets", facets, True),
        ("filaments", filaments, True),
        ("ridges", ridges, False),
        ("sparks", sparks, False),
        ("labels", labels, False),
    )
    body = ""
    for name, items, masked in layers:
        mask_attr = ' mask="url(#lat-mask)"' if masked else ""
        body += f'<g class="{name}"{mask_attr}>' + "".join(items) + "</g>"
    return (
        f'<svg class="lattice" viewBox="0 0 {HERO_VIEW_W} {HERO_VIEW_H}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(caption)}">'
        + _hero_defs()
        + body
        + "</svg>"
    )


def child_line_text(child: Person | None, meeting: dict[str, Any]) -> str:
    """Meeting-section suffix for the focal child, if present."""
    if child:
        return f" {esc(genitive_given_name(child.name, child.sex))} ({esc(child.public_years)})"
    return meeting["child_fallback"]


def render_document_start(meta_content: dict[str, Any], css: str) -> str:
    """HTML document preamble through opening body tag."""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(meta_content["title"])}</title>
<style>{css}</style>
</head>
<body>
"""


def render_nav(meta_content: dict[str, Any]) -> str:
    """Top navigation between chronicle and tree pages."""
    return f"""<nav>
  <div class="wrap">
    <div class="brand">{esc(meta_content["brand"])}</div>
    <button class="navbtn active" id="nb1" onclick="showPage(1)">{esc(meta_content["nav_chronicle"])}</button>
    <button class="navbtn" id="nb2" onclick="showPage(2)">{esc(meta_content["nav_tree"])}</button>
  </div>
</nav>

"""


def render_hero_section(
    hero: dict[str, Any],
    st: dict[str, Any],
    documented_gens: int,
    export_date: str,
    father_line: list[Person],
) -> str:
    """Black hero kept to the mock's composition: title over a thin lilac
    hairline, the two-line subtitle, a text-link CTA and the luminous crystal —
    nothing else. Provenance (export date), the factual sentence, key figures
    and the privacy line follow in a light facts strip below the first
    viewport; the crystal's caption lives in its aria-label."""
    years = hero_graph_years(father_line)
    caption = hero_graph_caption(hero, years)
    graph_svg = render_hero_graph(years, caption)
    return f"""<header class="hero">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <h1>{esc(hero["h1"])}</h1>
      <p class="sub">{rich(hero["sub"])}</p>
      <button class="cta-link" onclick="showPage(2)">{esc(hero["cta"])}</button>
    </div>
    <figure class="hero-graph">
      {graph_svg}
    </figure>
  </div>
  <div class="hero-fade" aria-hidden="true"></div>
</header>

<div class="facts">
  <div class="wrap">
    <div class="label">{esc(hero["label_prefix"])} {esc(export_date)} · {esc(caption)}</div>
    <p class="facts-lead">{rich(hero["facts_line"])}</p>
    <div class="stats">
      <div><b>{documented_gens}</b><span>{plural(documented_gens, ('поколение', 'поколения', 'поколений'))} {esc(hero["stats"]["generations"])}</span></div>
      <div><b>{st['people']}</b><span>{plural(st['people'], ('человек', 'человека', 'человек'))} {esc(hero["stats"]["people"])}</span></div>
      <div><b>{st['surnames']}</b><span>{esc(hero["stats"]["surnames"])}</span></div>
      <div><b>{st['earliest_year'] or esc(hero["stats"]["earliest_fallback"])}</b><span>{esc(hero["stats"]["earliest_birth"])}</span></div>
    </div>
    <p class="facts-note">{rich(hero["privacy_note"])}</p>
  </div>
</div>

"""


def render_lines_section(
    lines: dict[str, Any],
    father_line: list[Person],
    mother_line: list[Person],
    skiba_father: list[Person],
    skiba_mother: list[Person],
) -> str:
    """Four direct-line branch cards."""
    line_cards = "".join(
        line_branch_card(lines["branches"][key], chain_text(chain))
        for key, chain in (
            ("matyukhin_father", father_line[:5]),
            ("astafyev_mother", mother_line[:4]),
            ("skiba_father", skiba_father[:5]),
            ("potashkin_mother", skiba_mother[:5]),
        )
    )
    return f"""<section id="line">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(lines["label"])}</div>
      <h2>{esc(lines["title"])}</h2>
      <p>{esc(lines["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2" style="margin-bottom:44px">
      {line_cards}
    </div>
  </div>
</section>

"""


def render_alekseevs_section(alekseevs: dict[str, Any]) -> str:
    """Alekseev collateral branch cards."""
    return f"""<section>
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(alekseevs["label"])}</div>
      <h2>{esc(alekseevs["title"])}</h2>
      <p>{rich(alekseevs["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      {alekseev_card(alekseevs["tatar"])}
      {alekseev_card(alekseevs["donbass"])}
    </div>
  </div>
</section>

"""


def render_timeline_section(timeline: dict[str, Any], timeline_html: str) -> str:
    """Generation timeline section wrapper."""
    return f"""<section class="alt">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(timeline["label"])}</div>
      <h2>{esc(timeline["title"])}</h2>
      <p>{esc(timeline["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="tl">{timeline_html}
    </div>
  </div>
</section>

"""


def render_surnames_section(surnames: dict[str, Any], surnames_html: str) -> str:
    """Surname frequency section wrapper."""
    return f"""<section>
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(surnames["label"])}</div>
      <h2>{esc(surnames["title"])}</h2>
      <p>{esc(surnames["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">{surnames_html}</div>
  </div>
</section>

"""


def render_places_section(places: dict[str, Any], places_html: str) -> str:
    """Geography section wrapper."""
    return f"""<section class="alt">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(places["label"])}</div>
      <h2>{esc(places["title"])}</h2>
      <p>{esc(places["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="grid g3">{places_html}</div>
  </div>
</section>

"""


def render_meeting_section(
    meeting: dict[str, Any],
    root: Person,
    spouse: Person,
    child_suffix: str,
    export_date: str,
    st: dict[str, Any],
) -> str:
    """Marriage meeting point and living-family cards."""
    return f"""<section>
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(meeting["label"])}</div>
      <h2>{esc(meeting["title"])}</h2>
      <p>{rich(meeting["lead_prefix"])} <b>{esc(root.short)}</b> ({esc(root.public_years)}) и <b>{esc(spouse.short)}</b> ({esc(spouse.public_years)}) {esc(meeting["lead_suffix"])}{child_suffix}.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="card">
        <div class="tag">{esc(meeting["living"]["tag"])}</div>
        <h3>{esc(meeting["living"]["title"])}</h3>
        <p>{rich(meeting["living"]["body"])}</p>
      </div>
      <div class="card">
        <div class="tag">{esc(meeting["source"]["tag"])}</div>
        <h3>{esc(meeting["source"]["title"])}</h3>
        <p>{esc(meeting["source"]["intro_prefix"])} {esc(export_date)}: {counted(st['people'], ('человек', 'человека', 'человек'))}, {counted(st['families'], ('семейная запись', 'семейные записи', 'семейных записей'))}, {counted(st['with_death'], ('дата', 'даты', 'дат'))} {esc(meeting["source"]["intro_suffix"])}</p>
      </div>
    </div>
  </div>
</section>

"""


def render_sources_section(sources: dict[str, Any], st: dict[str, Any]) -> str:
    """Provenance, gaps, legend and archive guidance."""
    provenance = sources["provenance"]
    missing = sources["missing"]
    legend = sources["legend"]
    archives = sources["archives"]
    return f"""<section class="src">
  <div class="wrap">
      <div class="sect-head">
      <div class="label">{esc(sources["label"])}</div>
      <h2>{esc(sources["title"])}</h2>
      <p>{rich(sources["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="scard">
        <h3>{esc(provenance["title"])}</h3>
        <ul>
          <li>{rich(provenance["gedcom_item"])}</li>
          <li>{rich(provenance["copy_item"])}</li>
        </ul>
        <p style="margin:10px 0">{esc(provenance["birth_intro_prefix"])} {counted(st['people'], ('человека', 'человек', 'человек'))} {esc(provenance["birth_intro_middle"])} {st['with_birth']}. {esc(provenance["birth_intro_suffix"])}</p>
        <ul>
          <li>{rich(provenance["birth_buckets"]["full"])} — {counted(st['birth_full'], ('запись', 'записи', 'записей'))}</li>
          <li>{rich(provenance["birth_buckets"]["year_only"])} — {st['birth_year_only']}; {esc(provenance["birth_buckets"]["month_year"])} — {st['birth_month_year']}</li>
          <li>{rich(provenance["birth_buckets"]["qualified"])} — {st['birth_qualified']}: {esc(provenance["birth_buckets"]["qualified_note"])}</li>
          <li>{rich(provenance["birth_buckets"]["missing"])} — {st['birth_missing']} {plural(st['birth_missing'], ('человек', 'человека', 'человек'))}</li>
        </ul>
      </div>
      <div class="scard">
        <h3>{esc(missing["title"])}</h3>
        <p style="margin-bottom:10px">{rich(missing["intro"])}</p>
        <ul>
          <li><b>{counted(st['matched'], ('запись', 'записи', 'записей'))}</b> {esc(missing["smart_match_suffix"])}</li>
          <li>{rich(missing["smart_match_caveat"])}</li>
          <li>{esc(missing["no_archives"])}</li>
        </ul>
      </div>
      <div class="scard">
        <h3>{esc(legend["title"])}</h3>
        <ul>
          <li>{rich(legend["hypothesis"])}</li>
          <li>{rich(legend["calculated_dates"])}</li>
          <li>{rich(legend["dashed_card"])}</li>
        </ul>
      </div>
      <div class="scard">
        <h3>{esc(archives["title"])}</h3>
        <ul>
          <li>{rich(archives["mokroe"])}</li>
          <li>{rich(archives["valday"])}</li>
          <li>{rich(archives["chistopol"])}</li>
          <li>{rich(archives["slavyanoserbsk"])}</li>
          <li>{rich(archives["khimki"])}</li>
        </ul>
      </div>
    </div>
  </div>
</section>
"""


def render_chronicle_page(
    content: dict[str, Any],
    st: dict[str, Any],
    family: FamilyContext,
    father_line: list[Person],
    mother_line: list[Person],
    skiba_father: list[Person],
    skiba_mother: list[Person],
    documented_gens: int,
    export_date: str,
    timeline_people: list[Person],
    places_html: str,
    surnames_html: str,
) -> str:
    """First page: chronicle sections from hero through sources."""
    child_suffix = child_line_text(family.child, content["meeting"])
    timeline_html = build_timeline_html(content["timeline"], timeline_people, family.root.id)
    return (
        '<div class="page visible" id="page1">\n'
        + render_hero_section(content["hero"], st, documented_gens, export_date, timeline_people)
        + render_lines_section(
            content["lines"],
            father_line,
            mother_line,
            skiba_father,
            skiba_mother,
        )
        + render_alekseevs_section(content["alekseevs"])
        + render_timeline_section(content["timeline"], timeline_html)
        + render_surnames_section(content["surnames"], surnames_html)
        + render_places_section(content["places"], places_html)
        + render_meeting_section(
            content["meeting"],
            family.root,
            family.spouse,
            child_suffix,
            export_date,
            st,
        )
        + render_sources_section(content["sources"], st)
        + "</div>\n\n"
    )


def render_tree_page(
    tree: dict[str, Any],
    people: dict[str, Person],
    goals: list[tuple[Person, int]],
    pedigree_svg: str,
    goals_html: str,
) -> str:
    """Second page: SVG pedigree chart and search goals."""
    goals_text = tree["goals"]
    return f"""<div class="page" id="page2">
<section class="pagehead">
  <div class="wrap">
    <div class="label">{esc(tree["label"])}</div>
    <h1>{esc(tree["h1"])}</h1>
    <p class="sub">{rich(tree["lead"])}</p>
    <div class="stats" style="margin-top:24px">
      <div><b>{len([p for p in people.values() if p.famc])}</b><span>{esc(tree["stats"]["with_parents"])}</span></div>
      <div><b>{len(goals)}</b><span>{esc(tree["stats"]["search_goals"])}</span></div>
    </div>
  </div>
</section>

<section class="treewrap">
  <div class="wrap" style="max-width:none">{pedigree_svg}
    <div class="legend">
      <span><i class="ok"></i>{esc(tree["legend"]["ok"])}</span>
      <span><i class="hyp"></i>{esc(tree["legend"]["hyp"])}</span>
      <span><i class="q"></i>{esc(tree["legend"]["q"])}</span>
      <span><i class="anchor"></i>{esc(tree["legend"]["anchor"])}</span>
    </div>
  </div>
</section>

<section class="alt">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">{esc(goals_text["label"])}</div>
      <h2>{esc(goals_text["title"])}</h2>
      <p>{esc(goals_text["lead"])}</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">{goals_html}</div>
  </div>
</section>
</div>

"""


def render_footer(footer: dict[str, Any], export_date: str) -> str:
    """Site footer."""
    return f"""<footer>
  <div class="wrap"><b>{esc(footer["brand"])}</b>{esc(footer["middle"])} {esc(export_date)}{esc(footer["suffix"])}</div>
</footer>

"""


def render_page_script() -> str:
    """Client-side tab switcher plus nav context: the sticky nav turns graphite
    while the dark hero is in view and porcelain everywhere else."""
    return """<script>
function showPage(n) {
  document.getElementById('page1').classList.toggle('visible', n===1);
  document.getElementById('page2').classList.toggle('visible', n===2);
  document.getElementById('nb1').classList.toggle('active', n===1);
  document.getElementById('nb2').classList.toggle('active', n===2);
  window.scrollTo({top:0});
}
var heroEl = document.querySelector('#page1 .hero');
if (heroEl && 'IntersectionObserver' in window) {
  new IntersectionObserver(function(entries) {
    document.body.classList.toggle('over-hero', entries[0].isIntersecting);
  }, {rootMargin: '-72px 0px 0px 0px'}).observe(heroEl);
}
</script>
</body>
</html>"""


def build_html(
    people: dict[str, Person],
    families: dict[str, Family],
    meta: dict[str, str],
    content: dict[str, Any],
) -> str:
    family = resolve_family_context(people, families)
    st = stats(people, families)
    father_line = direct_lines(ROOT_ID, people, families)["father"]
    mother_line = direct_lines(ROOT_ID, people, families)["mother"]
    skiba_father = direct_lines(family.spouse.id, people, families)["father"]
    skiba_mother = direct_lines(family.spouse.id, people, families)["mother"]

    gens_father = count_generations(ROOT_ID, people, families)
    gens_skiba = count_generations(family.spouse.id, people, families)
    documented_gens = max(gens_father, gens_skiba) + 1
    goals = missing_parent_goals([ROOT_ID, family.spouse.id], people, families)
    gen_names = generation_names(content)

    # Full paternal chain, same depth as the pedigree chart — down to the
    # 1834 Mokroe ancestors (Fedot, Grigory, Ilya, Matvey).
    timeline_people = father_line
    if len(timeline_people) < 4:
        timeline_people = skiba_father

    places_html = build_places_html(content["places"], merged_places(people))
    surnames_html = build_surnames_html(content["surnames"], st["top_surnames"])
    goals_html = build_goals_html(content["tree"], goals, gen_names)
    pedigree_svg = render_pedigree_svg(
        family.root,
        family.spouse,
        family.child,
        people,
        families,
        content,
        # Deep enough to reach the 1834 Mokroe ancestors: Fedot (4),
        # Grigory (5), Ilya (6) and Matvey (7).
        max_gen=7,
    )
    export_date = format_date(meta.get("date", "")) or "2026"
    css = CSS.read_text(encoding="utf-8") if CSS.exists() else ""

    return (
        render_document_start(content["meta"], css)
        + render_nav(content["meta"])
        + render_chronicle_page(
            content,
            st,
            family,
            father_line,
            mother_line,
            skiba_father,
            skiba_mother,
            documented_gens,
            export_date,
            timeline_people,
            places_html,
            surnames_html,
        )
        + render_tree_page(content["tree"], people, goals, pedigree_svg, goals_html)
        + render_footer(content["footer"], export_date)
        + render_page_script()
    )


def main() -> None:
    content = load_content()
    people, families, meta = parse_gedcom(GEDCOM_PATH)
    html_content = build_html(people, families, meta, content)

    # Post-build safety validation (P0 invariant check):
    # Ensure no exact birth dates or places of living people leaked into the generated HTML.
    for person in people.values():
        if person.is_living:
            if person.birt and len(person.birt) > 4:
                # If exact birth date exists (e.g. "17 APR 1971"), it must not be in the output
                if person.birt in html_content:
                    raise ValueError(f"CRITICAL PRIVACY LEAK: Exact birth date '{person.birt}' of living person {person.id} ({person.label}) leaked into generated HTML!")
                # Also check common formatted variations of exact dates to be safe
                formatted = format_date(person.birt)
                if formatted and len(formatted) > 4 and formatted in html_content:
                    raise ValueError(f"CRITICAL PRIVACY LEAK: Formatted birth date '{formatted}' of living person {person.id} ({person.label}) leaked into generated HTML!")
            if person.birt_plac:
                # Birthplace of living people must not leak into the output.
                # Since place names like "Дмитров" or "Химки" are mentioned in general historical texts,
                # we only trigger an error if the birthplace is rendered in direct association with the person,
                # or if a specific public_place check is violated (public_place must be empty for living).
                if person.public_place:
                    raise ValueError(f"CRITICAL PRIVACY LEAK: public_place is not empty for living person {person.id} ({person.label}): '{person.public_place}'")

    OUTPUT_PATH.write_text(html_content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
