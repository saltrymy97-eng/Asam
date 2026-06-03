# ui/opening_balances_ui.py – واجهة الأرصدة الافتتاحية (فخمة ومتكاملة)
import streamlit as st
import pandas as pd
from datetime import date
from services.opening_balances_service import (
    get_accounts_for_opening,
    get_products_for_opening,
    create_opening_balances
)

T = "#F8FAFC"
S = "#CBD5E1"
GR = "#10B981"
RD = "#EF4444"
PR = "#8B5CF6"
BL = "#3B82F6"

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">📋 الأرصدة الافتتاحية</h1>
        <p style="color:{S}; font-size:1.2rem;">تسجيل أرصدة بداية المدة للحسابات والمخزون</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📊 أرصدة الحسابات", "📦 أرصدة المخزون"])

    # ---------- تبويب الحسابات ----------
    with tab1:
        st.markdown(f"<h3 style='color:{BL};'>أرصدة الحسابات الافتتاحية</h3>", unsafe_allow_html=True)
        accounts = get_accounts_for_opening()
        if not accounts:
            st.warning("لا توجد حسابات في شجرة الحسابات. أضف حسابات أولاً.")
        else:
            # بناء جدول قابل للتعديل
            df = pd.DataFrame(accounts)
            df['الرصيد مدين'] = 0.0
            df['الرصيد دائن'] = 0.0
            df_display = df[['code', 'name', 'الرصيد مدين', 'الرصيد دائن']]
            
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "code": "الكود",
                    "name": "اسم الحساب",
                    "الرصيد مدين": st.column_config.NumberColumn("رصيد مدين", min_value=0, step=0.01),
                    "الرصيد دائن": st.column_config.NumberColumn("رصيد دائن", min_value=0, step=0.01)
                },
                use_container_width=True,
                hide_index=True,
                num_rows="fixed"
            )
            
            # تحويل البيانات المعدلة إلى قائمة قواميس
            account_balances = []
            for _, row in edited_df.iterrows():
                account_balances.append({
                    'code': row['code'],
                    'debit': float(row['الرصيد مدين']),
                    'credit': float(row['الرصيد دائن'])
                })
            
            st.session_state['account_balances'] = account_balances

    # ---------- تبويب المخزون ----------
    with tab2:
        st.markdown(f"<h3 style='color:{GR};'>أرصدة المخزون الافتتاحية</h3>", unsafe_allow_html=True)
        products = get_products_for_opening()
        if not products:
            st.warning("لا توجد منتجات. أضف منتجات أولاً.")
        else:
            df_prod = pd.DataFrame(products)
            df_prod['الكمية الافتتاحية'] = 0.0
            df_prod['تكلفة الوحدة'] = df_prod['purchase_price'].fillna(0.0)
            df_prod_display = df_prod[['id', 'name', 'الكمية الافتتاحية', 'تكلفة الوحدة']]
            
            edited_prod_df = st.data_editor(
                df_prod_display,
                column_config={
                    "id": "الرقم",
                    "name": "اسم المنتج",
                    "الكمية الافتتاحية": st.column_config.NumberColumn("الكمية", min_value=0, step=1.0),
                    "تكلفة الوحدة": st.column_config.NumberColumn("تكلفة الوحدة", min_value=0.0, step=0.01)
                },
                use_container_width=True,
                hide_index=True,
                num_rows="fixed"
            )
            
            inventory_items = []
            for _, row in edited_prod_df.iterrows():
                qty = float(row['الكمية الافتتاحية'])
                if qty > 0:
                    inventory_items.append({
                        'product_id': int(row['id']),
                        'quantity': qty,
                        'unit_cost': float(row['تكلفة الوحدة'])
                    })
            
            st.session_state['inventory_items'] = inventory_items

    # ---------- حفظ ----------
    st.markdown("---")
    entry_date = st.date_input("تاريخ الافتتاح", value=date.today())
    
    if st.button("💾 حفظ الأرصدة الافتتاحية", type="primary", use_container_width=True):
        account_balances = st.session_state.get('account_balances', [])
        inventory_items = st.session_state.get('inventory_items', [])
        
        if not account_balances and not inventory_items:
            st.error("يجب إدخال رصيد واحد على الأقل")
        else:
            entry_id, err = create_opening_balances(
                account_balances,
                inventory_items,
                entry_date.strftime("%Y-%m-%d"),
                st.session_state.user.get('username', 'admin')
            )
            if err:
                st.error(f"فشل في حفظ الأرصدة: {err}")
            else:
                st.success(f"تم تسجيل الأرصدة الافتتاحية بقيد رقم {entry_id}")
                st.balloons()
