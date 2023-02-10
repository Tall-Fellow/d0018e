from flask import Flask
from flask_mysqldb import MySQL
from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import MySQLdb.cursors

# create and configure the app & database connection
app = Flask(__name__)

app.secret_key = 'dev'

app.config['MYSQL_HOST']     = '130.240.200.107'
app.config['MYSQL_DB']       = 'mydb'
app.config['MYSQL_USER']     = 'external'
app.config['MYSQL_PASSWORD'] = 'password'
mysql = MySQL(app)

def get_db_cursor():
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)

@app.route('/')
def index():
    cursor = get_db_cursor()
    cursor.execute("SELECT * FROM Product")
    g.products = cursor.fetchall()
    return render_template('index.html')

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None

    else:
        cursor = get_db_cursor()
        cursor.execute("SELECT * FROM User WHERE id = %s", (user_id,))
        g.user = cursor.fetchone()

@app.route('/register/', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        error = None
        if not email:
            error = 'Username is required'

        elif not password:
            error = 'Password is required'

        if error is None:
            try:
                password = generate_password_hash(password)

                # Add user to db
                cursor = get_db_cursor()
                cursor.execute('INSERT INTO User VALUES (NULL, "customer", %s, %s)', (email, password,))
                mysql.connection.commit()
                
                # Login user to their new account
                cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
                user = cursor.fetchone()
                session.clear()
                session['user_id'] = user['id']
                flash("Welcome to Göstas!")

                return redirect(url_for("index"))
                
            except cursor.IntegrityError:
                error = f"User {email} is already registered!"

        flash(error)

    return render_template('auth/register.html')

@app.route('/login/', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = get_db_cursor()
        cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()

        error = None
        if user is None:
            error = 'Incorrect username.'

        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()    
    return redirect(url_for('index'))

@app.route('/add_product', methods =('GET', 'POST'))
def addProduct():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        media = request.files
        t1 = media[0]
        t2 = media[1]
        categories = request.form['category']
        return redirect(url_for('index'))

    return render_template('retailer/add_product.html')
