#!/usr/bin/env python3
"""Generate family archive website from GEDCOM export."""

from __future__ import annotations

import html
import math
from pathlib import Path

from collections import Counter

from parse_gedcom import (
    Family,
    Person,
    ancestors,
    canonical_place,
    direct_lines,
    format_date,
    parse_gedcom,
    stats,
)

ROOT_ID = "@I1@"
GEDCOM_PATH = Path(__file__).resolve().parents[1] / "data" / "skiba.ged"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "index.html"

CSS = Path(__file__).resolve().parents[1] / "assets" / "site.css"

SURNAME_NOTES = {
    "Матюхин": "Русская фамилия от уменьшительной формы имени Матвей. В селе Мокрое Белевского уезда достоверно прослеживается с Андрея Федотовича (р. 1870); принадлежность его отца Федота к Матюхиным ещё требует подтверждения.",
    "Скиба": "Украинская фамилия (скиба — «ломоть хлеба»); род из села Лозовая Павловка на Донбассе, затем Тула и Химки.",
    "Захаров": "Род из Толкиша (Татария): Ермил → Спиридон → Григорий Спиридонович, который писался и Захаровым, и Алексеевым.",
    "Алексеев": "Внимание: в древе две несвязанные ветви Алексеевых — татарская (из Захаровых) и донбасская. Обе сходятся в бабушках Надежды Скиба.",
    "Поташкин": "От прозвища «поташник»; корни в деревне Серганиха Валдайского уезда Новгородской губернии.",
    "Астафьев": "От имени Астафий; линия матери Сергея Матюхина — Дмитров и Долгопрудный.",
    "Никитин": "Родня по браку; связи в подмосковных записях базы.",
    "Сахаров": "Родня по браку; связи требуют уточнения по документам.",
    "Цыганов": "Родня по браку в ветви Поташкиных.",
    "Игнатьев": "Родня по браку; встречается в ветви Алексеевых.",
    "Чернов": "Астраханская родня по браку: Черновы жили в Астрахани с конца XIX века.",
    "Горелов": "Линия прабабушки Марии Гореловой по ветви Матюхиных.",
    "Алексанов": "Прапрабабушка по линии Матюхиных — Прасковья Алексанова.",
    "Елисеев": "Зинаида Елисеева из Толкиша — прапрабабушка Надежды по линии Алексеевых.",
    "Васильев": "Встречается в ветви Алексеевых через брак.",
    "Букин": "Родня по браку в ветви Алексеевых.",
    "Успенский": "Родня по браку; ветвь уточняется.",
    "Яковлев": "Родня по браку в ветви Скиба.",
}

PLACE_NOTES = {
    "г. Химки, Московская область": "Главное гнездо рода с середины XX века: здесь жили Скибы, здесь поженились Сергей и Надежда.",
    "село Мокрое Тульской области": "Село Белевского уезда Тульской губернии — родовое гнездо Матюхиных с XIX века.",
    "село Лозовая Павловка, Донбасс": "Село на Луганщине — точка выхода рода Скиба: здесь родились Григорий (1879) и Алексей (1907).",
    "с. Толкиш, Татария": "Село под Чистополем — родина Захаровых-Алексеевых и Елисеевых.",
    "г. Чистополь, Татария": "Уездный город на Каме; здесь родилась Серафима Алексеева (1912).",
    "с. Новошешминск, Татария": "Село Чистопольского уезда; родина братьев Алексеевых.",
    "дер. Серганиха, Валдайский уезд, Новгородская губерния": "Новгородская губерния — корень Поташкиных: здесь родился Федор (1904).",
    "г. Валдай, Новгородская губерния": "Новгородская губерния; связанные записи рода Поташкиных.",
    "город Дмитров, Московская область": "Подмосковье; родина Надежды Астафьевой (1931) и Сергея Матюхина (1971).",
    "Астрахань": "Город Черновых — родни по браку; жили здесь с конца XIX века.",
    "Москва": "Столица; сюда сходятся поздние ветви рода.",
    "г. Солнечногорск, Московская область": "Подмосковье; последний адрес Федора Поташкина и Серафимы Алексеевой.",
    "город Долгопрудный, Московская область": "Подмосковье; последний адрес Надежды Астафьевой.",
    "г. Борисоглебск": "Город на Воронежщине; встречается в записях рода.",
    "Донецкая область": "Донбасс; родина Маргариты Алексеевой (1909).",
    "Константиновка, Донецкая область": "Город на Донбассе; встречается в записях рода.",
}


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


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
) -> list[tuple[Person, str, int]]:
    """Gaps in the direct ancestor line only — closest generations first."""
    goals: list[tuple[Person, str, int]] = []
    seen: set[str] = set()

    def walk(pid: str, depth: int) -> None:
        if pid in seen or pid not in people:
            return
        seen.add(pid)
        person = people[pid]
        family = families.get(person.famc) if person.famc else None

        if family is None:
            if depth > 0:
                goals.append((person, "родители", depth))
            return

        if not family.husb:
            goals.append((person, "отец", depth))
        if not family.wife:
            goals.append((person, "мать", depth))

        for parent in (family.husb, family.wife):
            if parent:
                walk(parent, depth + 1)

    for root_id in root_ids:
        walk(root_id, 0)

    goals.sort(key=lambda item: (item[2], item[0].surname))
    return goals[:limit]


GENERATION_NAMES = {
    1: "родители",
    2: "деды и бабушки",
    3: "прадеды",
    4: "прапрадеды",
    5: "прапрапрадеды",
    6: "шестое поколение",
}

BOX_W = 158
BOX_H = 44
COL_W = 186
ROW_H = 58
TOP_PAD = 42
LEFT_PAD = 12

COLUMN_TITLES = [
    "СЕМЬЯ",
    "РОДИТЕЛИ",
    "ДЕДЫ И БАБУШКИ",
    "ПРАДЕДЫ",
    "ПРАПРАДЕДЫ",
    "ПРАПРАПРАДЕДЫ",
]


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
        build_ancestor_tree(family.husb, people, families, max_gen, gen + 1, "отец не найден")
    )
    node.children.append(
        build_ancestor_tree(family.wife, people, families, max_gen, gen + 1, "мать не найдена")
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


def render_box(node: TreeNode, max_gen: int) -> str:
    x = LEFT_PAD + node.gen * COL_W
    y = node.y - BOX_H / 2

    if node.is_missing:
        return (
            f'<g class="bx q"><rect x="{x}" y="{y:.1f}" width="{BOX_W}" height="{BOX_H}" rx="8"/>'
            f'<text x="{x + 10}" y="{node.y - 6:.1f}" class="t1">—</text>'
            f'<text x="{x + 10}" y="{node.y + 12:.1f}" class="t3">{esc(node.placeholder)}</text></g>'
        )

    person = node.person
    assert person is not None
    classes = ["bx"]
    if node.gen == 0:
        classes.append("me")
    elif person.is_reconstructed:
        classes.append("hyp")
    elif not node.children and person.birt:
        classes.append("deep")

    surname = person.surname or person.name
    given = person.name if person.surname else ""
    years = person.public_years.replace("р. ", "").replace("ум. ", "† ")
    if person.is_reconstructed and not person.is_living:
        years = f"{years} · гипотеза" if years != "? – ?" else "гипотеза"

    return (
        f'<g class="{" ".join(classes)}"><rect x="{x}" y="{y:.1f}" width="{BOX_W}" height="{BOX_H}" rx="8"/>'
        f'<text x="{x + 10}" y="{node.y - 9:.1f}" class="t1">{esc(surname)}</text>'
        f'<text x="{x + 10}" y="{node.y + 3:.1f}" class="t2">{esc(given)}</text>'
        f'<text x="{x + 10}" y="{node.y + 15:.1f}" class="t3">{esc(years)}</text></g>'
    )


def render_pedigree_svg(
    root: Person,
    spouse: Person,
    child: Person | None,
    people: dict[str, Person],
    families: dict[str, Family],
    max_gen: int = 4,
) -> str:
    """Two stacked ancestor charts: the husband's line above, the wife's below."""
    father_tree = build_ancestor_tree(root.id, people, families, max_gen)
    mother_tree = build_ancestor_tree(spouse.id, people, families, max_gen)

    cursor = [TOP_PAD + ROW_H]
    assign_positions(father_tree, cursor)
    cursor[0] += ROW_H * 1.5
    assign_positions(mother_tree, cursor)

    nodes: list[TreeNode] = []
    collect_nodes(father_tree, nodes)
    collect_nodes(mother_tree, nodes)

    parts: list[str] = []
    for index, title in enumerate(COLUMN_TITLES[: max_gen + 1]):
        parts.append(f'<text x="{LEFT_PAD + index * COL_W}" y="20" class="colhead">{esc(title)}</text>')

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
        parts.append(
            f'<g class="bx me"><rect x="{LEFT_PAD}" y="{y_child - BOX_H / 2:.1f}" '
            f'width="{BOX_W}" height="{BOX_H}" rx="8"/>'
            f'<text x="{LEFT_PAD + 10}" y="{y_child - 9:.1f}" class="t1">{esc(child.surname)}</text>'
            f'<text x="{LEFT_PAD + 10}" y="{y_child + 3:.1f}" class="t2">{esc(child.name)}</text>'
            f'<text x="{LEFT_PAD + 10}" y="{y_child + 15:.1f}" class="t3">'
            f'{esc(child.public_years.replace("р. ", ""))}</text></g>'
        )

    for node in nodes:
        parts.append(render_box(node, max_gen))

    width = LEFT_PAD * 2 + (max_gen + 1) * COL_W
    height = max(node.y for node in nodes) + ROW_H

    return (
        f'<svg class="pedigree" viewBox="0 0 {width} {height:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg" style="min-width:{width}px">'
        + "".join(parts)
        + "</svg>"
    )


def build_html(people: dict[str, Person], families: dict[str, Family], meta: dict[str, str]) -> str:
    root = people[ROOT_ID]
    spouse_fam = families[root.fams[0]]
    spouse_id = spouse_fam.wife if spouse_fam.husb == ROOT_ID else spouse_fam.husb
    spouse = people[spouse_id]
    children = [people[c] for c in spouse_fam.chil if c in people]
    child = children[0] if children else None

    st = stats(people, families)
    father_line = direct_lines(ROOT_ID, people, families)["father"]
    mother_line = direct_lines(ROOT_ID, people, families)["mother"]
    skiba_father = direct_lines(spouse_id, people, families)["father"]
    skiba_mother = direct_lines(spouse_id, people, families)["mother"]

    gens_father = count_generations(ROOT_ID, people, families)
    gens_skiba = count_generations(spouse_id, people, families)
    documented_gens = max(gens_father, gens_skiba) + 1
    goals = missing_parent_goals([ROOT_ID, spouse_id], people, families)

    timeline_people = father_line[:6]
    if len(timeline_people) < 4:
        timeline_people = skiba_father[:6]

    merged_places: Counter[str] = Counter()
    for person in people.values():
        if person.is_living:
            continue
        for raw_place in (person.birt_plac, person.deat_plac):
            raw_place = raw_place.strip()
            if raw_place and raw_place not in {"Россия", "Украина"}:
                merged_places[canonical_place(raw_place)] += 1

    places_html = "".join(
        f'<div class="card"><div class="tag">География · {count} записей</div><h4>{esc(place)}</h4>'
        f'<p>{esc(PLACE_NOTES.get(place, "Место из записей о рождении и смерти в семейной базе."))}</p></div>'
        for place, count in merged_places.most_common(9)
    )

    surnames_html = "".join(
        f'<div class="card"><h4>{esc(name)}</h4>'
        f'<p>{esc(SURNAME_NOTES.get(name, "Фамилия встречается в семейном древе; происхождение уточняется."))}</p>'
        f'<div class="mini">{count} носителей в базе</div></div>'
        for name, count in st["top_surnames"][:10]
    )

    timeline_html = ""
    for i, person in enumerate(timeline_people):
        me = " me" if person.id == ROOT_ID else ""
        timeline_html += f"""
      <div class="tl-item{me}">
        <div class="tl-gen">Поколение {len(timeline_people) - i} · линия Матюхиных</div>
        <h3>{esc(person.label)}</h3>
        <div class="yrs">{esc(person.public_years)}</div>
        <p>{esc(person.public_place or 'Место уточняется по метрикам и семейным записям.')}</p>
      </div>"""

    goals_html = ""
    for i, (person, kind, depth) in enumerate(goals, 1):
        generation = GENERATION_NAMES.get(depth, f"{depth}-е поколение")
        place = person.public_place
        hint = (
            f"Известное место — {place}: искать метрики этого прихода."
            if place
            else "Место рождения в базе не указано — сначала нужно установить приход."
        )
        goals_html += f"""
        <div class="goalrow"><div class="n">{i}</div><div>
          <b>{kind.capitalize()} — {esc(person.label)}</b>
          <p>{esc(person.public_years)} · {esc(generation)} по прямой линии. {esc(hint)}</p>
          <div class="st">{esc(generation.capitalize())} · пробел в прямой линии</div>
        </div></div>"""

    pedigree_svg = render_pedigree_svg(root, spouse, child, people, families, max_gen=5)
    export_date = format_date(meta.get("date", "")) or "2026"
    child_line_text = (
        f" {esc(child.name.split()[0])} ({esc(child.public_years)})" if child else " следующего поколения"
    )

    css = CSS.read_text(encoding="utf-8") if CSS.exists() else ""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Род Матюхиных и Скиба — семейный архив</title>
<style>{css}</style>
</head>
<body>
<nav>
  <div class="wrap">
    <div class="brand">Род Матюхиных и Скиба</div>
    <button class="navbtn active" id="nb1" onclick="showPage(1)">Летопись рода</button>
    <button class="navbtn" id="nb2" onclick="showPage(2)">Древо</button>
  </div>
</nav>

<div class="page visible" id="page1">
<div class="hero">
  <div class="wrap">
    <div class="label">Семейный архив · MyHeritage · экспорт {esc(export_date)}</div>
    <h1>Летопись рода Матюхиных и Скиба</h1>
    <p class="sub">Две главные линии — <b>Матюхины</b> из села Мокрое Тульской губернии и <b>Скибы</b> с донбасской Лозовой Павловки — сошлись в семье Сергея и Надежды. Тульская земля и Донбасс, Валдай и Татария, Подмосковье; {st['people']} человек в базе, {st['surnames']} фамилий, {documented_gens} поколений прослежено.</p>
    <p class="sub" style="font-size:15px;margin-top:-14px">Страница собрана автоматически из семейного древа MyHeritage — данные ныне живущих на ней не публикуются.</p>
    <button class="btn" onclick="showPage(2)">Открыть древо</button>
    <div class="stats">
      <div><b>{documented_gens}</b><span>ПОКОЛЕНИЙ ПРОСЛЕЖЕНО</span></div>
      <div><b>{st['people']}</b><span>ЧЕЛОВЕК В БАЗЕ</span></div>
      <div><b>{st['surnames']}</b><span>РОДОВЫХ ФАМИЛИЙ</span></div>
      <div><b>{st['earliest_year'] or 'XIX в.'}</b><span>ГОД РОЖДЕНИЯ САМОГО РАННЕГО ПРЕДКА</span></div>
    </div>
  </div>
</div>

<section id="line">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Четыре линии · ветви одного рода</div>
      <h2>Кем мы приходимся друг другу</h2>
      <p>У Сергея и Надежды — четыре родительские линии. Ниже цепочки так, как они записаны в семейном древе.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2" style="margin-bottom:44px">
      <div class="card">
        <div class="tag">Линия Сергея · по отцу</div>
        <h3>Матюхины</h3>
        <p>{chain_text(father_line[:5])}</p>
        <p>Корни в селе <b>Мокрое</b> Белевского уезда Тульской губернии. По архивным документам подтверждены родители Андрея — <b>Федот Григорьев</b> и <b>Параскева Петрова</b>.</p>
        <p>В базе он записан как «Федот Матюхин, р. до 1852», но <b>фамилия, дата рождения и отождествление с Федотом 1818/1819 года — пока гипотеза</b><span class="gip">гипотеза</span>: карточка не имеет источника, дата вычислена от года рождения сына.</p>
        <div class="mini">Проверить: ревизские сказки и метрики Белевского уезда (ГАТО, Тула)</div>
      </div>
      <div class="card">
        <div class="tag">Линия Сергея · по матери</div>
        <h3>Астафьевы</h3>
        <p>{chain_text(mother_line[:4])}</p>
        <p>Линия матери Сергея — <b>Надежды Астафьевой</b> (1931, Дмитров — 1997, Долгопрудный). Дед <b>Алексей Астафьев</b>; бабушка <b>Мария Архиповна</b> — пока без девичьей фамилии в базе.</p>
        <div class="mini">Цель: девичья фамилия Марии Архиповны и предки Петра Астафьева</div>
      </div>
      <div class="card">
        <div class="tag">Линия Надежды · по отцу</div>
        <h3>Скибы</h3>
        <p>{chain_text(skiba_father[:5])}</p>
        <p>Донбасская ветвь: род из села <b>Лозовая Павловка</b> (ныне Луганщина). Дед <b>Алексей Скиба</b> (1907, Лозовая Павловка — 1955, Химки), прадед <b>Григорий</b> (р. 1879), прапрадед <b>Андрей Скиба</b>. Жена Алексея — <b>Маргарита Алексеева</b> (1909, Донецкая обл.) из донбасской ветви Алексеевых.</p>
        <div class="mini">Вглубь: метрики Славяносербского уезда Екатеринославской губернии</div>
      </div>
      <div class="card">
        <div class="tag">Линия Надежды · по матери</div>
        <h3>Поташкины и Захаровы</h3>
        <p>{chain_text(skiba_mother[:5])}</p>
        <p>Бабушка <b>Нина Поташкина</b> (1938, Торопец): отец — <b>Федор Поташкин</b> с Валдая, мать — <b>Серафима Алексеева</b> из Чистополя, дочь <b>Григория Захарова-Алексеева</b> и <b>Зинаиды Елисеевой</b> из Толкиша.</p>
        <div class="mini">Вглубь: метрики Валдайского уезда (Поташкины) и Чистопольского уезда (Захаровы)</div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Совпадение фамилий · не путать</div>
      <h2>Две ветви Алексеевых</h2>
      <p>В древе две семьи Алексеевых, между собой не родственные. Обе сходятся в бабушках <b>Надежды Скиба</b> — по отцу и по матери.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="card">
        <div class="tag">Ветвь I · Татария · из Захаровых</div>
        <h3>Захаровы-Алексеевы</h3>
        <p><b>Ермил Захаров</b> → <b>Спиридон Ермилович</b> → <b>Григорий Спиридонович</b> (1887–1966), записанный как «Захаров/Алексеев».</p>
        <p>Его дети от <b>Зинаиды Елисеевой</b> (Толкиш) разошлись по фамилиям: старший <b>Василий</b> остался Захаровым, младшие — <b>Александр</b>, <b>Серафима</b>, <b>Иван</b>, <b>Константин</b> — стали Алексеевыми.</p>
        <p><b>Серафима</b> (1912, Чистополь) вышла за Федора Поташкина — она бабушка Надежды <b>по матери</b>.</p>
        <div class="mini">Толкиш · Новошешминск · Чистополь (Татария)</div>
      </div>
      <div class="card">
        <div class="tag">Ветвь II · Донбасс · самостоятельный род</div>
        <h3>Алексеевы донбасские</h3>
        <p><b>Василий Алексеев</b> → <b>Василий Васильевич</b> (1875–1935) и <b>Агафья Андреевна</b>; в семье восемь детей.</p>
        <p>Дочь <b>Маргарита</b> (1909, Донецкая обл. — 1987, Химки) вышла за <b>Алексея Скиба</b> — она бабушка Надежды <b>по отцу</b>.</p>
        <p>С татарскими Алексеевыми родство в документах не прослеживается: разные губернии, разные корни, совпадение распространённой фамилии.</p>
        <div class="mini">Донецкая область · Лозовая Павловка · Химки</div>
      </div>
    </div>
  </div>
</section>

<section style="background:var(--bg2)">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Самая длинная прослеженная линия</div>
      <h2>Матюхины: цепочка поколений</h2>
      <p>От Сергея Андреевича вглубь по отцовской линии — так записано в GEDCOM.</p>
      <div class="hr"></div>
    </div>
    <div class="tl">{timeline_html}
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Ономастика</div>
      <h2>Фамилии рода</h2>
      <p>Десять самых частых фамилий в базе; женские формы посчитаны вместе с мужскими.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">{surnames_html}</div>
  </div>
</section>

<section style="background:var(--bg2)">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">География</div>
      <h2>Гнёзда рода на карте слов</h2>
      <p>Места, чаще всего встречающиеся в записях о рождении и смерти.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g3">{places_html}</div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Точка встречи</div>
      <h2>Где сходятся две линии</h2>
      <p>Тульская линия Матюхиных и донбасско-валдайская линия Скиба сошлись в подмосковных Химках: <b>{esc(root.short)}</b> ({esc(root.public_years)}) и <b>{esc(spouse.short)}</b> ({esc(spouse.public_years)}) — родители{child_line_text}.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="card">
        <div class="tag">Ныне живущие</div>
        <h3>Сегодняшнее поколение</h3>
        <p>Данные ныне живущих родственников на сайте не публикуются: указаны только годы рождения, без точных дат, мест и контактов.</p>
      </div>
      <div class="card">
        <div class="tag">Источник</div>
        <h3>MyHeritage · SKIBA</h3>
        <p>Экспорт GEDCOM 5.5.1 от {esc(export_date)}: {st['people']} человек, {st['families']} семейных пар, {st['with_death']} дат смерти. Публикуется только часть, относящаяся к ушедшим поколениям.</p>
      </div>
    </div>
  </div>
</section>

<section class="src">
  <div class="wrap">
      <div class="sect-head">
      <div class="label">Достоверность</div>
      <h2>Источники и оговорки</h2>
      <p>Персональные данные импортированы из GEDCOM-экспорта MyHeritage. Описания, этимология фамилий, географические комментарии и направления поиска <b>сформированы автоматически и требуют проверки</b>.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="scard">
        <h3>Что откуда взято</h3>
        <ul>
          <li><b>Имена, даты, связи</b> — GEDCOM MyHeritage, проект SKIBA</li>
          <li><b>Точная дата рождения</b> — у {st['exact_dated']} из {st['people']} человек</li>
          <li><b>Дата выведена расчётом</b> — у {st['reconstructed']}: такие записи помечены как гипотеза</li>
          <li><b>Тексты разделов</b> — сгенерированы автоматически, архивно не проверены</li>
        </ul>
      </div>
      <div class="scard">
        <h3>Чего в файле нет</h3>
        <p style="margin-bottom:10px">Ссылки на источники в экспорте есть, но за ними стоят <b>не архивные документы</b>:</p>
        <ul>
          <li><b>{st['matched']} записей</b> связаны со Smart Match — совпадением с деревом другого пользователя MyHeritage</li>
          <li>Такое совпадение — <b>зацепка, а не доказательство</b>: чужое дерево может содержать ту же ошибку</li>
          <li>Ссылок на метрические книги, ревизские сказки и записи ЗАГС в файле нет ни одной</li>
        </ul>
      </div>
      <div class="scard">
        <h3>Как читать пометки</h3>
        <ul>
          <li><span class="leg">гипотеза</span> запись без источника с вычисленной датой</li>
          <li><b>«до 1852», «ок. 1870»</b> — дата выведена от родственников, а не из документа</li>
          <li><b>Пунктирная карточка в древе</b> — предок не найден, это цель поиска</li>
        </ul>
      </div>
      <div class="scard">
        <h3>Архивные направления</h3>
        <ul>
          <li>Метрики по <b>с. Мокрое</b> Белевского уезда (ГАТО, Тула)</li>
          <li>Метрики <b>Валдайского уезда</b> — Поташкины (ГАНО)</li>
          <li>Метрики <b>Чистопольского уезда</b> — Захаровы-Алексеевы (ГА РТ)</li>
          <li>Метрики <b>Славяносербского уезда</b> — Скибы (Лозовая Павловка)</li>
          <li>Записи ЗАГС по <b>Химкам</b> и Московской области</li>
        </ul>
      </div>
    </div>
  </div>
</section>
</div>

<div class="page" id="page2">
<section class="hero" style="padding:60px 0 40px">
  <div class="wrap">
    <div class="label">Страница 2 · визуальное древо · прямые предки</div>
    <h1 style="font-size:clamp(34px,4vw,56px)">Древо прямых предков</h1>
    <p class="sub">Читается слева направо: семья Сергея и Надежды → родители → деды → прадеды. Верхняя половина — линия Матюхиных, нижняя — Скиба.</p>
    <div class="stats" style="margin-top:24px">
      <div><b>{len([p for p in people.values() if p.famc])}</b><span>С УКАЗАННЫМИ РОДИТЕЛЯМИ</span></div>
      <div><b>{len(goals)}</b><span>ЦЕЛЕЙ ПОИСКА</span></div>
    </div>
  </div>
</section>

<section style="overflow-x:auto;padding-top:20px">
  <div class="wrap" style="max-width:none">{pedigree_svg}
    <div class="legend">
      <span><i style="background:rgba(58,16,40,.9);border:1px solid var(--border)"></i>предок с записью в базе</span>
      <span><i style="border:1px dashed var(--champ2);background:rgba(58,16,40,.55)"></i>гипотеза — нет источника, дата вычислена</span>
      <span><i style="border:1px dashed var(--line)"></i>предок не найден — цель поиска</span>
      <span><i style="background:rgba(14,143,75,.25);border:1px solid var(--green)"></i>ныне живущие</span>
    </div>
  </div>
</section>

<section style="background:var(--bg2)">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Что ищем дальше</div>
      <h2>Карта поиска: белые пятна</h2>
      <p>Приоритеты — по GEDCOM-записям, где родители ещё не указаны.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">{goals_html}</div>
  </div>
</section>
</div>

<footer>
  <div class="wrap"><b>Род Матюхиных и Скиба</b> · семейный архив · данные MyHeritage SKIBA · экспорт {esc(export_date)} · сайт сгенерирован из GEDCOM</div>
</footer>

<script>
function showPage(n) {{
  document.getElementById('page1').classList.toggle('visible', n===1);
  document.getElementById('page2').classList.toggle('visible', n===2);
  document.getElementById('nb1').classList.toggle('active', n===1);
  document.getElementById('nb2').classList.toggle('active', n===2);
  window.scrollTo({{top:0}});
}}
</script>
</body>
</html>"""


def main() -> None:
    people, families, meta = parse_gedcom(GEDCOM_PATH)
    OUTPUT_PATH.write_text(build_html(people, families, meta), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
