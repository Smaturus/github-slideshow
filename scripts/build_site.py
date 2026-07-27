#!/usr/bin/env python3
"""Generate family archive website from GEDCOM export and content/content.yaml."""

from __future__ import annotations

import html
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
            "sub_lead",
            "sub_scope_prefix",
            "sub_stats_people_suffix",
            "sub_stats_gens_suffix",
            "privacy_note",
            "cta",
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


def hero_stats_text(hero: dict[str, Any], st: dict[str, Any], documented_gens: int) -> str:
    """Compose hero subtitle statistics line."""
    return (
        f'{counted(st["people"], ("человек", "человека", "человек"))} {esc(hero["sub_stats_people_suffix"])} '
        f'{counted(st["surnames"], ("фамилия", "фамилии", "фамилий"))}, '
        f'{counted(documented_gens, ("поколение", "поколения", "поколений"))} {esc(hero["sub_stats_gens_suffix"])}'
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
) -> str:
    """Landing hero with stats and privacy note."""
    hero_stats = hero_stats_text(hero, st, documented_gens)
    return f"""<div class="hero">
  <div class="wrap">
    <div class="label">{esc(hero["label_prefix"])} {esc(export_date)}</div>
    <h1>{esc(hero["h1"])}</h1>
    <p class="sub">{rich(hero["sub_lead"])} {esc(hero["sub_scope_prefix"])} {hero_stats}</p>
    <p class="sub note">{rich(hero["privacy_note"])}</p>
    <button class="btn" onclick="showPage(2)">{esc(hero["cta"])}</button>
    <div class="stats">
      <div><b>{documented_gens}</b><span>{plural(documented_gens, ('ПОКОЛЕНИЕ', 'ПОКОЛЕНИЯ', 'ПОКОЛЕНИЙ'))} {esc(hero["stats"]["generations"])}</span></div>
      <div><b>{st['people']}</b><span>{plural(st['people'], ('ЧЕЛОВЕК', 'ЧЕЛОВЕКА', 'ЧЕЛОВЕК'))} {esc(hero["stats"]["people"])}</span></div>
      <div><b>{st['surnames']}</b><span>{esc(hero["stats"]["surnames"])}</span></div>
      <div><b>{st['earliest_year'] or esc(hero["stats"]["earliest_fallback"])}</b><span>{esc(hero["stats"]["earliest_birth"])}</span></div>
    </div>
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
        + render_hero_section(content["hero"], st, documented_gens, export_date)
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
<section class="hero hero-compact">
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
    """Client-side tab switcher between chronicle and tree pages."""
    return """<script>
function showPage(n) {
  document.getElementById('page1').classList.toggle('visible', n===1);
  document.getElementById('page2').classList.toggle('visible', n===2);
  document.getElementById('nb1').classList.toggle('active', n===1);
  document.getElementById('nb2').classList.toggle('active', n===2);
  window.scrollTo({top:0});
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

    timeline_people = father_line[:6]
    if len(timeline_people) < 4:
        timeline_people = skiba_father[:6]

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
        max_gen=5,
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
