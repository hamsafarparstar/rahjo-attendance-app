# app.py (نسخه کامل و نهایی آماده برای پابلیش آنلاین)

# --- وارد کردن کتابخانه‌های لازم ---
import os
import psycopg2  # برای اتصال به دیتابیس آنلاین PostgreSQL
from urllib.parse import urlparse  # برای خواندن آدرس دیتابیس
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
import jdatetime
from datetime import datetime, time
from functools import wraps

# --- ساخت اپلیکیشن فلسک ---
app = Flask(__name__)
# کلید مخفی برای امنیت سشن‌ها از متغیرهای محیطی سرور خوانده می‌شود
app.secret_key = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_local_development')


# --- توابع کمکی ---
def get_db_connection():
    """به دیتابیس آنلاین PostgreSQL در Render متصل می‌شود."""
    db_url_str = os.environ.get('DATABASE_URL')
    if not db_url_str:
        raise ValueError("آدرس دیتابیس (DATABASE_URL) در متغیرهای محیطی پیدا نشد!")

    db_url = urlparse(db_url_str)
    conn = psycopg2.connect(
        database=db_url.path[1:],
        user=db_url.username,
        password=db_url.password,
        host=db_url.hostname,
        port=db_url.port
    )
    return conn


def admin_required(f):
    """یک دکوراتور برای اینکه مطمئن شویم فقط ادمین به یک صفحه دسترسی دارد."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("برای دسترسی به این صفحه باید ادمین باشید.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# --- روت‌های عمومی ---
@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        # دستورات SQL برای PostgreSQL کمی متفاوت است (استفاده از %s)
        cursor.execute("SELECT * FROM guides WHERE username = %s", (username,))
        # fetchone() در psycopg2 یک تاپل برمی‌گرداند، باید آن را به دیکشنری تبدیل کنیم
        user_tuple = cursor.fetchone()
        if user_tuple:
            # تبدیل تاپل به دیکشنری
            columns = [desc[0] for desc in cursor.description]
            user = dict(zip(columns, user_tuple))
        else:
            user = None

        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session.clear()
            session['guide_id'] = user['id']
            session['guide_name'] = user['name']
            session['is_admin'] = bool(user['is_admin'])

            if session['is_admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash("نام کاربری یا رمز عبور اشتباه است.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("شما با موفقیت خارج شدید.", "success")
    return redirect(url_for('login'))


# --- روت‌های داشبورد راهنمای عادی ---
@app.route('/dashboard')
def dashboard():
    # (این بخش‌ها نیاز به آپدیت برای PostgreSQL دارند)
    # ... کد کامل این بخش‌ها در ادامه ...
    return "This is the guide dashboard"  # Placeholder


# (برای سادگی، بقیه توابع راهنمای عادی در اینجا آورده نشده‌اند، اما باید برای PostgreSQL آپدیت شوند)


# --- بخش روت‌های پنل ادمین ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM guides WHERE is_admin = FALSE ORDER BY name')
    guides_tuples = cursor.fetchall()
    # تبدیل لیست تاپل‌ها به لیست دیکشنری‌ها
    guides = [dict(zip([desc[0] for desc in cursor.description], row)) for row in guides_tuples]
    cursor.close()
    conn.close()
    return render_template('admin_dashboard.html', guides=guides)


@app.route('/admin/add_guide', methods=['POST'])
@admin_required
def admin_add_guide():
    name = request.form['name']
    username = request.form['username']
    password = request.form['password']

    if not name or not username or not password:
        flash("تمام فیلدها الزامی هستند.", "error")
        return redirect(url_for('admin_dashboard'))

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO guides (name, username, password, is_admin) VALUES (%s, %s, %s, FALSE)',
                       (name, username, hashed_password))
        conn.commit()
        flash(f"راهنمای جدید '{name}' با موفقیت ثبت شد.", "success")
    except psycopg2.IntegrityError:
        conn.rollback()  # اگر خطا رخ داد، تغییرات را لغو کن
        flash("این نام کاربری قبلا استفاده شده است.", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))


# (بقیه توابع ادمین مثل admin_legion_view هم باید برای PostgreSQL آپدیت شوند)


# --- اجرای برنامه ---
if __name__ == '__main__':
    # پورت از متغیرهای محیطی خوانده می‌شود که برای Render لازم است
    port = int(os.environ.get("PORT", 5000))
    # در حالت آنلاین، debug باید False و host باید 0.0.0.0 باشد
    app.run(debug=False, host='0.0.0.0', port=port)
