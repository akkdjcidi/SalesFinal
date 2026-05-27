from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# Автоматически определяем папку, где лежит shop_app.py
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Универсальные пути к папкам
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Гарантируем создание папки instance
if not os.path.exists(INSTANCE_DIR):
    os.makedirs(INSTANCE_DIR)

# --- УМНОЕ ПОДКЛЮЧЕНИЕ БАЗЫ ДАННЫХ (Облако / Ноутбук) ---
db_url = os.environ.get('DATABASE_URL')
if db_url:
    # SQLAlchemy требует приставку postgresql://
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace("postgres://", "postgresql://", 1)
else:
    db_path = os.path.join(INSTANCE_DIR, "sales_system.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(500))

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    total_spent = db.Column(db.Float, default=0.0)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))
    base_salary = db.Column(db.Float, default=0.0)
    commission = db.Column(db.Float, default=0.0)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    amount = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Ожидает")
    address = db.Column(db.String(200))
    card_number = db.Column(db.String(20))

with app.app_context():
    db.create_all()

@app.route("/")
def shop_index():
    db.session.commit()
    db.session.expire_all()
    all_products = Product.query.all()
    return render_template("index.html", products=all_products)

@app.route("/buy/<int:product_id>", methods=["POST"])
def buy_item(product_id):
    db.session.commit()
    db.session.expire_all()
    
    p = Product.query.get(product_id)
    if not p or p.quantity <= 0:
        return "Товара нет в наличии на складе!", 400

    client_name = request.form.get('client_name') or "Покупатель с сайта"
    client_phone = request.form.get('client_phone') or "-"
    address = request.form.get('address') or "Самовывоз"
    card_number = request.form.get('card_number') or "Наличные"

    c = Client.query.filter_by(phone=client_phone).first()
    if not c:
        c = Client(name=client_name, phone=client_phone, total_spent=0.0)
        db.session.add(c)
        db.session.flush()

    online_bot = Employee.query.filter_by(name="Онлайн-магазин").first()
    if not online_bot:
        online_bot = Employee(name="Онлайн-магазин", role="Робот")
        db.session.add(online_bot)
        db.session.flush()

    p.quantity -= 1
    c.total_spent += p.price
    
    new_sale = Sale(
        product_id=p.id,
        employee_id=online_bot.id,
        client_id=c.id,
        amount=p.price,
        status="Ожидает",
        address=address,
        card_number=card_number
    )
    
    db.session.add(new_sale)
    db.session.commit()
    
    try:
        return render_template("success.html", product=p)
    except Exception:
        return f"<h3>Заказ успешно оформлен!</h3><p>Товар {p.title} ожидает отправки по адресу: {address}</p><a href='/'>Назад в магазин</a>"

if __name__ == "__main__":
    app.run(debug=True, port=5001)
