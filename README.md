# Род Матюхиных и Скиба — семейный архив

Статический сайт семейного архива, сгенерированный из GEDCOM-экспорта MyHeritage (проект SKIBA).

## Приватность

GEDCOM содержит точные даты рождения, места и контакты **ныне живущих** людей, поэтому он **не хранится в репозитории** (см. `.gitignore`). Положите свой экспорт в `data/skiba.ged` локально перед сборкой.

Генератор автоматически защищает живых: для человека без даты смерти публикуется только **год рождения** («р. 1971»), места рождения и e-mail не выводятся вообще.

## Структура

- `data/skiba.ged` — исходный GEDCOM, локально, не коммитится
- `content/content.yaml` — тексты сайта (заголовки, абзацы, подписи; без GEDCOM-данных)
- `requirements.txt` — минимальные Python-зависимости для сборки
- `scripts/parse_gedcom.py` — парсер GEDCOM
- `scripts/build_site.py` — генератор `index.html` (читает GEDCOM и `content/content.yaml`)
- `assets/site.css` — стили
- `index.html` — готовый сайт (летопись + SVG-древо)

## Редактирование текстов и пересборка

Статические тексты (заголовки, абзацы летописи, подписи к разделам, легенда древа) лежат в `content/content.yaml`. Имена, даты, цепочки предков и статистика по-прежнему берутся из GEDCOM в Python — в абзацах YAML нет плейсхолдеров.

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build_site.py
```

## Локальный просмотр

```bash
python3 -m http.server 8080
```

Откройте http://localhost:8080

## GitHub Pages

Сайт публикуется из ветки `gh-pages`, а её содержимое автоматически обновляется после merge в `master` через GitHub Actions (`.github/workflows/pages.yml`).

### Предварительные настройки репозитория

1. Включите права записи для workflow:
   - `Settings` → `Actions` → `General` → `Workflow permissions`
   - выберите `Read and write permissions`
2. Проверьте правила для ветки `gh-pages`:
   - workflow делает `git push --force` в `gh-pages`
   - если включены branch protection/rulesets, они должны разрешать этот push для GitHub Actions (иначе публикация будет блокироваться)

### Рабочий процесс публикации

1. Правите `content/content.yaml` (или другие исходники сайта)
2. Локально пересобираете `index.html`
3. Коммитите изменения в `master` (обычно через PR и merge)
4. После merge workflow публикует в `gh-pages` **только**:
   - `index.html`
   - `.nojekyll`
   - `assets/`

Важно: GitHub Actions в этом репозитории **не пересобирает** сайт из GEDCOM, потому что GEDCOM не хранится в репозитории. Поэтому перед merge обновлённый `index.html` должен быть уже закоммичен.
