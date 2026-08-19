# ui/accounting_ui.py – واجهة الحسابات (تصميم زجاجي فخم + عرض احترافي للأسماء والأرصدة + عملات متعددة)
import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import date
from services.accounting_service import (
    get_account_code,
    save_journal_entry,
    get_recent_entries,
    get_entry_details,
    get_ledger,
    get_trial_balance,
    get_distinct_accounts
)
from services.audit_service import log_action
from services import cost_center_service
from services.currency_service import get_base_currency, get_exchange_rate

DB_PATH = os.path.join("data", "erp.db")

# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

# ---------- دوال مساعدة للعرض الاحترافي ----------
def get_account_display_name(code):
    """تحويل كود الحساب إلى اسمه الكامل من شجرة الحسابات"""
    if not code:
        return ""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # إذا كان الكود رقماً، نبحث عنه في شجرة الحسابات
    if code.isdigit():
        row = conn.execute("SELECT code, name FROM accounts WHERE code = ?", (code,)).fetchone()
        conn.close()
        if row:
            return f"{row['code']} - {row['name']}"
    # إذا لم يكن رقماً (مثل اسم العميل)، نرجعه كما هو
    conn.close()
    return code

def get_accounts_list():
    """جلب جميع الحسابات من شجرة الحسابات"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()
    conn.close()
    return [f"{a['code']} - {a['name']}" for a in accounts]

def get_cost_centers_list():
    """جلب قائمة مراكز التكلفة النشطة للاختيار"""
    centers = cost_center_service.get_all_cost_centers(active_only=True)
    if not centers:
        return [], {}
    options = [f"{c['code']} - {c['name']}" for c in centers]
    mapping = {f"{c['code']} - {c['name']}": c['id'] for c in centers}
    return options, mapping

def get_all_currencies():
    """جلب جميع العملات النشطة من قاعدة البيانات"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # جلب العملات النشطة
    currencies = conn.execute(
        "SELECT code, name, symbol FROM currencies WHERE is_active = 1 ORDER BY is_base DESC, code"
    ).fetchall()
    conn.close()
    return currencies

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">قيود اليومية، دفتر الأستاذ، وميزان المراجعة</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 قيود اليومية", "📖 دفتر الأستاذ", "⚖️ ميزان المراجعة"])

    # ---------- قيود اليومية ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>تسجيل قيد يومية</h3>", unsafe_allow_html=True)
        
        accounts_list = get_accounts_list()
        cc_options, cc_mapping = get_cost_centers_list()
        currencies = get_all_currencies()
        
        if not accounts_list:
            st.warning("لا توجد حسابات. أضف حسابات من شجرة الحسابات أولاً.")
        else:
            with st.form("journal_entry_form"):
                entry_date = st.date_input("التاريخ", value=date.today())
                description = st.text_input("البيان", placeholder="أدخل وصف العملية المالية")
                
                st.markdown(f"<p style='color:{TEXT_SECONDARY}; margin-top:1rem;'>الأسطر المحاسبية (حتى 4 أسطر)</p>", unsafe_allow_html=True)
                
                lines = []
                cost_center_allocations = []
                
                for i in range(4):
                    cols = st.columns([3, 1.5, 1.5, 1])
                    account = cols[0].selectbox(
                        f"الحساب {i+1}",
                        [""] + accounts_list,
                        key=f"acc_{i}"
                    )
                    debit = cols[1].number_input(f"مدين {i+1}", min_value=0.0, step=0.01, key=f"deb_{i}")
                    credit = cols[2].number_input(f"دائن {i+1}", min_value=0.0, step=0.01, key=f"cred_{i}")
                    
                    # ✨ إضافة قائمة منسدلة للعملة
                    curr_names = [f"{c['code']} - {c['name']}" for c in currencies]
                    if curr_names:
                        # افتراضي العملة الأساسية
                        base_currency = get_base_currency()
                        default_curr = f"{base_currency['code']} - {base_currency['name']}" if base_currency else curr_names[0]
                        selected_curr = cols[3].selectbox(
                            f"العملة {i+1}",
                            curr_names,
                            index=curr_names.index(default_curr) if default_curr in curr_names else 0,
                            key=f"curr_{i}"
                        )
                        currency_code = selected_curr.split(" - ")[0]
                    else:
                        currency_code = "YER"
                    
                    if account:
                        code = account.split(" - ")[-1]
                        lines.append({
                            "account": code, 
                            "debit": debit, 
                            "credit": credit,
                            "currency_code": currency_code
                        })
                        
                        if cc_options:
                            with st.expander(f"🎯 توزيع مراكز التكلفة للسطر {i+1}", expanded=False):
                                st.caption("يمكنك توزيع مبلغ السطر على حتى 3 مراكز تكلفة")
                                allocs_for_line = []
                                remaining_amount = debit if debit > 0 else credit
                                
                                for j in range(3):
                                    c_cols = st.columns([3, 2, 2])
                                    center_choice = c_cols[0].selectbox(
                                        f"مركز التكلفة {j+1}",
                                        ["-- لا يوجد --"] + cc_options,
                                        key=f"cc_{i}_{j}"
                                    )
                                    if center_choice != "-- لا يوجد --":
                                        center_id = cc_mapping[center_choice]
                                        alloc_amount = c_cols[1].number_input(
                                            f"المبلغ {j+1}",
                                            min_value=0.0,
                                            max_value=float(remaining_amount),
                                            step=0.01,
                                            key=f"cc_amt_{i}_{j}"
                                        )
                                        alloc_pct = c_cols[2].number_input(
                                            f"% {j+1}",
                                            min_value=0.0,
                                            max_value=100.0,
                                            step=1.0,
                                            key=f"cc_pct_{i}_{j}"
                                        )
                                        if alloc_amount > 0:
                                            allocs_for_line.append({
                                                'cost_center_id': center_id,
                                                'amount': alloc_amount,
                                                'percentage': alloc_pct if alloc_pct > 0 else (alloc_amount / remaining_amount * 100 if remaining_amount > 0 else 0)
                                            })
                                
                                if allocs_for_line:
                                    total_alloc = sum(a['amount'] for a in allocs_for_line)
                                    if abs(total_alloc - remaining_amount) > 0.01:
                                        st.warning(f"مجموع التوزيعات ({total_alloc:,.2f}) لا يساوي مبلغ السطر ({remaining_amount:,.2f})")
                                    cost_center_allocations.append({
                                        'line_index': i,
                                        'allocations': allocs_for_line
                                    })

                submitted = st.form_submit_button("💾 حفظ القيد", type="primary")
                
                if submitted:
                    if not description:
                        st.error("البيان مطلوب")
                    elif not lines:
                        st.error("أضف سطراً محاسبياً واحداً على الأقل")
                    else:
                        # 🚀 إرسال البيانات مباشرة للخدمة الخلفية (Backend) التي تدعم العملات
                        # (تم إزالة شرط التحقق المبدئي الذي كان يمنع العملات الأجنبية)
                        entry_id, error = save_journal_entry(
                            description, lines, entry_date.strftime("%Y-%m-%d"),
                            cost_center_allocations=cost_center_allocations if cost_center_allocations else None
                        )
                        
                        if error:
                            # ستظهر هنا رسالة الخطأ الذكية التي تأتي من accounting_service (بالعملة الأساسية)
                            st.error(error)
                        else:
                            # جلب اسم المستخدم بأمان من الجلسة لتفادي أخطاء المفاتيح
                            username = st.session_state.user.get('username', 'admin') if 'user' in st.session_state else 'admin'
                            log_action(
                                username=username,
                                action="قيد يومية",
                                table_name="journal_entries",
                                record_id=entry_id,
                                new_value=f"البيان: {description}"
                            )
                            st.success("تم تسجيل القيد بنجاح مع تحويل العملات وتوزيعات مراكز التكلفة ✅")
                            st.rerun()

        # عرض آخر القيود
        st.markdown("---")
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};\">آخر قيود اليومية</h4>", unsafe_allow_html=True)
        entries = get_recent_entries()
        if entries:
            df_entries = pd.DataFrame(entries)
            st.dataframe(df_entries, use_container_width=True, hide_index=True)
            
            entry_ids = [e['id'] for e in entries]
            selected_entry = st.selectbox("اختر قيداً لعرض تفاصيله", entry_ids)
            if selected_entry:
                details = get_entry_details(selected_entry)
                if details:
                    for idx, line in enumerate(details):
                        display_name = get_account_display_name(line['account_name'])
                        with st.container():
                            st.markdown(f"""
                            <div style="background:{GLASS_BG}; border:1px solid {GLASS_BORDER}; 
                                        border-radius:10px; padding:10px; margin-bottom:10px;">
                                <strong>الحساب:</strong> {display_name} &nbsp;&nbsp;
                                <strong>مدين:</strong> {line['debit']:,.2f} &nbsp;&nbsp;
                                <strong>دائن:</strong> {line['credit']:,.2f} &nbsp;&nbsp;
                                <strong>العملة:</strong> {line['currency_code']} &nbsp;&nbsp;
                                <strong>سعر الصرف:</strong> {line['exchange_rate']}
                            </div>
                            """, unsafe_allow_html=True)
                            if line.get('cost_center_allocations'):
                                st.caption("توزيع مراكز التكلفة:")
                                alloc_df = pd.DataFrame(line['cost_center_allocations'])
                                st.dataframe(alloc_df, use_container_width=True, hide_index=True)
                            else:
                                st.caption("لا يوجد توزيع لمراكز تكلفة")
                    total_d = sum(d['debit'] for d in details)
                    total_c = sum(d['credit'] for d in details)
                    st.markdown(f"**المجموع: مدين {total_d:,.2f} | دائن {total_c:,.2f}**")
        else:
            st.info("لا توجد قيود بعد")

    # ---------- دفتر الأستاذ ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>دفتر الأستاذ العام</h3>", unsafe_allow_html=True)
        accounts = get_distinct_accounts()
        if accounts:
            # تحويل الأكواد إلى أسماء قابلة للقراءة
            display_accounts = [get_account_display_name(acc) for acc in accounts]
            acc_mapping = dict(zip(display_accounts, accounts))
            
            selected_display = st.selectbox("اختر الحساب", display_accounts)
            selected_account = acc_mapping[selected_display]
            
            ledger = get_ledger(selected_account)
            if ledger:
                df_ledger = pd.DataFrame(ledger)
                df_ledger["رصيد مدين"] = df_ledger["debit"] - df_ledger["credit"]
                df_ledger["رصيد دائن"] = df_ledger["credit"] - df_ledger["debit"]
                df_ledger["رصيد مدين"] = df_ledger["رصيد مدين"].apply(lambda x: x if x > 0 else 0)
                df_ledger["رصيد دائن"] = df_ledger["رصيد دائن"].apply(lambda x: x if x > 0 else 0)
                
                # ✅ التعديل الاحترافي: التأكد من وجود العمود قبل تحويله
                if "account_name" in df_ledger.columns:
                    df_ledger["account_name"] = df_ledger["account_name"].apply(get_account_display_name)
                
                # إعادة ترتيب الأعمدة للعرض (مع التأكد من وجود account_name)
                cols = ["date", "description", "debit", "credit", "رصيد مدين", "رصيد دائن", "currency_code", "exchange_rate"]
                if "account_name" in df_ledger.columns:
                    cols.insert(2, "account_name")  # إضافة اسم الحساب في المكان المناسب
                
                df_ledger = df_ledger[cols]
                st.dataframe(df_ledger, use_container_width=True, hide_index=True)
                
                final_balance = (df_ledger["debit"].sum() - df_ledger["credit"].sum())
                if final_balance > 0:
                    st.markdown(f"**الرصيد النهائي: {final_balance:,.2f} (مدين)**")
                elif final_balance < 0:
                    st.markdown(f"**الرصيد النهائي: {abs(final_balance):,.2f} (دائن)**")
                else:
                    st.markdown(f"**الرصيد النهائي: 0.00**")
            else:
                st.info("لا توجد حركات على هذا الحساب")
        else:
            st.info("لا توجد حسابات بعد")

    # ---------- ميزان المراجعة ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>ميزان المراجعة</h3>", unsafe_allow_html=True)
        tb = get_trial_balance()
        if tb:
            df_tb = pd.DataFrame(tb)
            df_tb["رصيد مدين"] = df_tb["total_debit"] - df_tb["total_credit"]
            df_tb["رصيد دائن"] = df_tb["total_credit"] - df_tb["total_debit"]
            df_tb["رصيد مدين"] = df_tb["رصيد مدين"].apply(lambda x: x if x > 0 else 0)
            df_tb["رصيد دائن"] = df_tb["رصيد دائن"].apply(lambda x: x if x > 0 else 0)
            
            # 🔧 تحسين أسماء الحسابات
            df_tb["account_name"] = df_tb["account_name"].apply(get_account_display_name)
            
            df_tb = df_tb[["account_name", "total_debit", "total_credit", "رصيد مدين", "رصيد دائن"]]
            st.dataframe(df_tb, use_container_width=True, hide_index=True)
            
            total_d = df_tb["total_debit"].sum()
            total_c = df_tb["total_credit"].sum()
            st.markdown(f"**إجمالي المدين: {total_d:,.2f} | إجمالي الدائن: {total_c:,.2f}**")
            if abs(total_d - total_c) < 0.01:
                st.success("الميزان متوازن ✅")
            else:
                st.error("الميزان غير متوازن ⚠️")
        else:
            st.info("لا توجد قيود لعرض ميزان المراجعة")
