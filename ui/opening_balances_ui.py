# ui/opening_balances_ui.py – واجهة الأرصدة الافتتاحية (v2.0)
# ✅ عرض الإجمالي + كشف الفرق + منع الحفظ عند عدم التوازن
import streamlit as st
import pandas as pd
from datetime import date
from services.opening_balances_service import (
    get_accounts_for_opening,
    get_products_for_opening,
    create_opening_balances,
)


# ========== ألوان ==========
T = "#F8FAFC"
S = "#CBD5E1"
GR = "#10B981"
RD = "#EF4444"
PR = "#8B5CF6"
BL = "#3B82F6"
OR = "#F59E0B"


def _glass_card(content, color=BL):
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.08); border:1px solid {color};
         border-radius:14px; padding:1rem 1.5rem; margin:0.75rem 0;
         color:{T}; text-align:right;">
        {content}
    </div>
    """, unsafe_allow_html=True)


def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">📋 الأرصدة الافتتاحية</h1>
        <p style="color:{S}; font-size:1.2rem;">تسجيل أرصدة بداية المدة للحسابات والمخزون</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📊 أرصدة الحسابات", "📦 أرصدة المخزون"])

    # ============================================================
    # تبويب 1: أرصدة الحسابات
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{BL};'>أرصدة الحسابات الافتتاحية</h3>",
                    unsafe_allow_html=True)

        accounts = get_accounts_for_opening()
        if not accounts:
            st.warning("لا توجد حسابات في شجرة الحسابات. أضف حسابات أولاً.")
            account_balances = []
        else:
            df = pd.DataFrame(accounts)
            df['الرصيد مدين'] = 0.0
            df['الرصيد دائن'] = 0.0
            df_display = df[['code', 'name', 'الرصيد مدين', 'الرصيد دائن']]

            edited_df = st.data_editor(
                df_display,
                column_config={
                    "code": "الكود",
                    "name": "اسم الحساب",
                    "الرصيد مدين": st.column_config.NumberColumn(
                        "رصيد مدين", min_value=0.0, step=0.01, format="%.2f"
                    ),
                    "الرصيد دائن": st.column_config.NumberColumn(
                        "رصيد دائن", min_value=0.0, step=0.01, format="%.2f"
                    ),
                },
                use_container_width=True,
                hide_index=True,
                num_rows="fixed"
            )

            # ✅ استخراج الأرصدة
            account_balances = []
            total_dr = 0.0
            total_cr = 0.0

            for _, row in edited_df.iterrows():
                dr = float(row['الرصيد مدين'] or 0)
                cr = float(row['الرصيد دائن'] or 0)
                if dr > 0 or cr > 0:
                    account_balances.append({
                        'code': row['code'],
                        'name': row['name'],
                        'debit': dr,
                        'credit': cr,
                    })
                    total_dr += dr
                    total_cr += cr

            st.session_state['account_balances'] = account_balances

            # ✅ عرض الإجمالي
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("إجمالي المدين", f"{total_dr:,.2f}")
            col_b.metric("إجمالي الدائن", f"{total_cr:,.2f}")
            diff_acc = round(total_dr - total_cr, 2)

            if abs(diff_acc) < 0.01 and (total_dr > 0 or total_cr > 0):
                col_c.metric("الفرق", "✅ متوازن")
            elif total_dr > 0 or total_cr > 0:
                col_c.metric("الفرق", f"⚠️ {diff_acc:,.2f}")

    # ============================================================
    # تبويب 2: أرصدة المخزون
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{GR};'>أرصدة المخزون الافتتاحية</h3>",
                    unsafe_allow_html=True)

        products = get_products_for_opening()
        if not products:
            st.warning("لا توجد منتجات. أضف منتجات أولاً.")
            inventory_items = []
        else:
            df_prod = pd.DataFrame(products)
            df_prod['الكمية الافتتاحية'] = 0.0
            df_prod['تكلفة الوحدة'] = df_prod['purchase_price'].fillna(0.0)
            df_prod_display = df_prod[[
                'id', 'name', 'الكمية الافتتاحية', 'تكلفة الوحدة'
            ]]

            edited_prod_df = st.data_editor(
                df_prod_display,
                column_config={
                    "id": "الرقم",
                    "name": "اسم المنتج",
                    "الكمية الافتتاحية": st.column_config.NumberColumn(
                        "الكمية", min_value=0.0, step=1.0, format="%.2f"
                    ),
                    "تكلفة الوحدة": st.column_config.NumberColumn(
                        "تكلفة الوحدة", min_value=0.0, step=0.01, format="%.2f"
                    ),
                },
                use_container_width=True,
                hide_index=True,
                num_rows="fixed"
            )

            inventory_items = []
            total_inv_cost = 0.0

            for _, row in edited_prod_df.iterrows():
                qty = float(row['الكمية الافتتاحية'] or 0)
                if qty > 0:
                    cost = float(row['تكلفة الوحدة'] or 0)
                    inventory_items.append({
                        'product_id': int(row['id']),
                        'quantity': qty,
                        'unit_cost': cost,
                    })
                    total_inv_cost += qty * cost

            st.session_state['inventory_items'] = inventory_items

            st.metric("إجمالي قيمة المخزون", f"{total_inv_cost:,.2f}")

    # ============================================================
    # الحفظ
    # ============================================================
    st.markdown("---")
    entry_date = st.date_input("تاريخ الافتتاح", value=date.today())

    # ✅ عرض الملخص قبل الحفظ
    account_balances = st.session_state.get('account_balances', [])
    inventory_items = st.session_state.get('inventory_items', [])

    total_dr = sum(b['debit'] for b in account_balances)
    total_cr = sum(b['credit'] for b in account_balances)
    total_inv = sum(i['quantity'] * i['unit_cost'] for i in inventory_items)

    # المخزون مدين — يجب أن يُضاف للمقارنة
    total_dr_with_inv = total_dr + total_inv
    diff_final = round(total_dr_with_inv - total_cr, 2)

    _glass_card(f"""
        <div style="display:flex; justify-content:space-between;">
            <span><b>إجمالي المدين</b> (مع المخزون): {total_dr_with_inv:,.2f}</span>
            <span><b>إجمالي الدائن:</b> {total_cr:,.2f}</span>
            <span><b>الفرق:</b> 
                <span style="color:{'#10B981' if abs(diff_final) < 0.01 else '#EF4444'};">
                    {diff_final:,.2f}
                </span>
            </span>
        </div>
    """, color=GR if abs(diff_final) < 0.01 else OR)

    # ✅ حماية من التكرار
    if "saving_opening" not in st.session_state:
        st.session_state.saving_opening = False

    # ✅ لا يمكن الحفظ إذا لا يوجد بيانات
    has_data = bool(account_balances) or bool(inventory_items)
    can_save = (
        not st.session_state.saving_opening
        and has_data
    )

    if st.button(
        "💾 حفظ الأرصدة الافتتاحية",
        type="primary",
        use_container_width=True,
        disabled=not can_save,
        key="save_opening_btn"
    ):
        st.session_state.saving_opening = True
        st.rerun()

    if st.session_state.saving_opening:
        try:
            entry_id, err = create_opening_balances(
                account_balances,
                inventory_items,
                entry_date.strftime("%Y-%m-%d"),
                st.session_state.user.get('username', 'admin')
            )
            if err:
                st.error(f"❌ فشل في حفظ الأرصدة: {err}")
            else:
                st.success(f"✅ تم تسجيل الأرصدة الافتتاحية بقيد رقم {entry_id}")
                st.balloons()
        except Exception as e:
            st.error(f"❌ خطأ غير متوقع: {e}")
        finally:
            st.session_state.saving_opening = False
            st.rerun()
