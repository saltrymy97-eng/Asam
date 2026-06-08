# migrate_to_postgres.py – سكربت ترحيل حوكمة ERP من SQLite إلى PostgreSQL
import sqlite3
import pg8000.native

# ===================== إعدادات الاتصال =====================
SQLITE_DB = "erp.db"

PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "admin",
    "password": "123456",
    "database": "hokoma_erp"
}

# ===================== دوال المساعدة =====================
def get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_pg_conn():
    conn = pg8000.native.Connection(**PG_CONFIG)
    return conn

def sqlite_type_to_pg(col_type):
    """تحويل نوع العمود من SQLite إلى PostgreSQL"""
    col_type = col_type.upper()
    if "INT" in col_type:
        return "INTEGER"
    elif "CHAR" in col_type or "TEXT" in col_type or "CLOB" in col_type:
        return "TEXT"
    elif "BLOB" in col_type:
        return "BYTEA"
    elif "REAL" in col_type or "FLOAT" in col_type or "DOUB" in col_type:
        return "REAL"
    elif "BOOL" in col_type:
        return "BOOLEAN"
    elif "TIMESTAMP" in col_type or "DATETIME" in col_type:
        return "TIMESTAMP"
    else:
        return "TEXT"

def create_tables_in_postgres(pg_conn, sqlite_conn):
    """إنشاء جميع الجداول في PostgreSQL بنفس هيكل SQLite"""
    cur = sqlite_conn.cursor()
    
    # جلب أسماء جميع الجداول
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row["name"] for row in cur.fetchall()]
    
    pg_cursor = pg_conn.cursor()
    
    for table in tables:
        try:
            # حذف الجدول إذا كان موجوداً
            pg_cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
            
            # جلب معلومات الأعمدة
            cur.execute(f"PRAGMA table_info('{table}')")
            columns = cur.fetchall()
            
            if not columns:
                continue
            
            # بناء أمر CREATE TABLE
            col_defs = []
            primary_keys = []
            
            for col in columns:
                col_name = col["name"]
                col_type = sqlite_type_to_pg(col["type"])
                is_pk = col["pk"] > 0
                not_null = col["notnull"] > 0
                
                # تحويل SERIAL PRIMARY KEY
                if is_pk and "INT" in col_type.upper():
                    col_defs.append(f'"{col_name}" SERIAL PRIMARY KEY')
                else:
                    col_def_parts = [f'"{col_name}" {col_type}']
                    if not_null:
                        col_def_parts.append("NOT NULL")
                    # تعيين القيم الافتراضية
                    if col["dflt_value"] is not None:
                        dflt = col["dflt_value"]
                        if dflt.upper() == "CURRENT_TIMESTAMP":
                            col_def_parts.append("DEFAULT CURRENT_TIMESTAMP")
                        elif dflt.startswith("'") and dflt.endswith("'"):
                            col_def_parts.append(f"DEFAULT {dflt}")
                        else:
                            col_def_parts.append(f"DEFAULT {dflt}")
                    col_defs.append(" ".join(col_def_parts))
                
                # جمع المفاتيح الأساسية غير المسلسلة
                if is_pk and "INT" not in col_type.upper():
                    primary_keys.append(col_name)
            
            # إضافة PRIMARY KEY مركب إذا لزم
            if primary_keys and not any("PRIMARY KEY" in c for c in col_defs):
                col_defs.append(f'PRIMARY KEY ("{"\", \"".join(primary_keys)}")')
            
            create_sql = f'CREATE TABLE "{table}" (\n  ' + ',\n  '.join(col_defs) + '\n)'
            pg_cursor.execute(create_sql)
            print(f"✅ تم إنشاء جدول: {table}")
            
        except Exception as e:
            print(f"❌ فشل إنشاء جدول {table}: {e}")
    
    pg_conn.commit()
    pg_cursor.close()

def migrate_data(pg_conn, sqlite_conn):
    """نسخ البيانات من SQLite إلى PostgreSQL"""
    cur = sqlite_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row["name"] for row in cur.fetchall()]
    
    pg_cursor = pg_conn.cursor()
    
    for table in tables:
        try:
            # جلب البيانات
            cur.execute(f'SELECT * FROM "{table}"')
            rows = cur.fetchall()
            
            if not rows:
                print(f"⚠️ {table}: لا توجد بيانات")
                continue
            
            # جلب أسماء الأعمدة
            columns = [desc[0] for desc in cur.description]
            
            # إعداد INSERT
            placeholders = ','.join([':%s' % i for i in range(len(columns))])
            columns_str = '","'.join(columns)
            insert_sql = f'INSERT INTO "{table}" ("{columns_str}") VALUES ({placeholders})'
            
            # إدخال البيانات
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                for row in batch:
                    values = {}
                    for j, col in enumerate(columns):
                        val = row[col]
                        # تحويل None إلى NULL صريح
                        if val is None:
                            values[str(j)] = None
                        else:
                            values[str(j)] = val
                    try:
                        pg_cursor.execute(insert_sql, **values)
                    except Exception as e:
                        print(f"⚠️ خطأ في صف: {e}")
            
            pg_conn.commit()
            print(f"✅ {table}: تم نقل {len(rows)} صف")
            
        except Exception as e:
            print(f"❌ فشل نقل {table}: {e}")
    
    pg_cursor.close()

# ===================== التنفيذ =====================
if __name__ == "__main__":
    print("=" * 60)
    print("🔄 بدء ترحيل حوكمة ERP من SQLite إلى PostgreSQL")
    print("=" * 60)
    
    # الاتصال
    print("\n📂 الاتصال بقاعدة SQLite...")
    sqlite_conn = get_sqlite_conn()
    
    print("🐘 الاتصال بقاعدة PostgreSQL...")
    pg_conn = get_pg_conn()
    
    # إنشاء الجداول
    print("\n🏗️ إنشاء الجداول في PostgreSQL...")
    create_tables_in_postgres(pg_conn, sqlite_conn)
    
    # نقل البيانات
    print("\n📦 نقل البيانات...")
    migrate_data(pg_conn, sqlite_conn)
    
    # إغلاق الاتصالات
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n" + "=" * 60)
    print("✅ الترحيل اكتمل بنجاح!")
    print("=" * 60)
