# app.py (نسخه کامل و نهایی آماده برای پابلیش آنلاین)

# --- وارد کردن کتابخانه‌های لازم ---
import os
import psycopg2
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
import jdatetime
from datetime import datetime, time
from functools import wraps
import psycopg2.extras  # برای کار با دیکشنری‌ها

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


# --- << درب پشتی برای ساخت دیتابیس آنلاین (فقط یک بار استفاده شود) >> ---
@app.route('/create-db-one-time-secret-path')
def create_tables_online():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # دستورات ساخت جدول‌ها برای PostgreSQL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guides (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mentees (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, congress_code TEXT,
                journey_type TEXT, guide_id INTEGER,
                FOREIGN KEY (guide_id) REFERENCES guides(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY, mentee_id INTEGER, session_date TEXT NOT NULL,
                status TEXT NOT NULL, session_time TEXT,
                FOREIGN KEY (mentee_id) REFERENCES mentees(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guide_cds (
                id SERIAL PRIMARY KEY, guide_id INTEGER, record_date TEXT NOT NULL,
                cd_count INTEGER NOT NULL,
                FOREIGN KEY (guide_id) REFERENCES guides(id) ON DELETE CASCADE
            );
        ''')

        # وارد کردن کاربر ادمین
        hashed_admin_pass = generate_password_hash('adminpass')
        cursor.execute("""
            INSERT INTO guides (username, password, name, is_admin)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (username) DO NOTHING;
        """, ('admin', hashed_admin_pass, 'مدیر سیستم'))

        conn.commit()
        cursor.close()
        conn.close()
        return "جداول با موفقیت در دیتابیس آنلاین ساخته شدند! حالا این روت را از کد حذف و دوباره پابلیش کنید."
    except Exception as e:
        return f"خطایی رخ داد: {e}"


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
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM guides WHERE username = %s", (username,))
        user = cursor.fetchone()
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
    if 'guide_id' not in session or session.get('is_admin'):
        return redirect(url_for('login'))
    today_shamsi_date = jdatetime.date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    mentees_query = """
        SELECT m.id, m.name, m.congress_code, m.journey_type, a.id as attendance_id, a.status, a.session_time
        FROM mentees m LEFT JOIN attendance a ON m.id = a.mentee_id AND a.session_date = %s
        WHERE m.guide_id = %s
    """
    cursor.execute(mentees_query, (today_shamsi_date, session['guide_id']))
    mentees_data = cursor.fetchall()
    cursor.execute('SELECT * FROM guide_cds WHERE guide_id = %s ORDER BY record_date DESC', (session['guide_id'],))
    guide_cds_history = cursor.fetchall()
    cursor.execute('SELECT SUM(cd_count) as total FROM guide_cds WHERE guide_id = %s', (session['guide_id'],))
    total_cds_result = cursor.fetchone()
    total_guide_cds = total_cds_result['total'] if total_cds_result and total_cds_result['total'] is not None else 0
    cursor.close()
    conn.close()
    return render_template('dashboard.html', guide_name=session['guide_name'], mentees=mentees_data,
                           today_shamsi_date=today_shamsi_date, guide_cds_history=guide_cds_history,
                           total_guide_cds=total_guide_cds)


@app.route('/add_mentee', methods=['POST'])
def add_mentee():
    if 'guide_id' not in session: return redirect(url_for('login'))
    mentee_name = request.form['mentee_name']
    congress_code = request.form.get('congress_code', 'صادر نشده')
    journey_type = request.form.get('journey_type')
    guide_id = session['guide_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO mentees (name, congress_code, journey_type, guide_id) VALUES (%s, %s, %s, %s)',
                   (mentee_name, congress_code, journey_type, guide_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/record_attendance', methods=['POST'])
def record_attendance():
    if 'guide_id' not in session: return redirect(url_for('login'))
    mentee_id = request.form['mentee_id']
    session_date_str = request.form['session_date']
    status = request.form['status']
    session_time_str = request.form.get('session_time')
    try:
        gregorian_date = jdatetime.datetime.strptime(session_date_str, '%Y-%m-%d').togregorian()
        weekday = gregorian_date.weekday()
    except ValueError:
        return "فرمت تاریخ اشتباه است."
    if session_time_str and status == 'حاضر':
        try:
            session_time_obj = time.fromisoformat(session_time_str)
            if weekday == 3 and session_time_obj > time(14, 0):
                status = 'تاخیر'
            elif weekday == 5 and session_time_obj > time(17, 0):
                status = 'تاخیر'
        except ValueError:
            pass
    if weekday not in [3, 5]: return "ثبت حضور و غیاب فقط برای روزهای شنبه و پنجشنبه امکان‌پذیر است."
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO attendance (mentee_id, session_date, status, session_time) VALUES (%s, %s, %s, %s)',
                   (mentee_id, session_date_str, status, session_time_str))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/record_guide_cds', methods=['POST'])
def record_guide_cds():
    if 'guide_id' not in session: return redirect(url_for('login'))
    record_date = request.form['record_date']
    cd_count = request.form.get('cd_count', 0, type=int)
    guide_id = session['guide_id']
    if cd_count > 0:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO guide_cds (guide_id, record_date, cd_count) VALUES (%s, %s, %s)',
                       (guide_id, record_date, cd_count))
        conn.commit()
        cursor.close()
        conn.close()
    return redirect(url_for('dashboard'))


@app.route('/edit_attendance/<int:attendance_id>')
def edit_attendance(attendance_id):
    if 'guide_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM attendance WHERE id = %s', (attendance_id,))
    attendance_record = cursor.fetchone()
    cursor.close()
    conn.close()
    if not attendance_record: return "رکورد پیدا نشد!", 404
    return render_template('edit_attendance.html', attendance=attendance_record)


@app.route('/update_attendance/<int:attendance_id>', methods=['POST'])
def update_attendance(attendance_id):
    if 'guide_id' not in session: return redirect(url_for('login'))
    session_date_str = request.form['session_date']
    status = request.form['status']
    session_time_str = request.form.get('session_time')
    # منطق تاخیر اینجا هم لازم است
    try:
        gregorian_date = jdatetime.datetime.strptime(session_date_str, '%Y-%m-%d').togregorian()
        weekday = gregorian_date.weekday()
    except ValueError:
        return "فرمت تاریخ اشتباه است."
    if session_time_str and status == 'حاضر':
        try:
            session_time_obj = time.fromisoformat(session_time_str)
            if weekday == 3 and session_time_obj > time(14, 0):
                status = 'تاخیر'
            elif weekday == 5 and session_time_obj > time(17, 0):
                status = 'تاخیر'
        except ValueError:
            pass
    if weekday not in [3, 5]: return "ثبت حضور و غیاب فقط برای روزهای شنبه و پنجشنبه امکان‌پذیر است."
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE attendance SET session_date = %s, status = %s, session_time = %s WHERE id = %s',
                   (session_date_str, status, session_time_str, attendance_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/mentee/<int:mentee_id>')
def mentee_profile(mentee_id):
    if 'guide_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM mentees WHERE id = %s AND guide_id = %s', (mentee_id, session['guide_id']))
    mentee = cursor.fetchone()
    if not mentee:
        cursor.close()
        conn.close()
        return "دسترسی غیر مجاز", 403
    cursor.execute('SELECT * FROM attendance WHERE mentee_id = %s ORDER BY session_date DESC', (mentee_id,))
    attendance_history = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('mentee_profile.html', mentee=mentee, attendance_history=attendance_history)


# --- بخش روت‌های پنل ادمین ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT id, name FROM guides WHERE is_admin = FALSE ORDER BY name')
    guides = cursor.fetchall()
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
    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO guides (name, username, password, is_admin) VALUES (%s, %s, %s, FALSE)',
                       (name, username, hashed_password))
        conn.commit()
        flash(f"راهنمای جدید '{name}' با موفقیت ثبت شد.", "success")
    except psycopg2.IntegrityError:
        conn.rollback()
        flash("این نام کاربری قبلا استفاده شده است.", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/legion/<int:guide_id>')
@admin_required
def admin_legion_view(guide_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM guides WHERE id = %s', (guide_id,))
    guide = cursor.fetchone()
    cursor.execute('SELECT SUM(cd_count) as total FROM guide_cds WHERE guide_id = %s', (guide_id,))
    total_cds_result = cursor.fetchone()
    total_guide_cds = total_cds_result['total'] if total_cds_result and total_cds_result['total'] is not None else 0
    cursor.execute("SELECT journey_type, COUNT(id) as count FROM mentees WHERE guide_id = %s GROUP BY journey_type",
                   (guide_id,))
    journey_stats = cursor.fetchall()
    cursor.execute("""
        SELECT m.name, a.session_date, a.status 
        FROM attendance a JOIN mentees m ON a.mentee_id = m.id 
        WHERE m.guide_id = %s ORDER BY a.session_date DESC LIMIT 20
    """, (guide_id,))
    mentees_attendance = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_legion_view.html', guide=guide, total_guide_cds=total_guide_cds,
                           journey_stats=journey_stats, mentees_attendance=mentees_attendance)


# --- اجرای برنامه ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
