# ui/chart_ui.py – واجهة شجرة الحسابات (تصميم زجاجي فخم + توضيح وجهة الحساب + اختيار التصنيف)
import streamlit as st
import pandas as pd
from services.chart_service import (
    create_accounts_table,
    add_account,
    get_accounts_tree,
    build_tree,
    get_account_options
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

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 شجرة الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إدارة الحسابات الهرمية للنظام المحاسبي</p>
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
            
            # 🆕 تحديد أين يظهر الحساب بناءً على تصنيفه
            def where_appears(acc_type):
                if acc_type in ("Asset", "Liability", "Equity"):
                    return "الميزانية العمومية"
                elif acc_type in ("Revenue", "Expense"):
                    return "قائمة الدخل"
                else:
                    return "غير محدد"
            
            df["يظهر في"] = df["account_type"].apply(where_appears)
            
            # إعادة ترتيب وتسمية الأعمدة للعرض
            df_display = df[["code", "display_name", "level", "is_debit", "يظهر في"]].rename(
                columns={
                    "display_name": "اسم الحساب",
                    "code": "الكود",
                    "level": "المستوى",
                    "is_debit": "طبيعة الحساب",
                    "يظهر في": "يظهر في"
                }
            )
            st.dataframe(df_display, use_container_width=True, hide_index=True)
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
        
        # 🆕 حقل اختيار تصنيف الحساب
        account_type = st.selectbox(
            "تصنيف الحساب (يحدد أين يظهر في القوائم المالية)",
            ["", "Asset - أصل", "Liability - خصم", "Equity - حقوق ملكية", "Revenue - إيراد", "Expense - مصروف"],
            help="اختر التصنيف المناسب. يحدد ما إذا كان الحساب يظهر في الميزانية العمومية أم قائمة الدخل"
        )
        
        # تحويل القيمة المعروضة إلى القيمة المخزنة
        account_type_map = {
            "Asset - أصل": "Asset",
            "Liability - خصم": "Liability",
            "Equity - حقوق ملكية": "Equity",
            "Revenue - إيراد": "Revenue",
            "Expense - مصروف": "Expense"
        }
        selected_account_type = account_type_map.get(account_type)

        if st.button("💾 حفظ الحساب"):
            if not code or not name:
                st.error("الكود والاسم مطلوبان")
            else:
                success, error = add_account(code, name, parent_id, selected_account_type)
                if success:
                    st.success(f"تم إضافة الحساب {code} - {name}")
                    st.rerun()
                else:
                    st.error(error)
