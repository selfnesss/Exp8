from pathlib import Path
import sqlite3
from flask import Flask, render_template_string, request, g
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
            cur.execute('''INSERT OR IGNORE INTO products(id,name,brand,model,spec,price,stock,rating,category_id,description)
                           VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                r['id'], r['name'], r['brand'], r.get('model',''), r.get('spec',''), float(r['price']), int(r['stock']), float(r['rating']), int(r['category_id']), r.get('description','')
            ))
    con.commit()
    con.close()

def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

app = Flask(__name__)

INDEX_HTML = '''
<!doctype html>
<title>Electronics Store — Прототип</title>
<h2>Products</h2>
<form method="get">
  Search: <input name="q" value="{{q}}"> 
  Category: <select name="cat"><option value="">All</option>{% for c in cats %}<option value="{{c.id}}" {% if cat and cat|int == c.id %}selected{% endif %}>{{c.name}}</option>{% endfor %}</select>
  Sort: <select name="sort"><option value="name">Name</option><option value="price">Price</option><option value="rating">Rating</option></select>
  <button>Apply</button>
</form>
<table border=1 cellpadding=6>
<tr><th>Name</th><th>Brand</th><th>Model/Spec</th><th>Price</th><th>Stock</th><th>Rating</th><th>Category</th></tr>
{% for p in products %}
<tr>
  <td>{{p.name}}</td>
  <td>{{p.brand}}</td>
  <td>{{p.model}} {{p.spec}}</td>
  <td>{{p.price}}</td>
  <td>{{p.stock}}</td>
  <td>{{p.rating}}</td>
  <td>{{p.category}}</td>
</tr>
{% endfor %}
</table>
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
