from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import locale
import datetime
from datetime import timedelta

# Atur format mata uang ke Indonesia (ID)
locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Ganti dengan secret key yang aman

# Konfigurasi database
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',  # Sesuaikan dengan user MySQL
    'password': '',  # Sesuaikan dengan password MySQL
    'database': 'pos_db'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Ambil total barang dari database
    cursor.execute("SELECT COUNT(*) AS total_items FROM items")
    total_items = cursor.fetchone()['total_items']
    
    # Ambil total transaksi dari database
    cursor.execute("SELECT COUNT(*) AS total_transactions FROM transactions")
    total_transactions = cursor.fetchone()['total_transactions']
    
    # Tentukan rentang tanggal (26 bulan lalu - 25 bulan ini)
    today = datetime.date.today()
    start_date = (today.replace(day=26) - datetime.timedelta(days=31)).strftime('%Y-%m-%d')  # 26 bulan lalu
    end_date = today.replace(day=25).strftime('%Y-%m-%d')  # 25 bulan ini
    
    # Ambil total pendapatan dari database dalam rentang waktu
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0) AS total_revenue 
        FROM transactions 
        WHERE created_at BETWEEN %s AND %s
    """, (start_date, end_date))
    
    total_revenue = cursor.fetchone()['total_revenue']
    
    cursor.close()
    conn.close()
    
    # Format total revenue ke mata uang Rupiah
    formatted_revenue = locale.currency(total_revenue, grouping=True, symbol=True)

    return render_template('index.html', 
                           total_items=total_items, 
                           total_transactions=total_transactions, 
                           total_revenue=formatted_revenue, 
                           start_date=start_date, 
                           end_date=end_date)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "username" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    username = session["username"]

    # Ambil data user
    cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        flash("User not found!", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_username = request.form.get("username")
        old_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Validasi password lama (tanpa hash, langsung dibandingkan)
        if old_password and old_password != user["password"]:
            flash("Old password is incorrect!", "error")  # Jika gagal
            return redirect(url_for("profile"))

        # Update username jika berubah
        if new_username and new_username != user["username"]:
            cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, user["id"]))
            session["username"] = new_username  # Update session

        # Update password jika diisi dan sesuai konfirmasi
        if new_password:
            if new_password != confirm_password:
                flash("New password and confirm password do not match!", "error")  # Jika password baru tidak sesuai
                return redirect(url_for("profile"))

            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, user["id"]))

        conn.commit()
        flash("Profile updated successfully!", "success")  # Jika berhasil
    cursor.close()
    conn.close()
    return render_template("profile.html", user=user)


@app.route('/barang')
def barang():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM items")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('barang.html', items=items)

@app.route('/transactions')
def transactions():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM transactions ORDER BY created_at DESC")
    transactions = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('transactions.html', transactions=transactions)

@app.route('/transactions/edit/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Ambil transaksi berdasarkan ID
    cursor.execute("SELECT * FROM transactions WHERE id = %s", (id,))
    transaction = cursor.fetchone()
    
    if not transaction:
        return redirect(url_for('transactions'))

    if request.method == 'POST':
        quantity = int(request.form['quantity'])
        total_price = quantity * transaction['price']  # Hitung total harga
        
        cursor.execute(
            "UPDATE transactions SET quantity = %s, total_price = %s WHERE id = %s",
            (quantity, total_price, id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('transactions'))

    cursor.close()
    conn.close()
    return render_template('edit_transaction.html', transaction=transaction)

@app.route('/transactions/delete/<int:id>')
def delete_transaction(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM transactions WHERE id = %s", (id,))
    conn.commit()
    
    cursor.close()
    conn.close()
    return redirect(url_for('transactions'))

@app.route('/reports')
def reports():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Ambil semua laporan dari database
    cursor.execute("SELECT * FROM reports ORDER BY end_date DESC")
    reports = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('reports.html', reports=reports)

import datetime
from datetime import timedelta

def generate_report():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Ambil laporan terakhir
    cursor.execute("SELECT * FROM reports ORDER BY end_date DESC LIMIT 1")
    last_report = cursor.fetchone()

    # Ambil tanggal transaksi terakhir
    cursor.execute("SELECT MAX(DATE(created_at)) AS last_transaction_date FROM transactions")
    last_transaction = cursor.fetchone()
    last_transaction_date = last_transaction['last_transaction_date']

    if last_transaction_date is None:
        cursor.close()
        conn.close()
        return

    # Konversi last_transaction_date ke date jika masih string
    if isinstance(last_transaction_date, str):
        last_transaction_date = datetime.datetime.strptime(last_transaction_date, "%Y-%m-%d").date()

    if last_report is None:
        # Jika belum ada laporan, gunakan transaksi terakhir sebagai start_date
        start_date = last_transaction_date.replace(day=26) - timedelta(days=30)
        end_date = last_transaction_date
    else:
        # Pastikan last_end_date dalam format date
        last_end_date = last_report['end_date']
        if isinstance(last_end_date, str):
            last_end_date = datetime.datetime.strptime(last_end_date, "%Y-%m-%d").date()

        if last_transaction_date > last_end_date:
            start_date = last_end_date + timedelta(days=1)
            end_date = last_transaction_date
        else:
            start_date = last_report['start_date']
            end_date = last_report['end_date']

    # Hitung total transaksi dan pendapatan
    cursor.execute("""
        SELECT COUNT(*) AS total_transactions, SUM(total_price) AS total_revenue 
        FROM transactions 
        WHERE DATE(created_at) BETWEEN %s AND %s
    """, (start_date, end_date))

    report_data = cursor.fetchone()
    total_transactions = report_data['total_transactions'] or 0
    total_revenue = report_data['total_revenue'] or 0.0

    if last_report and last_transaction_date <= last_end_date:
        cursor.execute("""
            UPDATE reports 
            SET total_transactions = %s, total_revenue = %s 
            WHERE end_date = %s
        """, (total_transactions, total_revenue, end_date.strftime('%Y-%m-%d')))
    else:
        cursor.execute("""
            INSERT INTO reports (start_date, end_date, total_transactions, total_revenue)
            VALUES (%s, %s, %s, %s)
        """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), total_transactions, total_revenue))

    conn.commit()
    cursor.close()
    conn.close()

# Jalankan generate_report() setiap kali aplikasi dimulai
generate_report()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Username atau password salah!')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if "username" not in session:
        return redirect(url_for("login"))  # Pastikan user login dulu

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Ambil kode terakhir dari database
    cursor.execute("SELECT code FROM items ORDER BY code DESC LIMIT 1")
    last_item = cursor.fetchone()
    
    if last_item and last_item['code'].startswith("ITEM"):
        last_number = int(last_item['code'][4:])  # Ambil angka setelah "ITEM"
        new_code = f"ITEM{last_number + 1:03d}"  # Format 'ITEMXXX' dengan leading zero
    else:
        new_code = "ITEM001"  # Jika belum ada barang, mulai dari ITEM001

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        stock = request.form['stock']
        username = session["username"]  # Ambil username dari sesi

        # Simpan ke tabel `items`
        cursor.execute("INSERT INTO items (code, name, price, stock) VALUES (%s, %s, %s, %s)", (new_code, name, price, stock))

        # Simpan ke tabel `jejaktambahbarang`
        cursor.execute("INSERT INTO jejaktambahbarang (item_code, item_name, price, stock, username) VALUES (%s, %s, %s, %s, %s)", (new_code, name, price, stock, username))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('index'))

    cursor.close()
    conn.close()
    return render_template('form.html', item=None, new_code=new_code)

@app.route('/edit/<string:code>', methods=['GET', 'POST'])
def edit_item(code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM items WHERE code = %s", (code,))
    item = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        stock = request.form['stock']
        cursor.execute("UPDATE items SET name=%s, price=%s, stock=%s WHERE code=%s", (name, price, stock, code))
        conn.commit()
        return redirect(url_for('index'))
    return render_template('form.html', item=item)

@app.route('/delete/<string:code>')
def delete_item(code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE code = %s", (code,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
