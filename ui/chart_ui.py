# ui/chart_ui.py – واجهة شجرة الحسابات (v3.0)
# ✅ v3.0:
#   - إخفاء الحسابات النظامية (is_system=1) افتراضياً
#   - منع حذف الحسابات النظامية
#   - خيار "عرض الحسابات النظامية" للمستخدم
#   - تمرير created_by + deleted_by لتسجيل التدقيق
import streamlit as st
import pandas as pd
from services.chart_service import (
    create_accounts_table,
    add_account,
    get_accounts_tree,
    build_tree,
    get_account_options,
    delete_account
)

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

# خيارات الأنواع الوظيفية للحسابات التلقائية للنظام
FUNCTIONAL_TYPES = {
    "بدون (حساب عادي/فرعي)": None,
    "النقدية/الصندوق (cash)": "cash",
    "البنك (bank)": "bank",
    "المخزون (inventory)": "inventory",
    "العملاء/مدينون": "accounts_receivable",
    "الموردون/دائنون": "accounts_payable",
    "إيرادات المبيعات (sales_revenue)": "sales_revenue",
    "تكلفة البضاعة المباعة (cogs)": "cogs",
    "ضريبة المبيعات/مخرجات (sales_tax)": "sales_tax",
    "ضريبة المشتريات/مدخلات (purchase_tax)": "purchase_tax",
    "المصروفات العامة (operating_expense)": "operating_expense",
    "رأس المال (capital)": "capital",
    "الأرباح المبقاة (retained_earnings)": "retained_earnings",
    "مصروف الإهلاك (depreciation_expense)": "depreciation_expense",
    "مجمع الإهلاك (accumulated_depreciation)": "accumulated_depreciation",
    "مصروف الرواتب (salaries_expense)": "salaries_expense",
    "المصروفات المستحقة (accrued_expenses)": "accrued_expenses",
    "أرباح/زيادة المخزون (inventory_gain)": "inventory_gain",
    "خسائر/نقص الجرد (inventory_loss)": "inventory_loss",
    "فروق أسعار الصرف (exchange_difference)": "exchange_difference",
}


def _current_username():
    """✅ الحصول على المستخدم الحالي بأمان"""
    user = st.session_state.get('user') or {}
    return user.get('username', 'admin')


def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 شجرة الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الحسابات الهرمية والربط الوظيفي للنظام المحاسبي</p>
    </div>
    """, unsafe_allow_html=True)

    create_accounts_table()

    tab1, tab2 = st.tabs(["📊 عرض الشجرة", "➕ إضافة حساب"])

    # ============================================================
    # تبويب 1: عرض الشجرة
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>شجرة الحسابات</h3>",
                    unsafe_allow_html=True)

        # ✅ v3.0: خيار عرض الحسابات النظامية
        col_title, col_toggle = st.columns([3, 1])
        with col_toggle:
            show_system = st.checkbox(
                "🔧 عرض النظامية",
                value=False,
                help="عرض الحسابات النظامية (بنوك/صناديق فرعية)",
                key="show_system_accounts"
            )

        all_accounts = get_accounts_tree()

        # ✅ v3.0: فلترة الحسابات النظامية
        if all_accounts:
            if not show_system:
                accounts = [
                    a for a in all_accounts
                    if not a.get('is_system', 0)
                ]
            else:
                accounts = all_accounts
        else:
            accounts = []

        if accounts:
            # ✨ فرز الشجرة بترتيب هرمي دقيق
            accounts = sorted(accounts, key=lambda x: (len(x["code"]), x["code"]))

            tree = build_tree(accounts)
            df = pd.DataFrame(tree)
            df["display_name"] = df.apply(
                lambda r: " " * r["indent"] + r["name"], axis=1
            )

            def where_appears(acc_type):
                if acc_type in ("Asset", "Liability", "Equity"):
                    return "الميزانية العمومية"
                elif acc_type in ("Revenue", "Expense"):
                    return "قائمة الدخل"
                else:
                    return "غير محدد"

            df["يظهر في"] = df["account_type"].apply(where_appears)

            if "functional_type" not in df.columns:
                df["functional_type"] = "-"

            # ✅ v3.0: إضافة عمود "نظامي"
            if "is_system" not in df.columns:
                df["is_system"] = 0
            df["نظامي"] = df["is_system"].apply(
                lambda x: "🔧" if x else ""
            )

            df_display = df[[
                "code", "display_name", "level",
                "account_type", "functional_type", "يظهر في", "نظامي"
            ]].rename(columns={
                "code": "الكود",
                "display_name": "اسم الحساب",
                "level": "المستوى",
                "account_type": "التصنيف",
                "functional_type": "النوع الوظيفي",
                "يظهر في": "يظهر في",
                "نظامي": "🔧"
            })

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # ✅ v3.0: تنبيه
            if show_system:
                st.info("ℹ️ **الحسابات النظامية معروضة** — الحسابات المعلَّمة بـ 🔧 مُدارة تلقائياً من وحدات البنك/الصندوق.")

            st.markdown("---")
            st.subheader("🗑️ إدارة الحسابات")

            # ✅ تأكيد الحذف
            if "delete_confirm" not in st.session_state:
                st.session_state.delete_confirm = None

            for acc in accounts:
                # ✅ v3.0: تمييز الحسابات النظامية
                is_sys = acc.get('is_system', 0)

                col1, col2 = st.columns([4, 1])
                with col1:
                    if is_sys:
                        st.text(f"🔧 {acc['code']} - {acc['name']} (نظامي)")
                    else:
                        st.text(f"{acc['code']} - {acc['name']}")

                with col2:
                    if is_sys:
                        # ✅ v3.0: منع حذف الحسابات النظامية
                        st.button(
                            "🔒 محمي",
                            key=f"del_{acc['id']}",
                            disabled=True,
                            help="حساب نظامي — يُدار تلقائياً"
                        )
                    else:
                        if st.button("🗑️ حذف", key=f"del_{acc['id']}"):
                            st.session_state.delete_confirm = acc['id']
                            st.rerun()

            # ✅ نافذة تأكيد الحذف
            if st.session_state.delete_confirm:
                acc_id = st.session_state.delete_confirm
                acc = next((a for a in accounts if a['id'] == acc_id), None)

                # ✅ v3.0: حماية مزدوجة
                if acc and acc.get('is_system', 0):
                    st.error("⚠️ لا يمكن حذف حساب نظامي — استخدم وحدة البنك/الصندوق")
                    st.session_state.delete_confirm = None
                elif acc:
                    st.warning(
                        f"⚠️ هل أنت متأكد من حذف الحساب "
                        f"**{acc['code']} - {acc['name']}**؟"
                    )
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        if st.button("✅ نعم، احذف", type="primary",
                                     key="confirm_delete_yes"):
                            success, message = delete_account(
                                acc_id,
                                deleted_by=_current_username(),
                            )
                            st.session_state.delete_confirm = None
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    with col_c2:
                        if st.button("❌ إلغاء", key="confirm_delete_no"):
                            st.session_state.delete_confirm = None
                            st.rerun()
        else:
            if all_accounts:
                st.info("لا توجد حسابات عادية للعرض — فعّل 'عرض النظامية' لرؤية جميع الحسابات.")
            else:
                st.info("لا توجد حسابات. أضف حسابات جديدة من التبويب الثاني.")

    # ============================================================
    # تبويب 2: إضافة حساب
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة حساب جديد</h3>",
                    unsafe_allow_html=True)
        account_options = get_account_options()

        # ✅ v3.0: فلترة خيارات الحساب الأب — لا نُظهر النظامية كخيار
        filtered_options = {}
        for label, pid in account_options.items():
            if pid is None:
                filtered_options[label] = pid
                continue
            # نتحقق إذا كان الحساب نظامياً
            acc = next(
                (a for a in get_accounts_tree() if a['id'] == pid),
                None
            )
            if acc and not acc.get('is_system', 0):
                filtered_options[label] = pid

        selected_parent = st.selectbox("الحساب الأب", list(filtered_options.keys()))
        parent_id = filtered_options[selected_parent]

        col1, col2 = st.columns(2)
        code = col1.text_input("كود الحساب", key="add_acc_code")
        name = col2.text_input("اسم الحساب", key="add_acc_name")

        col3, col4 = st.columns(2)

        account_type = col3.selectbox(
            "تصنيف الحساب الرئيسي",
            ["", "Asset - أصل", "Liability - خصم", "Equity - حقوق ملكية",
             "Revenue - إيراد", "Expense - مصروف"],
            help="يحدد أين يظهر الحساب في القوائم المالية",
            key="add_acc_type"
        )

        selected_func_label = col4.selectbox(
            "النوع الوظيفي للنظام",
            list(FUNCTIONAL_TYPES.keys()),
            help="إذا كان هذا الحساب مخصصاً لاستقبال فواتير المبيعات/المشتريات أو الصندوق تلقائياً اختر نوعه هنا",
            key="add_acc_func"
        )

        account_type_map = {
            "Asset - أصل": "Asset",
            "Liability - خصم": "Liability",
            "Equity - حقوق ملكية": "Equity",
            "Revenue - إيراد": "Revenue",
            "Expense - مصروف": "Expense"
        }
        selected_account_type = account_type_map.get(account_type)
        functional_type = FUNCTIONAL_TYPES.get(selected_func_label)

        if st.button("💾 حفظ الحساب", key="add_acc_save"):
            if not code or not name:
                st.error("الكود والاسم مطلوبان")
            else:
                success, error = add_account(
                    code, name, parent_id,
                    selected_account_type,
                    functional_type=functional_type,
                    created_by=_current_username(),
                )
                if success:
                    st.success(f"تم إضافة الحساب {code} - {name} بنجاح!")
                    st.rerun()
                else:
                    st.error(error)
