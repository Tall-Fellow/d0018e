# TODO: Solve user_id = None crashing site

from flask import Flask
from flask_mysqldb import MySQL
from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import MySQLdb.cursors
import os

app = Flask(__name__)

app.secret_key = 'dev'

app.config['MYSQL_HOST']     = '130.240.200.107'
app.config['MYSQL_DB']       = 'mydb'
app.config['MYSQL_USER']     = 'external'
app.config['MYSQL_PASSWORD'] = 'password'
mysql = MySQL(app)

def db_query(query: str, data: tuple = None, commit: bool = False):
    """
        Executes query using a prepared statement with data. 
        Call function like: db_query('SELECT Foo FROM %s WHERE Bar = %s', (item1, item2)).
        If there's only one item in data you must include a final comma: (singleItem,). 
        To commit to database, set commit = True.
    """
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(query, data)
        if commit: mysql.connection.commit()
        return cursor

    except Exception as e:
        print(f"Unable to execute query: '{query}' with data '{data}'.\nError: {e}")
        raise

def create_order(userId: int):
    """
        Creates new order for userId and returns it
    """
    query = db_query('INSERT INTO `Order` (userId) VALUES (%s)', (userId,), commit = True)
    query = db_query('SELECT LAST_INSERT_ID()')
    order_id = query.fetchone()['LAST_INSERT_ID()']
    query = db_query('SELECT * FROM `Order` WHERE id = %s', (order_id,))

    return query.fetchone()

def update_order_price(order_id: int):
    query = db_query('SELECT price, numOrdered FROM CartItem WHERE orderId = %s', (order_id,))
    order_rows = query.fetchall()
    order_price = 0

    try:
        for row in order_rows:
            order_price += (row["price"] * row["numOrdered"])

        query = db_query('UPDATE `Order` SET totalPrice = %s WHERE id = %s', (order_price, order_id), commit = True)

    except:
        flash("Couldn't update order price")

def update_order(order_id: int, product_id: int, qty: int, price: float = None):
    # Fetch current product price if no price is given
    if price is None:
        query = db_query('SELECT price FROM Product WHERE id = %s', (product_id,))
        price = query.fetchone()["price"]

    # Search for matches against primary keys
    data = (order_id, product_id, price)
    query = db_query('SELECT numOrdered FROM CartItem WHERE orderId = %s AND productId = %s AND price = %s', data)
    existing = query.fetchone()

    # If order row for product with current price doesn't exist create new, else update/remove row
    if existing is None:
        if qty <= 0:
            flash("Can't add less than 1 to order!")
            return

        try:
            data = (order_id, product_id, qty, price)
            db_query('INSERT INTO CartItem VALUES (%s, %s, %s, %s)', data, commit = True)

        except:
            flash("Order row creation failed")
            return

    else:
        qty += existing["numOrdered"]
        if qty > 0:
            data = (qty, order_id, product_id, price)
            queryStr = 'UPDATE CartItem SET numOrdered = %s WHERE orderId = %s AND productId = %s AND price = %s'
        
        else:
            data = (order_id, product_id, price)
            queryStr = 'DELETE FROM CartItem WHERE orderId = %s AND productId = %s AND price = %s'

        try:
            query = db_query(queryStr, data, commit = True)

        except:
            flash("Unable to modify order rows")

    update_order_price(order_id)

def get_media(product_id):
    mediaDir = os.listdir(os.path.join(app.root_path, "static", "media"))
    urls = []
    
    for item in mediaDir:
        if int(item.split("_", 1)[0]) == product_id:
            urls.append(item)

    return urls

def get_products(filter: str = None):
    if filter is None:
        data = None
        queryString = "SELECT * FROM Product WHERE active = 1"
    
    else:
        data = ("%" + filter + "%", "%" + filter + "%")
        queryString = 'SELECT * FROM Product WHERE active = 1 AND (name LIKE %s OR category LIKE %s)'

    query = db_query(queryString, data)
    products = query.fetchall()

    for product in products:
        product['media'] = get_media(product['id'])

    return products

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None

    else:
        # Load user data
        query = db_query('SELECT * FROM User WHERE id = %s', (user_id,))
        g.user = query.fetchone()
    
        if g.user['active'] == 0:
            session.clear()
            flash("Your account is not active, contact an admin for assistance")
            return redirect(url_for('index'))

        # Load cart quantity info
        try:
            query = db_query('SELECT id FROM `Order` WHERE userId = %s AND isFinished = 0', (user_id,))
            order_id = query.fetchone()['id']
            query = db_query('SELECT COUNT(orderId) FROM CartItem WHERE orderId = %s', (order_id,))
            g.user['cartQty'] = query.fetchone()['COUNT(orderId)']
        
        except:
            g.user['cartQty'] = 0

@app.get('/')
def index():
    products = get_products()
    return render_template('index.html', products = products)

@app.post('/')
def search():
    search_txt = request.form['search_txt']
    products = get_products(search_txt)
    return render_template('index.html', products = products)

@app.route('/register/', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        zipcode = request.form['zip']
        phone = request.form['phone']
        firstname = request.form['firstname']
        lastname = request.form['lastname']


        error = None
        if not email:
            error = 'Username is required'

        elif not password:
            error = 'Password is required'

        if error is None:
            password = generate_password_hash(password)

            try:
                # Add user to db
                query = db_query('INSERT INTO User VALUES (NULL, "Customer", %s, %s, 1, %s, %s, %s, %s, %s)', (email, password, firstname, lastname, address, zipcode, phone), commit = True)
            
                # Login user to their new account
                query = db_query('SELECT id FROM User WHERE email = %s', (email,))
                user = query.fetchone()
                session.clear()
                session['user_id'] = user['id']
                flash("Welcome to Göstas!")

                return redirect(url_for("index"))
            
            except:
                error = f"User {email} is already registered!"

        flash(error)

    return render_template('auth/register.html')

@app.route('/login/', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Look for existing accounts
        query = db_query('SELECT id, password FROM User WHERE email = %s', (email,))
        user = query.fetchone()

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

@app.get('/logout/')
def logout():
    session.clear()    
    return redirect(url_for('index'))

@app.route('/users/', methods=('GET', 'POST'))
def administer_users():
    if g.user['role'] != 'Administrator':
        return redirect(url_for('index'))

    if request.method == 'POST':
        u_id = request.form['id']
        email = request.form['email']
        role = request.form['role']
        active = request.form['active']

        try:
            data = (email, role,  active, u_id)
            query = db_query('UPDATE User SET email = %s, role = %s, active = %s WHERE id = %s', data, commit = True)

        except:
            flash("Failed to update user")
    
    query = db_query('SELECT id, role, email, active FROM User')
    users = query.fetchall()

    return render_template('admin/users.html', users = users)

@app.route('/add_product/', methods=('GET', 'POST'))
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        categories = request.form['category']
        active = request.form['active']
        media = request.files.getlist('media')
        details = request.form['details']

        # Permission check
        if g.user['role'] != "Retailer":
            flash("Not a retailer")
            return render_template('retailer/add_product.html')

        # Create product
        try:
            data = (name, price, g.user['id'], categories, active, details)
            query = db_query('INSERT INTO Product VALUES (NULL, %s, %s, %s, %s, %s, %s)', data, commit = True)
        
        except:
            flash("Failed to create product")
            return render_template('retailer/add_product.html')

        # Upload media & connect to product
        try:
            query = db_query('SELECT LAST_INSERT_ID()')
            product_id = query.fetchone()['LAST_INSERT_ID()']

            for i in range(len(media)):
                filetype = media[i].content_type[media[i].content_type.rindex("/")+1:]
                filename = f"{product_id}_{i}.{filetype}"
                media[i].save(os.path.join(app.root_path, "static", "media", filename))
        
        except Exception as e:
            print(e)
            flash("Failed to upload one or more media objects")

        flash("Successfully added product!")
        return redirect(url_for('index'))

    return render_template('retailer/add_product.html')

@app.get('/manage_products/')
def manage_products():
    # Permission check
    if g.user['role'] != "Retailer":
        flash("No retailer account was found")
        return redirect(request.referrer)

    query = db_query('SELECT * FROM Product WHERE retailerId = %s', (g.user['id'],))
    products = query.fetchall()

    for product in products:
        product['media'] = get_media(product['id'])

    return render_template('retailer/manage_products.html', products=products)

@app.post('/update_product/')
def update_product():
    product_id = request.form['id']
    name = request.form['name']
    price = request.form['price']
    category = request.form['category']
    details = request.form['details']
    active = request.form['active']
    #media = request.files.getlist('media') # Implement image upload/removal for future versions

    try:
        data = (name, price, category, details, active, product_id)
        db_query('UPDATE Product SET name=%s, price=%s, category=%s, details=%s, active=%s WHERE id=%s', data, commit = True)

    except:
        flash("Failed to update product")

    return redirect(request.referrer)

@app.route('/details/<product_id>', methods=('GET', 'POST'))
def view_details(product_id):
    if request.method == 'POST':
        user_id = session.get('user_id')
        if user_id is None:
            flash("You need to be logged in to review products")
            return redirect(request.referrer)
        
        # Check if user has ordered product
        queryString = (
            "SELECT CartItem.orderId "
            "FROM CartItem "
            "INNER JOIN `Order` ON CartItem.orderId = `Order`.id "
            "WHERE CartItem.productId = %s AND `Order`.isFinished = 1"
        )
        query = db_query(queryString, (product_id,))
        result = query.fetchone()

        if result is None:
            flash("You need to buy the product before placing a review")
            return redirect(request.referrer)

        rating = request.form['rating']
        review = request.form['review']
        try:
            data = (user_id, product_id, rating, review)
            query = db_query('INSERT INTO Review VALUES (%s, %s, %s, %s)', data, commit = True) 

        except:
            flash("You've already left a review and can't place a new one")

    # Get product details
    query = db_query('SELECT * FROM Product WHERE id = %s', (product_id,))
    product = query.fetchone()

    if product is None:
        flash("Couldn't find product")
        return redirect(url_for('index'))

    if product['active'] == 0:
        flash("Product can't be viewed since it's inactive")
        return redirect(url_for('index'))
    
    product['media'] = get_media(product['id'])
    queryString = (
        "SELECT User.email, Review.rating, Review.review "
        "FROM Review "
        "INNER JOIN User ON Review.userId = User.id "
        "WHERE Review.productId = %s"
    )
    query = db_query(queryString, (product['id'],))
    product['reviews'] = query.fetchall()

    return render_template('product/details.html', product = product)

@app.get('/orders/')
def order_history():
    user_id = session.get('user_id')
    query = db_query('SELECT id, totalPrice FROM `Order` WHERE userId = %s AND isFinished = 1', (user_id,))
    orders = query.fetchall()

    # Fetch order rows
    for order in orders:
        queryString = (
            "SELECT "
                "CartItem.price, "
                "CartItem.numOrdered, "
                "Product.name, "
                "Product.id "
            "FROM CartItem "
                "INNER JOIN "
                "Product ON CartItem.productId = Product.id "
            "WHERE "
                "CartItem.orderId = %s"
        )
        query = db_query(queryString, (order['id'],))
        order['rows'] = query.fetchall()

    return render_template('order/history.html', orders = orders)

@app.route('/cart/', methods=('GET', 'POST'))
def view_cart():
    user_id = session.get('user_id')
    query = db_query('SELECT id, totalPrice FROM `Order` WHERE userId = %s AND isFinished = 0', (user_id,))
    order_info = query.fetchone()

    if order_info is None:
        cart = {
            'id': "",
            'totalPrice': 0,
            'rows': ""
        }
    
    else:
        queryString = (
            "SELECT Product.id, Product.name, Product.active, CartItem.price, CartItem.numOrdered "
            "FROM CartItem "
            "INNER JOIN Product ON CartItem.productId = Product.id "
            "WHERE CartItem.orderId = %s"
        )
        query = db_query(queryString, (order_info["id"],))
        order_rows = query.fetchall()

        active_rows = []
        for row in order_rows:
            if row['active'] == 0:
                # Remove from order rows and fetch updated order price
                update_order(order_info['id'], row['id'], row['numOrdered'] * -1, row['price'])
                query = db_query('SELECT id, totalPrice FROM `Order` WHERE id=%s', (order_info["id"],))
                order_info = query.fetchone()
                flash(f'Product {row["name"]} has been removed from cart because retailer has deactived the product')

            else:
                active_rows.append(row)


        cart = {
            'id': order_info['id'],
            'totalPrice': order_info['totalPrice'],
            'rows': active_rows
        }

    return render_template('cart/view_cart.html', cart = cart)

@app.post('/add_to_cart/')
def add_to_cart():
    user_id = session.get('user_id')
    product_id = request.form['id']
    qty = int(request.form['qty'])
    price = request.form['price']

    if user_id is None:
        return redirect(url_for('login'))

    elif product_id is None or qty < 1:
        return redirect(request.referrer)

    query = db_query('SELECT id FROM `Order` WHERE userId = %s AND isFinished = 0', (user_id,))
    curr_order = query.fetchone()

    if curr_order is None:
        curr_order = create_order(user_id)
    
    update_order(curr_order["id"], product_id, qty, price)
    flash("Added to cart!")

    return redirect(request.referrer)

@app.post('/remove_from_cart/')
def remove_from_cart():
    user_id = session.get('user_id')
    product_id = request.form['id']
    qty = int(request.form['qty']) * -1
    price = request.form['price']

    if user_id is None or product_id is None or qty > -1:
        return redirect(request.referrer)

    query = db_query('SELECT id FROM `Order` WHERE userId = %s AND isFinished = 0', (user_id,))
    curr_order = query.fetchone()

    if curr_order is None:
        flash("Nothing to remove")
        return redirect(request.refferer)

    update_order(curr_order["id"], product_id, qty, price)
    flash("Item successfully removed!")

    return redirect(url_for('view_cart'))

@app.post('/checkout/')
def checkout():
    user_id = session.get('user_id')
    query = db_query('SELECT id FROM `Order` WHERE userId = %s AND isFinished = 0', (user_id,))
    curr_order = query.fetchone()
    if curr_order is None:
        flash("Nothing in cart")
        return redirect(url_for('index'))

    try:
        query = db_query('UPDATE `Order` SET isFinished = 1 WHERE id = %s', (curr_order["id"],), commit = True)
    
    except:
        flash("Something went wrong when updating order status")

    return redirect(url_for('index'))
