# migrate_to_postgres.py – سكربت ترحيل حوكمة ERP من SQLite إلى PostgreSQL (pg8000)
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
    else:
        return "TEXT"

def create_tables_in_postgres(pg_conn, sqlite_conn):
    """إنشاء جميع الجداول في PostgreSQL بنفس هيكل SQLite"""
    cur = sqlite_conn.cursor()
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row["name"] for row in cur.fetchall()]
    
    for table in tables:
        try:
            # حذف الجدول إذا كان موجوداً
            pg_conn.run(f'DROP TABLE IF EXISTS "{table}" CASCADE')
            
            cur.execute(f"PRAGMA table_info('{table}')")
            columns = cur.fetchall()
            
            if not columns:
                continue
            
            col_defs = []
            
            for col in columns:
                col_name = col["name"]
                col_type = sqlite_type_to_pg(col["type"])
                is_pk = col["pk"] > 0
                not_null = col["notnull"] > 0
                
                if is_pk and "INT" in col_type.upper():
                    col_defs.append(f'"{col_name}" SERIAL PRIMARY KEY')
                else:
                    col_def_parts = [f'"{col_name}" {col_type}']
                    if not_null and not is_pk:
                        col_def_parts.append("NOT NULL")
                    if col["dflt_value"] is not None:
                        dflt = col["dflt_value"]
                        if dflt.upper() == "CURRENT_TIMESTAMP":
                            col_def_parts.append("DEFAULT CURRENT_TIMESTAMP")
                        elif dflt.startswith("'") and dflt.endswith("'"):
                            col_def_parts.append(f"DEFAULT {dflt}")
                        else:
                            try:
                                float(dflt)
                                col_def_parts.append(f"DEFAULT {dflt}")
                            except:
                                pass
                    if is_pk and "INT" not in col_type.upper():
                        col_def_parts.append("PRIMARY KEY")
                    col_defs.append(" ".join(col_def_parts))
            
            create_sql = f'CREATE TABLE "{table}" (\n  ' + ',\n  '.join(col_defs) + '\n)'
            pg_conn.run(create_sql)
            print(f"✅ تم إنشاء جدول: {table}")
            
        except Exception as e:
            print(f"❌ فشل إنشاء جدول {table}: {e}")

def migrate_data(pg_conn, sqlite_conn):
    """نسخ البيانات من SQLite إلى PostgreSQL"""
    cur = sqlite_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row["name"] for row in cur.fetchall()]
    
    for table in tables:
        try:
            cur.execute(f'SELECT * FROM "{table}"')
            rows = cur.fetchall()
            
            if not rows:
                print(f"⚠️ {table}: لا توجد بيانات")
                continue
            
            columns = [desc[0] for desc in cur.description]
            cols = '","'.join(columns)
            
            # استخدام INSERT متعدد
            for row in rows:
                values = [row[col] for col in columns]
                placeholders = ','.join([':%s' % i for i in range(len(columns))]
                pg_conn.run(f'INSERT INTO "{table}" ("{cols}") VALUES ({placeholders})', **dict(zip([str(i) for i in range(len(columns))], values)))
            
            print(f"✅ {table}: تم نقل {len(rows)} صف")
            
        except Exception as e:
            print(f"❌ فشل نقل {table}: {e}")

# ===================== التنفيذ =====================
if __name__ == "__main__":
    print("=" * 60)
    print("🔄 بدء ترحيل حوكمة ERP من SQLite إلى PostgreSQL")
    print("=" * 60)
    
    sqlite_conn = get_sqlite_conn()
    pg_conn = get_pg_conn()
    
    print("\n🏗️ إنشاء الجداول في PostgreSQL...")
    create_tables_in_postgres(pg_conn, sqlite_conn)
    
    print("\n📦 نقل البيانات...")
    migrate_data(pg_conn, sqlite_conn)
    
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n✅ الترحيل اكتمل بنجاح!")
