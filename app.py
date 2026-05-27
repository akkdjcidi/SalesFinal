from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

ADMIN_PASSWORD = "1234"

# Автоматически определяем папку, где лежит app.py
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
    status = db.Column(db.String(20), default="Выдан на месте") 
    address = db.Column(db.String(200))
    card_number = db.Column(db.String(20))

    product = db.relationship('Product', backref='sales')
    client = db.relationship('Client', backref='sales')
    employee = db.relationship('Employee', backref='sales')

with app.app_context():
    db.create_all()

@app.route("/")
def index():
    db.session.commit() 
    db.session.expire_all()
    
    online_bot = Employee.query.filter_by(name="Онлайн-магазин").first()
    if not online_bot:
        online_bot = Employee(name="Онлайн-магазин", role="Робот", base_salary=0.0, commission=0.0)
        db.session.add(online_bot)
        db.session.commit()

    products = Product.query.all()
    employees = Employee.query.all()
    clients = Client.query.all()
    sales = Sale.query.order_by(Sale.date.desc()).all()
    
    total_products = sum(p.quantity for p in products) if products else 0
    total_clients = len(clients)
    revenue = sum(sale.amount for sale in sales if sale.amount) if sales else 0.0
    avg_check = (revenue / len(sales)) if (sales and len(sales) > 0) else 0.0
    
    low_stock_count = sum(1 for p in products if p.quantity <= 3)
    
    current_time = datetime.now().strftime('%H:%M')
    current_date = datetime.now().strftime('%d.%m.%Y')
    
    product_sales_map = {}
    for sale in sales:
        if sale.product:
            product_sales_map[sale.product.title] = product_sales_map.get(sale.product.title, 0) + 1
            
    top_products = sorted(product_sales_map.items(), key=lambda x: x[1], reverse=True)[:3]
    
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        chart_labels.append(day.strftime('%d.%m'))
        day_revenue = sum(sale.amount for sale in sales if sale.date.date() == day and sale.amount)
        chart_data.append(day_revenue)

    return render_template(
        "dashboard.html", 
        products=products, all_products=products,
        employees=employees, all_employees=employees,
        clients=clients, all_clients=clients,
        sales=sales, revenue=revenue, avg_check=avg_check,
        total_clients=total_clients, total_products=total_products,
        top_products=top_products, chart_labels=chart_labels, chart_data=chart_data,
        low_stock_count=low_stock_count,
        current_time=current_time, current_date=current_date
    )

@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    db.session.commit()
    db.session.expire_all()
    if request.method == "POST":
        title = request.form.get("title")
        price = float(request.form.get("price") or 0)
        quantity = int(request.form.get("quantity") or 0)
        image_url = request.form.get("image_url")
        if title:
            new_product = Product(title=title, price=price, quantity=quantity, image_url=image_url)
            db.session.add(new_product)
            db.session.commit()
        return redirect(url_for("inventory"))
    return render_template("inventory.html", products=Product.query.all(), employees=Employee.query.all(), clients=Client.query.all())

@app.route("/edit_product/<int:product_id>", methods=["POST"])
def edit_product(product_id):
    password = request.form.get("password")
    if password != ADMIN_PASSWORD:
        return "<h2 style='color:red;'>Ошибка: Неверный пароль!</h2><a href='/inventory'>Вернуться на склад</a>", 403
    p = Product.query.get(product_id)
    if p:
        p.title = request.form.get("title", p.title)
        p.price = float(request.form.get("price", p.price))
        p.quantity = int(request.form.get("quantity", p.quantity))
        db.session.commit()
    return redirect(url_for("inventory"))

@app.route("/clients", methods=["GET", "POST"])
def clients_page():
    db.session.commit()
    db.session.expire_all()
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        if name:
            new_client = Client(name=name, phone=phone)
            db.session.add(new_client)
            db.session.commit()
        return redirect(url_for("clients_page"))
    return render_template("clients.html", clients=Client.query.all(), all_clients=Client.query.all(), sales=Sale.query.all())

@app.route("/staff", methods=["GET", "POST"])
def staff_page():
    db.session.commit()
    db.session.expire_all()
    
    if request.method == "POST":
        name = request.form.get("name")
        role = request.form.get("role")
        base_salary = float(request.form.get("base_salary") or 0.0)
        commission = float(request.form.get("commission") or 0.0)
        if name:
            new_emp = Employee(name=name, role=role, base_salary=base_salary, commission=commission)
            db.session.add(new_emp)
            db.session.commit()
        return redirect(url_for("staff_page"))
        
    now = datetime.now()
    req_month = request.args.get('month', default=now.month, type=int)
    req_year = request.args.get('year', default=now.year, type=int)
    all_sales = Sale.query.all()
    current_month_sales = [s for s in all_sales if s.date and s.date.year == req_year and s.date.month == req_month]
    months = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    current_month_name = f"{months[req_month]} {req_year}"

    history_months = []
    for i in range(6):
        m = now.month - i
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        history_months.append({"month": m, "year": y, "label": f"{months[m]} {y}"})

    return render_template(
        "staff.html", 
        employees=Employee.query.all(), 
        all_employees=Employee.query.all(), 
        sales=current_month_sales, 
        current_month_name=current_month_name,
        history_months=history_months,
        req_month=req_month,
        req_year=req_year
    )

@app.route("/orders")
def orders_page():
    db.session.commit()
    db.session.expire_all()
    online_orders = Sale.query.filter(Sale.status != "Выдан на месте").order_by(Sale.date.desc()).all()
    return render_template("orders.html", sales=online_orders)

@app.route("/update_order/<int:sale_id>/<status>")
def update_order(sale_id, status):
    sale = Sale.query.get(sale_id)
    if sale:
        sale.status = status
        db.session.commit()
    return redirect(url_for("orders_page"))

@app.route("/add_sale", methods=["POST"])
def add_sale():
    product_id = int(request.form.get("product_id") or 0)
    employee_id = int(request.form.get("employee_id") or 0)
    client_id = int(request.form.get("client_id") or 0)
    p = Product.query.get(product_id)
    if p and p.quantity > 0:
        p.quantity -= 1
        c = Client.query.get(client_id)
        if c:
            c.total_spent += p.price
        new_sale = Sale(
            product_id=product_id, employee_id=employee_id if employee_id > 0 else None, 
            client_id=client_id if client_id > 0 else None, amount=p.price, status="Выдан на месте"
        )
        db.session.add(new_sale)
        db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
