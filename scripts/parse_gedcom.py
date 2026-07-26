#!/usr/bin/env python3
"""Parse GEDCOM export from MyHeritage and expose structured family data."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MONTHS_RU = {
    "JAN": "января", "FEB": "февраля", "MAR": "марта", "APR": "апреля",
    "MAY": "мая", "JUN": "июня", "JUL": "июля", "AUG": "августа",
    "SEP": "сентября", "OCT": "октября", "NOV": "ноября", "DEC": "декабря",
}
MONTHS_RU_SHORT = {
    "JAN": "янв.", "FEB": "фев.", "MAR": "мар.", "APR": "апр.",
    "MAY": "мая", "JUN": "июн.", "JUL": "июл.", "AUG": "авг.",
    "SEP": "сен.", "OCT": "окт.", "NOV": "ноя.", "DEC": "дек.",
}
DATE_QUALIFIERS = {
    "ABT": "ок.", "BEF": "до", "AFT": "после", "EST": "ок.", "CAL": "ок.",
}


def format_date(value: str) -> str:
    """Render a GEDCOM date in Russian: '17 APR 1971' -> '17 апреля 1971'."""
    value = (value or "").strip()
    if not value:
        return ""

    range_match = re.match(r"^BET\s+(.+?)\s+AND\s+(.+)$", value, re.IGNORECASE)
    if range_match:
        return f"между {format_date(range_match.group(1))} и {format_date(range_match.group(2))}"

    prefix = ""
    head = value.split(" ", 1)[0].upper()
    if head in DATE_QUALIFIERS:
        prefix = DATE_QUALIFIERS[head] + " "
        value = value[len(head):].strip()

    full = re.match(r"^(\d{1,2})\s+([A-Z]{3})\s+(\d{4})$", value, re.IGNORECASE)
    if full:
        day, month, year = full.groups()
        return f"{prefix}{int(day)} {MONTHS_RU.get(month.upper(), month)} {year}"

    month_year = re.match(r"^([A-Z]{3})\s+(\d{4})$", value, re.IGNORECASE)
    if month_year:
        month, year = month_year.groups()
        return f"{prefix}{MONTHS_RU_SHORT.get(month.upper(), month)} {year}"

    return f"{prefix}{value}"


def clean_name(value: str) -> str:
    """Strip research artefacts from names: 'Иван(1)', '??????', trailing '?'."""
    value = re.sub(r"\(\d+\)", "", value or "")
    value = re.sub(r"\?{2,}", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


@dataclass
class Person:
    id: str
    givn: str = ""
    surn: str = ""
    sex: str = ""
    birt: str = ""
    birt_plac: str = ""
    deat: str = ""
    deat_plac: str = ""
    occu: str = ""
    note: str = ""
    fams: list[str] = field(default_factory=list)
    famc: str = ""
    email: str = ""

    @property
    def name(self) -> str:
        return clean_name(self.givn)

    @property
    def surname(self) -> str:
        return clean_name(self.surn)

    @property
    def label(self) -> str:
        if self.surname and self.name:
            return f"{self.surname} {self.name}"
        return self.name or self.surname or "неизвестный"

    @property
    def short(self) -> str:
        parts = self.name.split()
        if parts and self.surname:
            return f"{self.surname} {parts[0]}"
        return self.label

    @property
    def years(self) -> str:
        birth = format_date(self.birt)
        death = format_date(self.deat)
        if birth and death:
            return f"{birth} – {death}"
        if birth:
            return f"р. {birth}"
        if death:
            return f"ум. {death}"
        return "? – ?"

    @property
    def is_living(self) -> bool:
        return not self.deat

    @property
    def public_years(self) -> str:
        """Years safe to publish: living people are reduced to a birth year."""
        if self.is_living:
            year = year_only(self.birt)
            return f"р. {year}" if year else "ныне живущий"
        return self.years

    @property
    def public_place(self) -> str:
        """Birthplace is hidden for living people."""
        return "" if self.is_living else (self.birt_plac or self.deat_plac)


def year_only(date: str) -> str:
    """Extract a four-digit year from a GEDCOM date value."""
    match = re.search(r"\b(\d{4})\b", date or "")
    return match.group(1) if match else ""


@dataclass
class Family:
    id: str
    husb: str = ""
    wife: str = ""
    chil: list[str] = field(default_factory=list)
    marr: str = ""
    marr_plac: str = ""


def _load_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")


def _parse_records(text: str) -> list[dict[str, Any]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in lines:
        if not line.strip():
            continue
        line = line.lstrip("\ufeff")
        match = re.match(r"^(\d+)\s+(@[^@]+@\s+)?(\S+)(?:\s+(.*))?$", line)
        if not match:
            continue
        level = int(match.group(1))
        xref = (match.group(2) or "").strip() or None
        tag = match.group(3)
        value = match.group(4) or ""

        if level == 0:
            current = {"xref": xref, "tag": tag, "items": []}
            records.append(current)
            continue
        if current is not None:
            current["items"].append((level, tag, value, xref))

    return records


def _walk_items(items: list[tuple[int, str, str, str | None]]):
    ctx: list[tuple[int, str]] = []
    for level, tag, value, _xref in items:
        while ctx and ctx[-1][0] >= level:
            ctx.pop()
        ctx.append((level, tag))
        path = tuple(t for _, t in ctx)
        yield path, tag, value


def parse_gedcom(path: Path) -> tuple[dict[str, Person], dict[str, Family], dict[str, str]]:
    records = _parse_records(_load_text(path))
    people: dict[str, Person] = {}
    families: dict[str, Family] = {}
    meta: dict[str, str] = {}

    for record in records:
        if record["tag"] == "HEAD":
            for path, tag, value in _walk_items(record["items"]):
                if path == ("FILE",):
                    meta["file"] = value
                elif path == ("DATE",):
                    meta["date"] = value
        elif record["tag"] == "INDI":
            person = Person(id=record["xref"] or "")
            for path, tag, value in _walk_items(record["items"]):
                if path == ("NAME", "GIVN"):
                    person.givn = value
                elif path == ("NAME", "SURN"):
                    person.surn = value
                elif path == ("SEX",):
                    person.sex = value
                elif path == ("BIRT", "DATE"):
                    person.birt = value
                elif path == ("BIRT", "PLAC"):
                    person.birt_plac = value
                elif path == ("DEAT", "DATE"):
                    person.deat = value
                elif path == ("DEAT", "PLAC"):
                    person.deat_plac = value
                elif path == ("OCCU",):
                    person.occu = value
                elif path == ("NOTE",):
                    person.note = value
                elif path == ("FAMS",):
                    person.fams.append(value)
                elif path == ("FAMC",):
                    person.famc = value
                elif path == ("RESI", "EMAIL"):
                    person.email = value  # kept in memory only, never rendered
            people[person.id] = person
        elif record["tag"] == "FAM":
            family = Family(id=record["xref"] or "")
            for path, tag, value in _walk_items(record["items"]):
                if path == ("HUSB",):
                    family.husb = value
                elif path == ("WIFE",):
                    family.wife = value
                elif path == ("CHIL",):
                    family.chil.append(value)
                elif path == ("MARR", "DATE"):
                    family.marr = value
                elif path == ("MARR", "PLAC"):
                    family.marr_plac = value
            families[family.id] = family

    return people, families, meta


def ancestors(
    person_id: str,
    people: dict[str, Person],
    families: dict[str, Family],
    max_depth: int = 8,
) -> list[tuple[int, Person, str]]:
    """Return (depth, person, side) where side is self/father/mother lineage marker."""

    result: list[tuple[int, Person, str]] = []

    def walk(pid: str, depth: int, side: str) -> None:
        if depth > max_depth or pid not in people:
            return
        person = people[pid]
        result.append((depth, person, side))
        if not person.famc or person.famc not in families:
            return
        family = families[person.famc]
        if family.husb:
            walk(family.husb, depth + 1, "father" if depth == 0 else side)
        if family.wife:
            walk(family.wife, depth + 1, "mother" if depth == 0 else side)

    walk(person_id, 0, "self")
    return result


def direct_lines(
    root_id: str,
    people: dict[str, Person],
    families: dict[str, Family],
    generations: int = 5,
) -> dict[str, list[Person]]:
    """Build paternal and maternal ancestor chains."""

    def chain(pid: str, follow: str, depth: int = 0) -> list[Person]:
        out: list[Person] = []
        current = pid
        while depth < generations and current in people:
            person = people[current]
            out.append(person)
            if not person.famc or person.famc not in families:
                break
            family = families[person.famc]
            parent = family.husb if follow == "father" else family.wife
            if not parent:
                break
            current = parent
            depth += 1
        return out

    root = people[root_id]
    lines: dict[str, list[Person]] = {
        "father": chain(root_id, "father"),
        "mother": chain(root_id, "mother"),
    }

    if root.famc in families:
        family = families[root.famc]
        if family.wife:
            lines["mother_branch"] = chain(family.wife, "mother")
        if family.husb:
            lines["father_branch"] = chain(family.husb, "father")

    return lines


def canonical_surname(surname: str, known: set[str]) -> str:
    """Fold feminine surname forms into masculine ones (Матюхина → Матюхин)."""
    if surname.endswith("ая"):
        masculine = surname[:-2] + "ий"
        if masculine in known:
            return masculine
    if surname.endswith("а") and surname[:-1] in known:
        return surname[:-1]
    return surname


def stats(people: dict[str, Person], families: dict[str, Family]) -> dict[str, Any]:
    raw_surnames = {p.surname for p in people.values() if p.surname}
    surnames = Counter(
        canonical_surname(p.surname, raw_surnames) for p in people.values() if p.surname
    )
    places = Counter()
    for person in people.values():
        for place in (person.birt_plac, person.deat_plac):
            if place.strip():
                places[place.strip()] += 1

    birth_years = [int(y) for y in (year_only(p.birt) for p in people.values()) if y]
    return {
        "people": len(people),
        "families": len(families),
        "surnames": len(surnames),
        "top_surnames": surnames.most_common(12),
        "top_places": places.most_common(12),
        "with_birth": sum(1 for p in people.values() if p.birt),
        "with_death": sum(1 for p in people.values() if p.deat),
        "earliest_year": min(birth_years, default=0),
    }


if __name__ == "__main__":
    ged = Path(__file__).resolve().parents[1] / "data" / "skiba.ged"
    people, families, meta = parse_gedcom(ged)
    root = "@I1@"
    p = people[root]
    print(json.dumps({
        "meta": meta,
        "root": p.label,
        "years": p.years,
        "stats": stats(people, families),
        "father_line": [x.short for x in direct_lines(root, people, families)["father"][:6]],
        "mother_line": [x.short for x in direct_lines(root, people, families)["mother"][:6]],
    }, ensure_ascii=False, indent=2))
