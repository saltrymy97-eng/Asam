import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from database import get_conn, get_accounts_tree

# ============================================================
# 1. الدوال المساعدة للتقارير المالية
# ============================================================
def get_account_balance(account_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(debit),0) - COALESCE(SUM(credit),0) FROM journal_details WHERE account_id=?", (account_id,))
    bal = cur.fetchone()[0]
    conn.close()
    return bal

def get_trial_balance():
    accounts = get_accounts_tree()
    data = []
    for acc in accounts:
        bal = get_account_balance(acc['id'])
        if bal != 0:
            data.append({
                "رقم الحساب": acc['code'],
                "اسم الحساب": acc['name'],
                "النوع": acc['type'],
                "مدين": bal if bal > 0 and acc['type'] in ['asset', 'expense'] else 0,
                "دائن": -bal if bal < 0 and acc['type'] in ['asset', 'expense'] else (bal if bal > 0 and acc['type'] in ['liability', 'equity', 'revenue'] else 0)
            })
    return pd.DataFrame(data)

def get_income_statement():
    accounts = get_accounts_tree()
    revenues = []
    expenses = []
    for acc in accounts:
        bal = get_account_balance(acc['id'])
        if acc['type'] == 'revenue':
            revenues.append({"الحساب": acc['name'], "الرصيد": bal})
        elif acc['type'] == 'expense':
            expenses.append({"الحساب": acc['name'], "الرصيد": bal})
    total_rev = sum(r['الرصيد'] for r in revenues)
    total_exp = sum(e['الرصيد'] for e in expenses)
    net = total_rev - total_exp
    return pd.DataFrame(revenues), pd.DataFrame(expenses), total_rev, total_exp, net

def get_balance_sheet():
    accounts = get_accounts_tree()
    assets = []
    liabilities = []
    equity = []
    for acc in accounts:
        bal = get_account_balance(acc['id'])
        if acc['type'] == 'asset':
            assets.append({"الحساب": acc['name'], "الرصيد": bal})
        elif acc['type'] == 'liability':
            liabilities.append({"الحساب": acc['name'], "الرصيد": bal})
        elif acc['type'] == 'equity':
            equity.append({"الحساب": acc['name'], "الرصيد": bal})
    total_assets = sum(a['الرصيد'] for a in assets)
    total_liab = sum(l['الرصيد'] for l in liabilities)
    total_eq = sum(e['الرصيد'] for e in equity)
    return pd.DataFrame(assets), pd.DataFrame(liabilities), pd.DataFrame(equity), total_assets, total_liab, total_eq

# ============================================================
# 2. دوال سجل التدقيق (Audit Log)
# ============================================================
def init_audit_table():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        action TEXT,
        table_name TEXT,
        record_id INTEGER,
        details TEXT,
        timestamp TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.commit()
    conn.close()

def log_action(user, action, table_name, record_id, details=""):
    conn = get_conn()
    conn.execute("INSERT INTO audit_log (user, action, table_name, record_id, details) VALUES (?,?,?,?,?)",
                 (user, action, table_name, record_id, details))
    conn.commit()
    conn.close()

def get_audit_log(limit=100):
    conn = get_conn()
    df = pd.read_sql(f"SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT {limit}", conn)
    conn.close()
    return df

init_audit_table()

# ============================================================
# 3. دوال إدارة المستخدمين
# ============================================================
def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def get_all_users():
    conn = get_conn()
    df = pd.read_sql("SELECT id, username, role FROM users", conn)
    conn.close()
    return df

def add_user(username, password, role):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                     (username, hash_password(password), role))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def update_user(user_id, role, new_password=None):
    conn = get_conn()
    if new_password:
        conn.execute("UPDATE users SET role=?, password_hash=? WHERE id=?", (role, hash_password(new_password), user_id))
    else:
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ============================================================
# 4. الواجهة الرئيسية (تعرض عند استدعاء الملف)
# ============================================================
st.title("🛠️ الأدوات المتقدمة")
st.caption("تقارير مالية - سجل تدقيق - إدارة المستخدمين")

tab1, tab2, tab3 = st.tabs(["📊 التقارير المالية", "📜 سجل التدقيق", "👥 إدارة المستخدمين"])

# ---------- التبويب الأول: التقارير المالية ----------
with tab1:
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📋 ميزان المراجعة", "📈 قائمة الدخل", "📋 الميزانية العمومية"])
    
    with sub_tab1:
        st.subheader("ميزان المراجعة")
        tb = get_trial_balance()
        if not tb.empty:
            st.dataframe(tb, use_container_width=True)
            st.metric("مجموع المديـن", f"{tb['مدين'].sum():,.2f}")
            st.metric("مجموع الدائن", f"{tb['دائن'].sum():,.2f}")
        else:
            st.info("لا توجد أرصدة")
    
    with sub_tab2:
        st.subheader("قائمة الدخل")
        rev, exp, total_rev, total_exp, net = get_income_statement()
        col1, col2 = st.columns(2)
        with col1:
            st.write("**الإيرادات**")
            st.dataframe(rev, use_container_width=True)
            st.metric("إجمالي الإيرادات", f"{total_rev:,.2f}")
        with col2:
            st.write("**المصروفات**")
            st.dataframe(exp, use_container_width=True)
            st.metric("إجمالي المصروفات", f"{total_exp:,.2f}")
        st.divider()
        st.metric("صافي الربح / الخسارة", f"{net:,.2f}", delta_color="normal" if net>=0 else "inverse")
    
    with sub_tab3:
        st.subheader("الميزانية العمومية")
        assets, liab, equity, total_a, total_l, total_e = get_balance_sheet()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**الأصول**")
            st.dataframe(assets, use_container_width=True)
            st.metric("الإجمالي", f"{total_a:,.2f}")
        with col2:
            st.write("**الخصوم**")
            st.dataframe(liab, use_container_width=True)
            st.metric("الإجمالي", f"{total_l:,.2f}")
        with col3:
            st.write("**حقوق الملكية**")
            st.dataframe(equity, use_container_width=True)
            st.metric("الإجمالي", f"{total_e:,.2f}")
        st.divider()
        st.success(f"تحقق: الأصول ({total_a:,.2f}) = الخصوم ({total_l:,.2f}) + حقوق الملكية ({total_e:,.2f})")

# ---------- التبويب الثاني: سجل التدقيق ----------
with tab2:
    sub1, sub2 = st.tabs(["📜 عرض السجل", "➕ تسجيل اختباري"])
    with sub1:
        log_df = get_audit_log()
        if not log_df.empty:
            st.dataframe(log_df, use_container_width=True)
        else:
            st.info("لا توجد سجلات تدقيق بعد")
    with sub2:
        st.write("تسجيل حدث تجريبي (للتأكد من عمل السجل)")
        username = st.text_input("اسم المستخدم", value=st.session_state.get("username", "admin"))
        action = st.selectbox("الإجراء", ["إضافة", "تعديل", "حذف", "بيع", "شراء"])
        table = st.text_input("اسم الجدول", value="products")
        record_id = st.number_input("معرف السجل", min_value=1, step=1, value=1)
        details = st.text_area("تفاصيل إضافية")
        if st.button("تسجيل حدث"):
            log_action(username, action, table, record_id, details)
            st.success("تم التسجيل")
            st.rerun()

# ---------- التبويب الثالث: إدارة المستخدمين ----------
with tab3:
    if "role" not in st.session_state or st.session_state.role != "admin":
        st.error("عذراً، هذه الصفحة مخصصة للمسؤولين فقط.")
    else:
        user_tab1, user_tab2 = st.tabs(["📋 قائمة المستخدمين", "➕ إضافة مستخدم"])
        with user_tab1:
            users = get_all_users()
            if not users.empty:
                for _, row in users.iterrows():
                    with st.expander(f"{row['username']} - {row['role']}"):
                        new_role = st.selectbox("الدور", ["admin","cashier","accountant"], index=["admin","cashier","accountant"].index(row['role']), key=f"role_{row['id']}")
                        new_pwd = st.text_input("كلمة مرور جديدة (اتركها فارغة لعدم التغيير)", type="password", key=f"pwd_{row['id']}")
                        col1, col2 = st.columns(2)
                        if col1.button("تحديث", key=f"upd_{row['id']}"):
                            if new_pwd:
                                update_user(row['id'], new_role, new_pwd)
                            else:
                                update_user(row['id'], new_role)
                            st.success("تم التحديث")
                            st.rerun()
                        if col2.button("حذف", key=f"del_{row['id']}"):
                            delete_user(row['id'])
                            st.success("تم الحذف")
                            st.rerun()
            else:
                st.info("لا يوجد مستخدمون")
        with user_tab2:
            with st.form("add_user_form"):
                new_username = st.text_input("اسم المستخدم")
                new_password = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الدور", ["admin","cashier","accountant"])
                submitted = st.form_submit_button("إضافة مستخدم")
                if submitted:
                    if new_username and new_password:
                        if add_user(new_username, new_password, new_role):
                            st.success("تمت الإضافة")
                            st.rerun()
                        else:
                            st.error("اسم المستخدم موجود مسبقاً")
                    else:
                        st.error("يرجى ملء جميع الحقول")
