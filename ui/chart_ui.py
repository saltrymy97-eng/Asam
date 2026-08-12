# ui/chart_ui.py – واجهة شجرة الحسابات (تصميم زجاجي فخم + توضيح وجهة الحساب + دعم الحسابات الوظيفية)
import streamlit as st
import pandas as pd
from services.chart_service import (
    create_accounts_table,
    add_account,
    get_accounts_tree,
    build_tree,
    get_account_options,
    delete_account  # <--- تم استيراد دالة الحذف
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
    "العملاء/مدينون": "customers",
    "الموردون/دائنون": "suppliers",
    "إيرادات المبيعات (sales_revenue)": "sales_revenue",
    "تكلفة البضاعة المباعة (cogs)": "cogs",
    "ضريبة المبيعات/مخرجات (sales_tax)": "sales_tax",
    "ضريبة المشتريات/مدخلات (purchase_tax)": "purchase_tax",
    "المصروفات العامة (operating_expense)": "operating_expense",
    "رأس المال (capital)": "capital",
    "الأرباح المبقاة (retained_earnings)": "retained_earnings"
}

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 شجرة الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الحسابات الهرمية والربط الوظيفي للنظام المحاسبي</p>
    </div>
    """, unsafe_allow_html=True)

    create_accounts_table()

    tab1, tab2 = st.tabs(["📊 عرض الشجرة", "➕ إضافة حساب"])

    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>شجرة الحسابات</h3>", unsafe_allow_html=True)
        accounts = get_accounts_tree()
        if accounts:
            tree = build_tree(accounts)
            df = pd.DataFrame(tree)
            df["display_name"] = df.apply(lambda r: " " * r["indent"] + r["name"], axis=1)
            
            # تحديد أين يظهر الحساب بناءً على تصنيفه
            def where_appears(acc_type):
                if acc_type in ("Asset", "Liability", "Equity"):
                    return "الميزانية العمومية"
                elif acc_type in ("Revenue", "Expense"):
                    return "قائمة الدخل"
                else:
                    return "غير محدد"
            
            df["يظهر في"] = df["account_type"].apply(where_appears)
            
            # إضافة عمود النوع الوظيفي إذا كان متوفراً في DataFrame
            if "functional_type" not in df.columns:
                df["functional_type"] = "-"

            # إعادة ترتيب وتسمية الأعمدة للعرض
            df_display = df[["code", "display_name", "level", "account_type", "functional_type", "يظهر في"]].rename(
                columns={
                    "code": "الكود",
                    "display_name": "اسم الحساب",
                    "level": "المستوى",
                    "account_type": "التصنيف",
                    "functional_type": "النوع الوظيفي",
                    "يظهر في": "يظهر في"
                }
            )
            
            # عرض الجدول مع أزرار الحذف (تعديل جديد)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # إضافة أزرار الحذف أسفل الجدول أو بجانب كل صف
            st.markdown("---")
            st.subheader("🗑️ إدارة الحسابات")
            for acc in accounts:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"{acc['code']} - {acc['name']}")
                with col2:
                    if st.button(f"🗑️ حذف", key=f"del_{acc['id']}"):
                        success, message = delete_account(acc['id'])
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
        else:
            st.info("لا توجد حسابات. أضف حسابات جديدة من التبويب الثاني.")

    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>إضافة حساب جديد</h3>", unsafe_allow_html=True)
        account_options = get_account_options()
        
        selected_parent = st.selectbox("الحساب الأب", list(account_options.keys()))
        parent_id = account_options[selected_parent]

        col1, col2 = st.columns(2)
        code = col1.text_input("كود الحساب")
        name = col2.text_input("اسم الحساب")
        
        col3, col4 = st.columns(2)
        
        account_type = col3.selectbox(
            "تصنيف الحساب الرئيسي",
            ["", "Asset - أصل", "Liability - خصم", "Equity - حقوق ملكية", "Revenue - إيراد", "Expense - مصروف"],
            help="يحدد أين يظهر الحساب في القوائم المالية"
        )
        
        selected_func_label = col4.selectbox(
            "النوع الوظيفي للنظام (اختياري)",
            list(FUNCTIONAL_TYPES.keys()),
            help="إذا كان هذا الحساب مخصصاً لاستقبال فواتير المبيعات/المشتريات أو الصندوق تلقائياً اختر نوعه هنا"
        )
        
        # تحويل القيم المعروضة إلى القيمة التخزينية
        account_type_map = {
            "Asset - أصل": "Asset",
            "Liability - خصم": "Liability",
            "Equity - حقوق ملكية": "Equity",
            "Revenue - إيراد": "Revenue",
            "Expense - مصروف": "Expense"
        }
        selected_account_type = account_type_map.get(account_type)
        functional_type = FUNCTIONAL_TYPES.get(selected_func_label)

        if st.button("💾 حفظ الحساب"):
            if not code or not name:
                st.error("الكود والاسم مطلوبان")
            else:
                # ملاحظة: تم إرسال functional_type لدالة add_account
                success, error = add_account(code, name, parent_id, selected_account_type, functional_type=functional_type)
                if success:
                    st.success(f"تم إضافة الحساب {code} - {name} بنجاح!")
                    st.rerun()
                else:
                    st.error(error)
