#!/usr/bin/env python3
"""Generate family archive website from GEDCOM export."""

from __future__ import annotations

import html
import math
from pathlib import Path

from collections import Counter

from parse_gedcom import Family, Person, ancestors, direct_lines, parse_gedcom, stats

ROOT_ID = "@I1@"
GEDCOM_PATH = Path(__file__).resolve().parents[1] / "data" / "skiba.ged"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "index.html"

CSS = Path(__file__).resolve().parents[1] / "assets" / "site.css"

SURNAME_NOTES = {
    "Матюхин": "Русская фамилия; в селе Мокрое Белевского уезда Тульской губернии прослеживается с середины XIX века (Федот Матюхин).",
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

PLACE_ALIASES = {
    "Химки": "Химки",
    "гХимки": "Химки",
    "Химки, Московская область, Россия": "Химки",
    "с.Мокрое": "с. Мокрое (Тульская обл.)",
    "село Мокрое": "с. Мокрое (Тульская обл.)",
    "село Мокрое Тульской области": "с. Мокрое (Тульская обл.)",
    "с.Мокрое, Белевский уезд Тульской губернии": "с. Мокрое (Тульская обл.)",
    "Москва": "Москва",
    "гМосква": "Москва",
    "Moscow": "Москва",
    "Moscow, Russia": "Москва",
    "Россия Москва": "Москва",
    "Чистополь": "Чистополь (Татария)",
    "гЧистополь": "Чистополь (Татария)",
    "Толкиш, Татария": "Толкиш (Татария)",
    "Малый Толкиш": "Толкиш (Татария)",
    "Новошешминск": "Новошешминск (Татария)",
    "Солнечногорск": "Солнечногорск",
    "гСолнечногорск": "Солнечногорск",
    "Дмитров": "Дмитров",
    "город Дмитров": "Дмитров",
    "Долгопрудный": "Долгопрудный",
    "город Долгопрудный": "Долгопрудный",
    "Борисоглебск": "Борисоглебск",
    "гБорисоглебск": "Борисоглебск",
    "Село Лозовая Павловка": "с. Лозовая Павловка (Донбасс)",
    "Ворошиловградская область, Сергинский/Сергеевский/Серговский (Коневский) район, село Лозовая Павловка": "с. Лозовая Павловка (Донбасс)",
    "дер.Серганиха Валдайского уезда Новгородской губернии": "Валдайский уезд",
    "г.Валдай": "Валдайский уезд",
    "Астрахань": "Астрахань",
    "Жуковский": "Жуковский",
    "Торопец": "Торопец",
}

PLACE_NOTES = {
    "Химки": "Главное гнездо рода с середины XX века: здесь жили Скибы, здесь поженились Сергей и Надежда.",
    "с. Мокрое (Тульская обл.)": "Село Белевского уезда Тульской губернии — родовое гнездо Матюхиных с XIX века.",
    "с. Лозовая Павловка (Донбасс)": "Село на Луганщине — точка выхода рода Скиба: здесь родились Григорий (1879) и Алексей (1907).",
    "Толкиш (Татария)": "Село под Чистополем — родина Захаровых-Алексеевых и Елисеевых.",
    "Чистополь (Татария)": "Уездный город на Каме; здесь родилась Серафима Алексеева (1912).",
    "Новошешминск (Татария)": "Село Чистопольского уезда; родина братьев Алексеевых.",
    "Валдайский уезд": "Новгородская губерния, дер. Серганиха — корень Поташкиных: здесь родился Федор (1904).",
    "Дмитров": "Подмосковье; родина Надежды Астафьевой (1931) и Сергея Матюхина (1971).",
    "Астрахань": "Город Черновых — родни по браку; жили здесь с конца XIX века.",
    "Москва": "Столица; сюда сходятся поздние ветви рода.",
    "Солнечногорск": "Подмосковье; последний адрес Федора Поташкина и Серафимы Алексеевой.",
    "Долгопрудный": "Подмосковье; последний адрес Надежды Астафьевой.",
}


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def chain_text(people: list[Person]) -> str:
    return " → ".join(f"<b>{esc(p.surn)} {esc(p.givn.split()[0] if p.givn else '')}</b> ({esc(p.years)})" for p in people)


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


def missing_parent_goals(people: dict[str, Person], families: dict[str, Family], limit: int = 9) -> list[tuple[Person, str]]:
    goals: list[tuple[Person, str]] = []
    for person in people.values():
        if person.famc and person.famc in families:
            family = families[person.famc]
            if not family.husb:
                goals.append((person, "отец"))
            if not family.wife:
                goals.append((person, "мать"))
        elif person.birt and person.id not in {"@I1@", "@I2@", "@I3@"}:
            goals.append((person, "родители"))
    goals.sort(key=lambda item: (0 if item[1] == "родители" else 1, item[0].birt or "ZZZ"))
    return goals[:limit]


class TreeNode:
    def __init__(self, person: Person | None, gen: int, branch: str, slot: int):
        self.person = person
        self.gen = gen
        self.branch = branch  # father / mother
        self.slot = slot
        self.children: list[TreeNode] = []

    @property
    def missing(self) -> bool:
        return self.person is None


def build_branch(
    pid: str | None,
    gen: int,
    branch: str,
    slot: int,
    people: dict[str, Person],
    families: dict[str, Family],
    max_gen: int,
) -> TreeNode | None:
    if gen > max_gen:
        return None
    person = people.get(pid) if pid else None
    node = TreeNode(person, gen, branch, slot)
    if not person or not person.famc or person.famc not in families:
        return node
    family = families[person.famc]
    father = build_branch(family.husb, gen + 1, branch, slot * 2, people, families, max_gen)
    mother = build_branch(family.wife, gen + 1, branch, slot * 2 + 1, people, families, max_gen)
    if father:
        node.children.append(father)
    if mother:
        node.children.append(mother)
    return node


def layout_tree(
    father_root: TreeNode | None,
    mother_root: TreeNode | None,
    max_gen: int,
) -> tuple[list[dict], float]:
    """Assign y positions for pedigree boxes."""
    boxes: list[dict] = []
    row_h = 96
    top_base = 80
    bottom_base = 80 + row_h * (2 ** max_gen) / 2

    def place(node: TreeNode | None, gen: int, y: float, x_col: int, branch: str) -> None:
        if node is None:
            return
        x = 10 + gen * 184
        person = node.person
        if person:
            cls = "me" if gen == 0 else ("q" if not person.famc else "")
            if gen == max_gen and person.birt:
                cls = (cls + " deep").strip()
            boxes.append(
                {
                    "x": x,
                    "y": y,
                    "person": person,
                    "cls": cls,
                    "gen": gen,
                    "branch": branch,
                }
            )
        if node.children:
            span = row_h * (2 ** (max_gen - gen - 1))
            start_y = y - span / 2 + row_h / 4
            for i, child in enumerate(node.children):
                place(child, gen + 1, start_y + i * span, x_col, branch)

    if father_root:
        place(father_root, 0, top_base + row_h * 1.5, 0, "father")
    if mother_root:
        place(mother_root, 0, bottom_base + row_h * 3, 0, "mother")

  # family box at generation -1 equivalent
    height = max(b["y"] for b in boxes) + 80 if boxes else 600
    return boxes, height


def render_pedigree_svg(
    root: Person,
    spouse: Person,
    child: Person | None,
    people: dict[str, Person],
    families: dict[str, Family],
    max_gen: int = 4,
) -> str:
    father_root = build_branch(root.id, 0, "father", 0, people, families, max_gen)
    mother_root = build_branch(spouse.id, 0, "mother", 0, people, families, max_gen)

    boxes: list[dict] = []
    row_h = 88
    cols = ["СЕМЬЯ", "РОДИТЕЛИ", "ДЕДЫ", "ПРАДЕДЫ", "ПРАПРАДЕДЫ", "ГЛУБЖЕ"]

    def walk(node: TreeNode | None, gen: int, y_center: float, branch: str) -> float:
        if node is None:
            return y_center
        x = 12 + gen * 176
        p = node.person
        if p:
            boxes.append({"x": x, "y": y_center, "p": p, "gen": gen, "branch": branch, "missing": not p.famc})
        if not node.children:
            return y_center
        span = row_h * max(1, 2 ** (len(node.children) - 1))
        start = y_center - span / 2 + row_h / 2
        ys = []
        for i, child_node in enumerate(node.children):
            cy = start + i * (span / max(1, len(node.children) - 1)) if len(node.children) > 1 else y_center
            ys.append(walk(child_node, gen + 1, cy, branch))
        return y_center

    walk(father_root, 0, 150, "father")
    walk(mother_root, 0, 430, "mother")

    # family card
    fam_y = 290
    boxes.insert(
        0,
        {
            "x": 12,
            "y": fam_y,
            "p": None,
            "gen": -1,
            "branch": "family",
            "missing": False,
            "custom": [root, spouse, child] if child else [root, spouse],
        },
    )

    max_y = max(b["y"] for b in boxes) + 60
    width = 12 + (max_gen + 2) * 176

    lines: list[str] = []
    for i, title in enumerate(cols[: max_gen + 2]):
        lines.append(f'<text x="{12 + i * 176}" y="18" class="colhead">{esc(title)}</text>')

    for box in boxes:
        x, y = box["x"], box["y"]
        if box.get("custom"):
            people_line = box["custom"]
            lines.append(f'<g class="bx me"><rect x="{x}" y="{y - 21}" width="160" height="52" rx="8"/>')
            lines.append(f'<text x="{x + 9}" y="{y - 6}" class="t1">Семья Матюхиных</text>')
            names = " · ".join(esc(p.givn.split()[0] if p.givn else p.surn) for p in people_line)
            lines.append(f'<text x="{x + 9}" y="{y + 6}" class="t2">{names}</text>')
            lines.append(f'<text x="{x + 9}" y="{y + 18}" class="t3">ныне живущие</text></g>')
            continue
        p: Person = box["p"]
        cls = "bx"
        if box["gen"] == 0:
            cls += " me"
        elif box["missing"] and box["gen"] > 0:
            cls += " q"
        elif box["gen"] == max_gen:
            cls += " deep"
        givn = p.givn.split()[0] if p.givn else ""
        lines.append(f'<g class="{cls}"><rect x="{x}" y="{y - 21}" width="160" height="42" rx="8"/>')
        lines.append(f'<text x="{x + 9}" y="{y - 6}" class="t1">{esc(p.surn)}</text>')
        lines.append(f'<text x="{x + 9}" y="{y + 6}" class="t2">{esc(p.givn)}</text>')
        yrs = p.years.replace("р. ", "").replace("ум. ", "")
        lines.append(f'<text x="{x + 9}" y="{y + 17}" class="t3">{esc(yrs)}</text></g>')

    svg = (
        f'<svg class="pedigree" viewBox="0 0 {width} {max_y}" xmlns="http://www.w3.org/2000/svg" style="min-width:{width}px">'
        + "".join(lines)
        + "</svg>"
    )
    return svg


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
    goals = missing_parent_goals(people, families)

    timeline_people = father_line[:6]
    if len(timeline_people) < 4:
        timeline_people = skiba_father[:6]

    merged_places: Counter[str] = Counter()
    for person in people.values():
        for raw_place in (person.birt_plac, person.deat_plac):
            raw_place = raw_place.strip()
            if raw_place and raw_place not in {"Россия", "Украина"}:
                merged_places[PLACE_ALIASES.get(raw_place, raw_place)] += 1

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
        <h3>{esc(person.surn)} {esc(person.givn)}</h3>
        <div class="yrs">{esc(person.years)}</div>
        <p>{esc(person.birt_plac or person.deat_plac or 'Место уточняется по метрикам и семейным записям.')}</p>
      </div>"""

    goals_html = ""
    for i, (person, kind) in enumerate(goals, 1):
        goals_html += f"""
        <div class="goalrow"><div class="n">{i}</div><div>
          <b>{kind.capitalize()} — {esc(person.label)} ({esc(person.years)})</b>
          <p>Запись о рождении есть, родственная связь вверх пока не замкнута в GEDCOM-экспорте.</p>
          <div class="st">MyHeritage · метрики · архивные запросы</div>
        </div></div>"""

    pedigree_svg = render_pedigree_svg(root, spouse, child, people, families, max_gen=4)
    export_date = meta.get("date", "2026")
    child_line = f" и {esc(child.givn.split()[0])}" if child else ""

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
    <p class="sub" style="font-size:15px;margin-top:-14px">Сайт собран автоматически из GEDCOM-файла, экспортированного из MyHeritage ({esc(meta.get('file', 'SKIBA'))}).</p>
    <button class="btn" onclick="showPage(2)">Открыть древо</button>
    <div class="stats">
      <div><b>{documented_gens}</b><span>ПОКОЛЕНИЙ ПРОСЛЕЖЕНО</span></div>
      <div><b>{st['people']}</b><span>ЧЕЛОВЕК В БАЗЕ</span></div>
      <div><b>{st['surnames']}</b><span>РОДОВЫХ ФАМИЛИЙ</span></div>
      <div><b>{esc(st['earliest'] or 'XIX в.')}</b><span>САМАЯ РАННЯЯ ДАТА</span></div>
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
        <div class="tag">Линия отца · Матюхины</div>
        <h3>Матюхины</h3>
        <p>{chain_text(father_line[:5])}</p>
        <p>Корни в селе <b>Мокрое</b> Белевского уезда Тульской губернии. Прапрадед <b>Федот Матюхин</b> — самая ранняя подтверждённая точка линии в экспорте.</p>
        <div class="mini">Вглубь: метрики и ревизии Белевского уезда (ГАТО, Тула)</div>
      </div>
      <div class="card">
        <div class="tag">Линия отца · Астафьевы</div>
        <h3>Астафьевы</h3>
        <p>{chain_text(mother_line[:4])}</p>
        <p>Линия матери Сергея — <b>Надежды Астафьевой</b> (1931, Дмитров — 1997, Долгопрудный). Дед <b>Алексей Астафьев</b>; бабушка <b>Мария Архиповна</b> — пока без девичьей фамилии в базе.</p>
        <div class="mini">Цель: девичья фамилия Марии Архиповны и предки Петра Астафьева</div>
      </div>
      <div class="card">
        <div class="tag">Линия матери · Скибы</div>
        <h3>Скибы</h3>
        <p>{chain_text(skiba_father[:5])}</p>
        <p>Донбасская ветвь: род из села <b>Лозовая Павловка</b> (ныне Луганщина). Дед <b>Алексей Скиба</b> (1907, Лозовая Павловка — 1955, Химки), прадед <b>Григорий</b> (р. 1879), прапрадед <b>Андрей Скиба</b>. Жена Алексея — <b>Маргарита Алексеева</b> (1909, Донецкая обл.) из донбасской ветви Алексеевых.</p>
        <div class="mini">Вглубь: метрики Славяносербского уезда Екатеринославской губернии</div>
      </div>
      <div class="card">
        <div class="tag">Линия матери · Поташкины и Захаровы</div>
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
      <h2>Химки · 25 ноября 2000</h2>
      <p><b>{esc(root.label)}</b> ({esc(root.years)}, {esc(root.birt_plac)}) и <b>{esc(spouse.label)}</b> ({esc(spouse.years)}, {esc(spouse.birt_plac)}) поженились в Химках. Дочь <b>{esc(child.label) if child else '—'}</b>{' (' + esc(child.years) + ')' if child else ''} — продолжение рода.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="card">
        <div class="tag">Ныне живущие</div>
        <h3>Сергей{child_line} и Надежда</h3>
        <p>Семейный архив ведётся в MyHeritage. Этот сайт — публичная витрина экспортированных данных.</p>
      </div>
      <div class="card">
        <div class="tag">Источник</div>
        <h3>MyHeritage · SKIBA</h3>
        <p>Экспорт GEDCOM 5.5.1 от {esc(export_date)}. {st['with_birth']} дат рождения, {st['with_death']} дат смерти, {st['families']} семейных пар.</p>
      </div>
    </div>
  </div>
</section>

<section class="src">
  <div class="wrap">
    <div class="sect-head">
      <div class="label">Достоверность</div>
      <h2>Источники</h2>
      <p>Данные взяты из семейного древа MyHeritage без ручных дополнений.</p>
      <div class="hr"></div>
    </div>
    <div class="grid g2">
      <div class="scard">
        <h3>Электронная база</h3>
        <ul>
          <li><b>MyHeritage</b> — проект SKIBA, экспорт GEDCOM</li>
          <li><b>Smart Matches</b> — совпадения по Скиба, Матюхиным</li>
          <li><b>Семейные фотографии</b> — альбомы в MyHeritage</li>
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
      <span><i style="background:rgba(58,16,40,.9);border:1px solid var(--border)"></i>установленный предок</span>
      <span><i style="border:1px dashed var(--line)"></i>связь не замкнута</span>
      <span><i style="background:rgba(14,143,75,.25);border:1px solid var(--green)"></i>ныне живущая семья</span>
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
