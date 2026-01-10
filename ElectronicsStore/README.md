# Electronics Store — Вариант 1 (магазин бытовой техники)

Минимальный прототип практической работы для нечетного варианта — магазин бытовой техники.

Содержит:
- `schema.sql` — схема SQLite БД.
- `data/` — CSV с примерными записями для таблиц `categories` и `products`.
- `app.py` — минимальный Flask-прототип интерфейса с поиском/сортировкой/фильтрацией.
- `requirements.txt` — зависимости Python.

Как запустить (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r ElectronicsStore/requirements.txt
python ElectronicsStore/app.py
```

Откройте http://127.0.0.1:5000/ и попробуйте фильтры/поиск/сортировку.
