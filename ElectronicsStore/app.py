from pathlib import Path
import sqlite3
from flask import Flask, render_template_string, request, g, redirect
import csv

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / 'electronics.db'

def init_db():
    if DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    sql = (BASE / 'schema.sql').read_text(encoding='utf-8')
    cur.executescript(sql)
    # load sample data
    with open(BASE / 'data' / 'categories.csv', encoding='utf-8') as f:
        dr = csv.DictReader(f)
        for r in dr:
            cur.execute('INSERT OR IGNORE INTO categories(id,name) VALUES(?,?)', (r['id'], r['name']))
    with open(BASE / 'data' / 'products.csv', encoding='utf-8') as f:
        dr = csv.DictReader(f)
        for r in dr:
            cur.execute('''INSERT OR IGNORE INTO products(id,name,brand,model,spec,price,stock,rating,category_id,description,image)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (
                r['id'], r['name'], r['brand'], r.get('model',''), r.get('spec',''), float(r['price']), int(r['stock']), float(r['rating']), int(r['category_id']), r.get('description',''), r.get('image','')
            ))
    with open(BASE / 'data' / 'customers.csv', encoding='utf-8') as f:
        dr = csv.DictReader(f)
        for r in dr:
            cur.execute('INSERT OR IGNORE INTO customers(id,first_name,last_name,phone,email) VALUES(?,?,?,?,?)', (
                r['id'], r['first_name'], r['last_name'], r['phone'], r['email']
            ))
    con.commit()
    con.close()

def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        ensure_orders_status_column(db)
    return db

ORDER_STATUSES = ['Новый', 'В обработке', 'Отправлен', 'Доставлен', 'Отменен']
ORDER_STATUS_CLASSES = {
    'Новый': 'new',
    'В обработке': 'processing',
    'Отправлен': 'shipped',
    'Доставлен': 'delivered',
    'Отменен': 'canceled',
}

def ensure_orders_status_column(db):
    if getattr(g, '_orders_status_checked', False):
        return
    cols = [row['name'] for row in db.execute('PRAGMA table_info(orders)').fetchall()]
    if 'status' not in cols:
        db.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Новый'")
        db.execute("UPDATE orders SET status = 'Новый' WHERE status IS NULL")
        db.commit()
    g._orders_status_checked = True

app = Flask(__name__)

INDEX_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Electronics Store — Прототип</title>
<style>
:root {
    --bg: #f6f4f1;
    --paper: #ffffff;
    --ink: #1f2a37;
    --muted: #6b7280;
    --line: #e5e7eb;
    --accent: #b45309;
}
body {
    font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif;
    background-color: var(--bg);
    margin: 24px;
    color: var(--ink);
}
h2 {
    color: var(--ink);
    text-align: center;
    letter-spacing: 0.3px;
}
form {
    background-color: var(--paper);
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08);
    margin-bottom: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    border: 1px solid var(--line);
}
form input, form select, form button {
    padding: 8px 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #fff;
}
form input, form select {
    color: var(--ink);
}
form button {
    background-color: var(--ink);
    color: #fff;
    cursor: pointer;
    border: none;
}
form button:hover {
    background-color: #111827;
}
table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    background-color: var(--paper);
    box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--line);
}
nav.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 16px;
    justify-content: center;
    margin: 6px 0 18px;
    font-size: 13px;
    color: var(--muted);
}
nav.actions a {
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
    padding: 4px 0;
    border-bottom: 2px solid transparent;
}
nav.actions a:hover {
    border-bottom-color: var(--accent);
}
th, td {
    padding: 12px 14px;
    text-align: left;
    border-bottom: 1px solid var(--line);
}
th {
    background-color: #f3f4f6;
    color: var(--ink);
    font-weight: 700;
    text-transform: uppercase;
    font-size: 12px;
    letter-spacing: 0.6px;
}
tr:nth-child(even) {
    background-color: #fafafa;
}
tr:hover {
    background-color: #fef3c7;
}
img {
    max-width: 96px;
    height: auto;
    border-radius: 8px;
}
</style>
</head>
<body>
<h2>Товары</h2>
<nav class="actions">
  <a href="/add_product">Добавить новый товар</a>
  <a href="/add_customer">Добавить нового клиента</a>
  <a href="/customers">Просмотр клиентов</a>
  <a href="/add_order">Добавить новый заказ</a>
  <a href="/orders">Просмотр заказов</a>
</nav>
<form method="get">
  Поиск: <input name="q" value="{{q}}" placeholder="Поиск по названию, описанию или бренду"> 
  Категория: <select name="cat"><option value="">Все</option>{% for c in cats %}<option value="{{c.id}}" {% if cat and cat|int == c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select>
  Сортировка: <select name="sort"><option value="name">Название</option><option value="price">Цена</option><option value="rating">Рейтинг</option></select>
  <button>Применить</button>
</form>
<table>
<tr><th>Изображение</th><th>Название</th><th>Бренд</th><th>Модель/Спецификация</th><th>Описание</th><th>Цена</th><th>Запас</th><th>Рейтинг</th><th>Категория</th><th>Действия</th></tr>
{% for p in products %}
<tr>
  <td>{% if p.image %}<img src="{{p.image}}" alt="{{p.name}}">{% endif %}</td>
  <td>{{p.name}}</td>
  <td>{{p.brand}}</td>
  <td>{{p.model}} {{p.spec}}</td>
  <td>{{p.description}}</td>
  <td>{{p.price}}</td>
  <td>{{p.stock}}</td>
  <td>{{p.rating}}</td>
  <td>{{p.category}}</td>
  <td><a href="/edit_product/{{p.id}}">Редактировать</a> | <a href="/delete_product/{{p.id}}" onclick="return confirm('Удалить?')">Удалить</a></td>
</tr>
{% endfor %}
</table>
</body>
</html>
'''

ADD_PRODUCT_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Add Product — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
form { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
form input, form select, form textarea { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
form button { background-color: #3498db; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
form button:hover { background-color: #2980b9; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
table { width: 100%; border-collapse: separate; border-spacing: 0; background-color: var(--paper); box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--line); }
th { background-color: #f3f4f6; color: var(--ink); font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: 0.6px; }
tr:nth-child(even) { background-color: #fafafa; }
tr:hover { background-color: #fef3c7; }
</style>
</head>
<body>
<h2>Добавить новый товар</h2>
<form method="post">
  <input name="name" placeholder="Название товара" required>
  <input name="brand" placeholder="Бренд">
  <input name="model" placeholder="Модель">
  <input name="spec" placeholder="Спецификации">
  <input name="price" type="number" step="0.01" placeholder="Цена" required>
  <input name="stock" type="number" placeholder="Запас" required>
  <input name="rating" type="number" step="0.1" placeholder="Рейтинг">
  <select name="category_id" required>
    <option value="">Выберите категорию</option>
    {% for c in cats %}
    <option value="{{c.id}}">{{c.name}}</option>
    {% endfor %}
  </select>
  <textarea name="description" placeholder="Описание"></textarea>
  <input name="image" placeholder="URL изображения">
  <button>Добавить товар</button>
</form>
<p><a class="btn-link" href="/">Назад к товарам</a></p>
</body>
</html>
'''

ADD_CUSTOMER_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Add Customer — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
form { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
form input { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
form button { background-color: #3498db; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
form button:hover { background-color: #2980b9; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
</head>
<body>
<h2>Добавить нового клиента</h2>
<form method="post">
  <input name="first_name" placeholder="Имя" required>
  <input name="last_name" placeholder="Фамилия" required>
  <input name="phone" placeholder="Телефон" required>
  <input name="email" placeholder="Email" required>
  <button>Добавить клиента</button>
</form>
<p><a class="btn-link" href="/">Назад к товарам</a></p>
</body>
</html>
'''

CUSTOMERS_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Customers — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
table { width: 100%; border-collapse: collapse; background-color: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
th { background-color: #34495e; color: white; }
tr:nth-child(even) { background-color: #f9f9f9; }
tr:hover { background-color: #e8f4fd; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
table { width: 100%; border-collapse: separate; border-spacing: 0; background-color: var(--paper); box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--line); }
th { background-color: #f3f4f6; color: var(--ink); font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: 0.6px; }
tr:nth-child(even) { background-color: #fafafa; }
tr:hover { background-color: #fef3c7; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
</head>
<body>
<h2>Клиенты</h2>
<table>
<tr><th>ID</th><th>Имя</th><th>Фамилия</th><th>Телефон</th><th>Email</th><th>Действия</th></tr>
{% for c in customers %}
<tr>
  <td>{{c.id}}</td>
  <td>{{c.first_name}}</td>
  <td>{{c.last_name}}</td>
  <td>{{c.phone}}</td>
  <td>{{c.email}}</td>
  <td><a href="/edit_customer/{{c.id}}">Редактировать</a> | <a href="/delete_customer/{{c.id}}" onclick="return confirm('Удалить?')">Удалить</a></td>
</tr>
{% endfor %}
</table>
<p><a class="btn-link" href="/">Назад к товарам</a></p>
</body>
</html>
'''

ADD_ORDER_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Add Order — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
form { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }
form select, form input { padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
.product-row { display: flex; align-items: center; margin: 10px 0; }
.product-row select, .product-row input { margin-right: 10px; }
button { background-color: #3498db; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; }
button:hover { background-color: #2980b9; }
.add-product { margin-top: 10px; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
<script>
function addProduct() {
    const container = document.getElementById('products-container');
    const row = document.createElement('div');
    row.className = 'product-row';
    row.innerHTML = `
        <select name="product_ids">
            <option value="">Select Product</option>
            {% for p in products %}
            <option value="{{p.id}}">{{p.name}} ({{p.price}})</option>
            {% endfor %}
        </select>
        <input name="quantities" type="number" min="1" placeholder="Quantity" required>
        <button type="button" onclick="removeProduct(this)">Remove</button>
    `;
    container.appendChild(row);
}
function removeProduct(btn) {
    btn.parentElement.remove();
}
</script>
</head>
<body>
<h2>Добавить новый заказ</h2>
<form method="post">
  <select name="customer_id" required>
    <option value="">Выберите клиента</option>
    {% for c in customers %}
    <option value="{{c.id}}">{{c.first_name}} {{c.last_name}} ({{c.email}})</option>
    {% endfor %}
  </select>
  <select name="status" required>
    {% for s in order_statuses %}
    <option value="{{s}}">{{s}}</option>
    {% endfor %}
  </select>
  <div id="products-container">
    <div class="product-row">
      <select name="product_ids" required>
        <option value="">Выберите товар</option>
        {% for p in products %}
        <option value="{{p.id}}">{{p.name}} ({{p.price}})</option>
        {% endfor %}
      </select>
      <input name="quantities" type="number" min="1" placeholder="Количество" required>
    </div>
  </div>
  <button type="button" class="add-product" onclick="addProduct()">Добавить ещё товар</button>
  <br><br>
  <button type="submit">Создать заказ</button>
</form>
<p><a class="btn-link" href="/">Назад к товарам</a></p>
</body>
</html>
'''

ORDERS_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Orders — Electronics Store</title>
<style>
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form.filter { background-color: var(--paper); padding: 12px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; border: 1px solid var(--line); }
form.filter label { font-size: 13px; color: var(--muted); }
form.filter select, form.filter input { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form.filter button { background-color: var(--ink); color: #fff; border: none; border-radius: 8px; padding: 8px 12px; cursor: pointer; }
form.filter button:hover { background-color: #111827; }
table { width: 100%; border-collapse: separate; border-spacing: 0; background-color: var(--paper); box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--line); }
th { background-color: #f3f4f6; color: var(--ink); font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: 0.6px; }
tr:nth-child(even) { background-color: #fafafa; }
tr:hover { background-color: #fef3c7; }
.status-select { padding: 6px; border-radius: 16px; border: 1px solid #ddd; font-weight: 600; cursor: pointer; }
.status-new { background: #e3f2fd; color: #1565c0; }
.status-processing { background: #fff8e1; color: #8d6e63; }
.status-shipped { background: #ede7f6; color: #5e35b1; }
.status-delivered { background: #e8f5e9; color: #2e7d32; }
.status-canceled { background: #ffebee; color: #c62828; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
<script>
function updateStatusClass(selectEl) {
    const option = selectEl.options[selectEl.selectedIndex];
    const cls = option.getAttribute('data-status-class') || 'new';
    selectEl.className = 'status-select status-' + cls;
    if (selectEl.form) {
        selectEl.form.submit();
    }
}
window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.status-select').forEach((selectEl) => {
        selectEl.addEventListener('change', () => updateStatusClass(selectEl));
    });
});
</script>
</head>
<body>
<h2>Заказы</h2>
<form class="filter" method="get">
  <label>Статус:
    <select name="status">
      <option value="">Все</option>
      {% for s in order_statuses %}
      <option value="{{s}}" {% if status == s %}selected{% endif %}>{{s}}</option>
      {% endfor %}
    </select>
  </label>
  <label>Дата с:
    <input type="date" name="date_from" value="{{date_from}}">
  </label>
  <label>Дата по:
    <input type="date" name="date_to" value="{{date_to}}">
  </label>
  <label>Сортировка:
    <select name="sort">
      <option value="created_desc" {% if sort == 'created_desc' %}selected{% endif %}>Сначала новые</option>
      <option value="created_asc" {% if sort == 'created_asc' %}selected{% endif %}>Сначала старые</option>
      <option value="total_desc" {% if sort == 'total_desc' %}selected{% endif %}>Сумма по убыванию</option>
      <option value="total_asc" {% if sort == 'total_asc' %}selected{% endif %}>Сумма по возрастанию</option>
      <option value="status_asc" {% if sort == 'status_asc' %}selected{% endif %}>Статус A→Я</option>
    </select>
  </label>
  <button type="submit">Применить</button>
</form>
<table>
<tr><th>ID</th><th>Клиент</th><th>Дата создания</th><th>Сумма</th><th>Статус</th><th>Товары</th></tr>
{% for o in orders %}
<tr>
  <td><a href="/orders/{{o.id}}">{{o.id}}</a></td>
  <td>{{o.first_name}} {{o.last_name}} ({{o.email}})</td>
  <td>{{o.created_at}}</td>
  <td>{{o.total}}</td>
  <td>
    <form method="post" action="/orders/update_status">
      <input type="hidden" name="order_id" value="{{o.id}}">
      <select name="status" class="status-select status-{{ status_classes.get(o.status, 'new') }}">
        {% for s in order_statuses %}
        <option value="{{s}}" data-status-class="{{ status_classes.get(s, 'new') }}" {% if o.status == s %}selected{% endif %}>{{s}}</option>
        {% endfor %}
      </select>
    </form>
  </td>
  <td>{{o.items or 'Нет товаров'}}</td>
</tr>
{% endfor %}
</table>
<p><a class="btn-link" href="/">Назад к товарам</a></p>
</body>
</html>
'''

ORDER_DETAIL_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Order Details — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
.card { background-color: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); margin-bottom: 16px; }
.row { display: flex; flex-wrap: wrap; gap: 16px; }
table { width: 100%; border-collapse: collapse; background-color: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
th { background-color: #34495e; color: white; }
.status-select { padding: 6px; border-radius: 16px; border: 1px solid #ddd; font-weight: 600; cursor: pointer; }
.status-new { background: #e3f2fd; color: #1565c0; }
.status-processing { background: #fff8e1; color: #8d6e63; }
.status-shipped { background: #ede7f6; color: #5e35b1; }
.status-delivered { background: #e8f5e9; color: #2e7d32; }
.status-canceled { background: #ffebee; color: #c62828; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
table { width: 100%; border-collapse: separate; border-spacing: 0; background-color: var(--paper); box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--line); }
th { background-color: #f3f4f6; color: var(--ink); font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: 0.6px; }
tr:nth-child(even) { background-color: #fafafa; }
tr:hover { background-color: #fef3c7; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
<script>
function updateStatusClass(selectEl) {
    const option = selectEl.options[selectEl.selectedIndex];
    const cls = option.getAttribute('data-status-class') || 'new';
    selectEl.className = 'status-select status-' + cls;
    if (selectEl.form) {
        selectEl.form.submit();
    }
}
window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.status-select').forEach((selectEl) => {
        selectEl.addEventListener('change', () => updateStatusClass(selectEl));
    });
});
</script>
</head>
<body>
<h2>Заказ #{{order.id}}</h2>
<div class="card">
  <div class="row">
    <div>Клиент: {{order.first_name}} {{order.last_name}} ({{order.email}})</div>
    <div>Дата: {{order.created_at}}</div>
    <div>Сумма: {{order.total}}</div>
  </div>
  <div style="margin-top: 10px;">
    <form method="post" action="/orders/update_status">
      <input type="hidden" name="order_id" value="{{order.id}}">
      <select name="status" class="status-select status-{{ status_classes.get(order.status, 'new') }}">
        {% for s in order_statuses %}
        <option value="{{s}}" data-status-class="{{ status_classes.get(s, 'new') }}" {% if order.status == s %}selected{% endif %}>{{s}}</option>
        {% endfor %}
      </select>
    </form>
  </div>
</div>
<table>
  <tr><th>Товар</th><th>Цена</th><th>Кол-во</th><th>Сумма</th></tr>
  {% for i in items %}
  <tr>
    <td>{{i.name}}</td>
    <td>{{i.price}}</td>
    <td>{{i.quantity}}</td>
    <td>{{i.subtotal}}</td>
  </tr>
  {% endfor %}
</table>
<p><a class="btn-link" href="/orders">Назад к заказам</a></p>
</body>
</html>
'''

EDIT_PRODUCT_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Edit Product — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
form { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
form input, form select, form textarea { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
form button { background-color: #3498db; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
form button:hover { background-color: #2980b9; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
</head>
<body>
<h2>Редактировать товар</h2>
<form method="post">
  <input name="name" value="{{product.name}}" placeholder="Название товара" required>
  <input name="brand" value="{{product.brand}}" placeholder="Бренд">
  <input name="model" value="{{product.model}}" placeholder="Модель">
  <input name="spec" value="{{product.spec}}" placeholder="Спецификации">
  <input name="price" type="number" step="0.01" value="{{product.price}}" placeholder="Цена" required>
  <input name="stock" type="number" value="{{product.stock}}" placeholder="Запас" required>
  <input name="rating" type="number" step="0.1" value="{{product.rating}}" placeholder="Рейтинг">
  <select name="category_id" required>
    <option value="">Выберите категорию</option>
    {% for c in cats %}
    <option value="{{c.id}}" {% if c.id == product.category_id %}selected{% endif %}>{{c.name}}</option>
    {% endfor %}
  </select>
  <textarea name="description" placeholder="Описание">{{product.description}}</textarea>
  <input name="image" value="{{product.image}}" placeholder="URL изображения">
  <button>Обновить товар</button>
</form>
<p><a class="btn-link" href="/">Назад к товарам</a></p>
</body>
</html>
'''

EDIT_CUSTOMER_HTML = '''
<!doctype html>
<html lang="ru">
<head>
<title>Edit Customer — Electronics Store</title>
<style>
body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
h2 { color: #2c3e50; text-align: center; }
form { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
form input { width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
form button { background-color: #3498db; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
form button:hover { background-color: #2980b9; }
/* Base theme */
:root { --bg: #f6f4f1; --paper: #ffffff; --ink: #1f2a37; --muted: #6b7280; --line: #e5e7eb; --accent: #b45309; }
body { font-family: "Trebuchet MS", "Lucida Sans Unicode", "Lucida Grande", sans-serif; background-color: var(--bg); margin: 24px; color: var(--ink); }
h2 { color: var(--ink); text-align: center; letter-spacing: 0.3px; }
form { background-color: var(--paper); padding: 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(31, 41, 55, 0.08); margin-bottom: 16px; border: 1px solid var(--line); }
form input, form select, form textarea, form button { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--ink); }
form button { background-color: var(--ink); color: #fff; cursor: pointer; border: none; }
form button:hover { background-color: #111827; }
.btn-link { display: inline-block; padding: 8px 14px; border-radius: 999px; background: #eef2f7; color: #2c3e50; text-decoration: none; font-weight: 600; }
.btn-link:hover { background: #e2e8f0; }
</style>
</head>
<body>
<h2>Редактировать клиента</h2>
<form method="post">
  <input name="first_name" value="{{customer.first_name}}" placeholder="Имя" required>
  <input name="last_name" value="{{customer.last_name}}" placeholder="Фамилия" required>
  <input name="phone" value="{{customer.phone}}" placeholder="Телефон" required>
  <input name="email" value="{{customer.email}}" placeholder="Email" required>
  <button>Обновить клиента</button>
</form>
<p><a class="btn-link" href="/customers">Назад к клиентам</a></p>
</body>
</html>
'''

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_db', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    q = request.args.get('q','').strip()
    cat = request.args.get('cat','')
    sort = request.args.get('sort','name')
    db = get_db()
    cats = db.execute('SELECT * FROM categories').fetchall()
    params = []
    where = []
    if q:
        where.append("(p.name LIKE ? OR p.description LIKE ? OR p.brand LIKE ?)")
        params += [f'%{q}%']*3
    if cat:
        where.append('p.category_id = ?')
        params.append(cat)
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
    if sort not in ('name','price','rating'):
        sort = 'name'
    sql = f"SELECT p.*, c.name as category FROM products p LEFT JOIN categories c ON p.category_id=c.id {where_sql} ORDER BY p.{sort}"
    products = db.execute(sql, params).fetchall()
    return render_template_string(INDEX_HTML, products=products, cats=cats, q=q, cat=cat)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        model = request.form.get('model')
        spec = request.form.get('spec')
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        rating = float(request.form.get('rating', 0))
        category_id = int(request.form.get('category_id', 0))
        description = request.form.get('description')
        image = request.form.get('image')
        db = get_db()
        db.execute('''INSERT INTO products (name, brand, model, spec, price, stock, rating, category_id, description, image)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                   (name, brand, model, spec, price, stock, rating, category_id, description, image))
        db.commit()
        return redirect('/')
    db = get_db()
    cats = db.execute('SELECT * FROM categories').fetchall()
    return render_template_string(ADD_PRODUCT_HTML, cats=cats)

@app.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        db = get_db()
        db.execute('''INSERT INTO customers (first_name, last_name, phone, email)
                      VALUES (?, ?, ?, ?)''', 
                   (first_name, last_name, phone, email))
        db.commit()
        return redirect('/')
    return render_template_string(ADD_CUSTOMER_HTML)

@app.route('/customers')
def customers():
    db = get_db()
    customers_list = db.execute('SELECT * FROM customers').fetchall()
    return render_template_string(CUSTOMERS_HTML, customers=customers_list)

@app.route('/add_order', methods=['GET', 'POST'])
def add_order():
    db = get_db()
    customers_list = db.execute('SELECT * FROM customers').fetchall()
    products_list = db.execute('SELECT * FROM products').fetchall()
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        if not customer_id:
            return "Error: Select customer", 400
        customer_id = int(customer_id)
        status = request.form.get('status', 'Новый')
        if status not in ORDER_STATUSES:
            status = 'Новый'
        product_ids = request.form.getlist('product_ids')
        quantities = request.form.getlist('quantities')
        if len(product_ids) != len(quantities):
            return "Error: Mismatch in products and quantities", 400
        total = 0
        cursor = db.execute(
            'INSERT INTO orders (customer_id, created_at, total, status) VALUES (?, datetime("now"), 0, ?)',
            (customer_id, status)
        )
        order_id = cursor.lastrowid
        for pid_str, qty_str in zip(product_ids, quantities):
            if not pid_str or not qty_str:
                continue
            try:
                pid = int(pid_str)
                qty = int(qty_str)
                if qty <= 0:
                    continue
            except ValueError:
                continue
            product = db.execute('SELECT price FROM products WHERE id = ?', (pid,)).fetchone()
            if product:
                price = product[0]
                db.execute('INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)', (order_id, pid, qty, price))
                total += price * qty
        db.execute('UPDATE orders SET total = ? WHERE id = ?', (total, order_id))
        db.commit()
        return redirect('/orders')
    return render_template_string(
        ADD_ORDER_HTML,
        customers=customers_list,
        products=products_list,
        order_statuses=ORDER_STATUSES
    )

@app.route('/orders')
def orders():
    db = get_db()
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sort = request.args.get('sort', 'created_desc')
    sort_map = {
        'created_desc': 'o.created_at DESC',
        'created_asc': 'o.created_at ASC',
        'total_desc': 'o.total DESC',
        'total_asc': 'o.total ASC',
        'status_asc': 'o.status ASC',
    }
    sort_sql = sort_map.get(sort, sort_map['created_desc'])
    where = []
    params = []
    if status:
        where.append('o.status = ?')
        params.append(status)
    if date_from:
        where.append('date(o.created_at) >= date(?)')
        params.append(date_from)
    if date_to:
        where.append('date(o.created_at) <= date(?)')
        params.append(date_to)
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
    orders_list = db.execute(f'''
        SELECT o.id, o.created_at, o.total, o.status, c.first_name, c.last_name, c.email,
               GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')', '; ') as items
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        LEFT JOIN products p ON oi.product_id = p.id
        {where_sql}
        GROUP BY o.id
        ORDER BY {sort_sql}
    ''', params).fetchall()
    return render_template_string(
        ORDERS_HTML,
        orders=orders_list,
        order_statuses=ORDER_STATUSES,
        status_classes=ORDER_STATUS_CLASSES,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort=sort
    )

@app.route('/orders/<int:order_id>')
def order_detail(order_id):
    db = get_db()
    order = db.execute('''
        SELECT o.id, o.created_at, o.total, o.status, c.first_name, c.last_name, c.email
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.id = ?
    ''', (order_id,)).fetchone()
    if order is None:
        return "Order not found", 404
    items = db.execute('''
        SELECT p.name, oi.price, oi.quantity, (oi.price * oi.quantity) AS subtotal
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    return render_template_string(
        ORDER_DETAIL_HTML,
        order=order,
        items=items,
        order_statuses=ORDER_STATUSES,
        status_classes=ORDER_STATUS_CLASSES
    )

@app.route('/orders/update_status', methods=['POST'])
def update_order_status():
    order_id = request.form.get('order_id')
    status = request.form.get('status', '')
    if status not in ORDER_STATUSES:
        return "Error: Invalid status", 400
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return "Error: Invalid order id", 400
    db = get_db()
    db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    db.commit()
    return redirect(request.referrer or '/orders')

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        model = request.form.get('model')
        spec = request.form.get('spec')
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        rating = float(request.form.get('rating', 0))
        category_id = int(request.form.get('category_id', 0))
        description = request.form.get('description')
        image = request.form.get('image')
        db.execute('''UPDATE products SET name=?, brand=?, model=?, spec=?, price=?, stock=?, rating=?, category_id=?, description=?, image=? WHERE id=?''',
                   (name, brand, model, spec, price, stock, rating, category_id, description, image, product_id))
        db.commit()
        return redirect('/')
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    cats = db.execute('SELECT * FROM categories').fetchall()
    return render_template_string(EDIT_PRODUCT_HTML, product=product, cats=cats)

@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    db = get_db()
    db.execute('DELETE FROM products WHERE id = ?', (product_id,))
    db.commit()
    return redirect('/')

@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    db = get_db()
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        db.execute('UPDATE customers SET first_name=?, last_name=?, phone=?, email=? WHERE id=?',
                   (first_name, last_name, phone, email, customer_id))
        db.commit()
        return redirect('/customers')
    customer = db.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    return render_template_string(EDIT_CUSTOMER_HTML, customer=customer)

@app.route('/delete_customer/<int:customer_id>')
def delete_customer(customer_id):
    db = get_db()
    db.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
    db.commit()
    return redirect('/customers')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
