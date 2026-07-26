# Род Матюхиных и Скиба — семейный архив

Статический сайт семейного архива, сгенерированный из GEDCOM-экспорта MyHeritage (проект SKIBA).

## Структура

- `data/skiba.ged` — исходный GEDCOM (233 человека, 90 семей)
- `scripts/parse_gedcom.py` — парсер GEDCOM
- `scripts/build_site.py` — генератор `index.html`
- `assets/site.css` — стили (по образцу [баталовы.древо.рус](https://баталовы.древо.рус/))
- `index.html` — готовый сайт (летопись + SVG-древо)

## Пересборка сайта

```bash
python3 scripts/build_site.py
```

## Локальный просмотр

```bash
python3 -m http.server 8080
```

Откройте http://localhost:8080

## GitHub Pages

Сайт публикуется как статический `index.html` из корня репозитория (файл `.nojekyll` отключает Jekyll).
