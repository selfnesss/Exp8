# Clothing Store — Вариант 2 (проект)

Краткая реализация практической работы (вариант 2 — магазин одежды).

Содержит:
- `schema.sql` — схема SQLite БД (аналог структуры в примере).
- `data/` — CSV с примерными записями для таблиц `categories` и `products`.
- `app.py` — минимальный Flask-прототип интерфейса с поиском/сортировкой/фильтрацией.
- `requirements.txt` — зависимости Python.

Как запустить (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r ClothingStore/requirements.txt
python ClothingStore/app.py
```

Откройте http://127.0.0.1:5000/ и попробуйте фильтры/поиск/сортировку.

Чтобы добавить в ваш репозиторий GitHub: выполните `git add`, `git commit` и `git push`.
