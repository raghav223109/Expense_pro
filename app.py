
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func
import pandas as pd
from io import BytesIO

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'expense-tracker-secret-key'

db = SQLAlchemy(app)

CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Rent', 'Other']
CURRENCIES = ['INR', 'USD', 'EUR']

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    currency = db.Column(db.String(10), default='INR')
    date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class SavingsGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    goal_amount = db.Column(db.Float, nullable=False)
    saved_amount = db.Column(db.Float, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

with app.app_context():
    db.create_all()

def is_logged_in():
    return 'user_id' in session

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))

    expenses = Expense.query.filter_by(user_id=session['user_id']).all()
    goals = SavingsGoal.query.filter_by(user_id=session['user_id']).all()

    total = round(sum(e.amount for e in expenses), 2)

    category_data = db.session.query(
        Expense.category,
        func.sum(Expense.amount)
    ).filter_by(user_id=session['user_id']).group_by(Expense.category).all()

    cat_labels = [x[0] for x in category_data]
    cat_values = [float(x[1]) for x in category_data]

    return render_template(
        'index.html',
        expenses=expenses,
        total=total,
        categories=CATEGORIES,
        currencies=CURRENCIES,
        goals=goals,
        cat_labels=cat_labels,
        cat_values=cat_values
    )

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        user = User(
            username=username,
            email=email,
            password=password
        )

        db.session.add(user)
        db.session.commit()

        flash('Account created successfully!', 'success')

        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username

            return redirect(url_for('index'))

        flash('Invalid credentials', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add', methods=['POST'])
def add():
    if not is_logged_in():
        return redirect(url_for('login'))

    expense = Expense(
        description=request.form['description'],
        amount=float(request.form['amount']),
        category=request.form['category'],
        currency=request.form['currency'],
        date=datetime.strptime(request.form['date'], '%Y-%m-%d'),
        user_id=session['user_id']
    )

    db.session.add(expense)
    db.session.commit()

    flash('Expense added successfully!', 'success')

    return redirect(url_for('index'))

@app.route('/add_goal', methods=['POST'])
def add_goal():
    goal = SavingsGoal(
        title=request.form['title'],
        goal_amount=float(request.form['goal_amount']),
        saved_amount=float(request.form.get('saved_amount', 0)),
        user_id=session['user_id']
    )

    db.session.add(goal)
    db.session.commit()

    flash('Goal added!', 'success')

    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    users = User.query.count()
    transactions = Expense.query.count()
    goals = SavingsGoal.query.count()

    active_users = db.session.query(
        User.username,
        func.count(Expense.id)
    ).join(
        Expense,
        Expense.user_id == User.id
    ).group_by(User.username).all()

    return render_template(
        'admin.html',
        users=users,
        transactions=transactions,
        goals=goals,
        active_users=active_users
    )

@app.route('/export/csv')
def export_csv():
    expenses = Expense.query.filter_by(user_id=session['user_id']).all()

    data = []

    for e in expenses:
        data.append({
            'Description': e.description,
            'Amount': e.amount,
            'Category': e.category,
            'Currency': e.currency
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name='expenses.csv'
    )

if __name__ == '__main__':
    app.run(debug=True)
