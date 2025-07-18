# init_db.py (نسخه کامل و نهایی آماده برای پابلیش آنلاین)

import os
import psycopg2
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash


def get_db_connection():
    """به دیتابیس آنلاین PostgreSQL در Render متصل می‌شود."""
    db_url_str = os.environ.get('DATABASE_URL')
    if not db_url_str:
        raise ValueError("آدرس دیتابیس (DATABASE_URL) در متغیرهای محیطی پیدا نشد!")

    db_url = urlparse(db_url_str)
    try:
        conn = psycopg2.connect(
            database=db_url.path[1:],
            user=db_url.username,
            password=db_url.password,
            host=db_url.hostname,
            port=db_url.port
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"خطا در اتصال به دیتابیس: {e}")
        raise


print("در حال اتصال به دیتابیس...")
conn = get_db_connection()
cursor = conn.cursor()
print("اتصال موفق بود. در حال ساخت جداول...")

# دستورات ساخت جدول‌ها برای PostgreSQL
# از SERIAL PRIMARY KEY برای ساخت ID خودکار استفاده می‌شود
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
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        congress_code TEXT,
        journey_type TEXT,
        guide_id INTEGER,
        FOREIGN KEY (guide_id) REFERENCES guides(id) ON DELETE CASCADE
    );
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        mentee_id INTEGER,
        session_date TEXT NOT NULL,
        status TEXT NOT NULL,
        session_time TEXT,
        FOREIGN KEY (mentee_id) REFERENCES mentees(id) ON DELETE CASCADE
    );
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS guide_cds (
        id SERIAL PRIMARY KEY,
        guide_id INTEGER,
        record_date TEXT NOT NULL,
        cd_count INTEGER NOT NULL,
        FOREIGN KEY (guide_id) REFERENCES guides(id) ON DELETE CASCADE
    );
''')

print("جداول با موفقیت ساخته یا تایید شدند.")

# --- وارد کردن داده‌های تستی ---
# از ON CONFLICT (username) DO NOTHING برای جلوگیری از خطای تکراری استفاده می‌کنیم
try:
    # ساخت کاربر ادمین
    hashed_admin_pass = generate_password_hash('adminpass')
    cursor.execute("""
        INSERT INTO guides (username, password, name, is_admin)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (username) DO NOTHING;
    """, ('admin', hashed_admin_pass, 'مدیر سیستم'))

    # ساخت کاربران عادی
    hashed_password_ali = generate_password_hash('1234')
    cursor.execute("""
        INSERT INTO guides (username, password, name, is_admin)
        VALUES (%s, %s, %s, FALSE)
        ON CONFLICT (username) DO NOTHING;
    """, ('ali', hashed_password_ali, 'علی رضایی'))

    hashed_password_reza = generate_password_hash('abcd')
    cursor.execute("""
        INSERT INTO guides (username, password, name, is_admin)
        VALUES (%s, %s, %s, FALSE)
        ON CONFLICT (username) DO NOTHING;
    """, ('reza', hashed_password_reza, 'رضا محمدی'))

    print("کاربران تستی با موفقیت وارد شدند.")

    # (در نسخه آنلاین معمولا داده‌های تستی رهجو را وارد نمی‌کنیم، اما برای تست اولیه می‌توان اضافه کرد)

    conn.commit()
except Exception as e:
    print(f"خطا در وارد کردن داده‌ها: {e}")
    conn.rollback()  # اگر خطایی رخ داد، تغییرات را لغو کن
finally:
    cursor.close()
    conn.close()

print("اسکریپت init_db با موفقیت اجرا شد.")
