# ui/inventory_adjustment_ui.py – واجهة التسويات المخزنية والجرد (تصميم زجاجي فخم + حماية من التكرار)
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from services.inventory_adjustment_service import (
    create_adjustments_table,
    get_products_for_adjustment,
    create_adjustment,
    get_adjustments
)

# ========== ألوان التصميم ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
GLASS_BG = "rgba(255, 255, 255, 0.08)"
GLASS_BORDER = "rgba(255, 255, 255, 0.15)"

def glass_card(content):
    """بطاقة زجاجية"""
    st.markdown(f"""
    <div style="background:{GLASS_BG}; backdrop-filter:blur(15px);
         border:1px solid {GLASS_BORDER}; border-radius:16px;
         padding:1.5rem; margin:0.8rem 0;
         box-shadow:0 8px 32px rgba(0,0,0,0.3); color:{T};">
         {content}
    </div>
    """, unsafe_allow_html=True)

def kpi_card(title, value, icon, color, subtitle=""):
    """بطاقة مؤشر"""
    st.markdown(f"""
    <div style="background:{GLASS_BG}; backdrop-filter:blur(12px);
         border:1px solid {GLASS_BORDER}; border-radius:14px;
         padding:1.2rem 1.5rem; text-align:center;
         box-shadow:0 4px 20px rgba(0,0,0,0.2);">
         <span style="font-size:2rem;">{icon}</span>
         <h3 style="color:{color}; margin:0.3rem 0; font-size:1.5rem;">{value}</h3>
         <p style="color:{S}; font-size:0.85rem; margin:0;">{title}</p>
         <small style="color:{S};">{subtitle}</small>
    </div>
    """, unsafe_allow_html=True)

def show():
    create_adjustments_table()
    
    # ========== هيدر ==========
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">📦 التسويات المخزنية</h1>
        <p style="color:{S}; font-size:1.2rem;">الجرد الفعلي واكتشاف العجز والفائض مع التكامل المحاسبي</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 تسجيل جرد", "📋 سجل التسويات", "📊 تحليل الانحرافات"])

    # ---------- تبويب تسجيل الجرد ----------
    with tab1:
        products = get_products_for_adjustment()
        if not products:
            st.info("لا توجد منتجات في المخزون")
        else:
            col_form, col_info = st.columns([2, 1])
            
            with col_form:
                st.markdown(f"<h3 style='color:{GR};'>تسجيل الجرد الفعلي</h3>", unsafe_allow_html=True)
                
                product_names = [f"{p['name']} (النظام: {p['quantity']})" for p in products]
                selected_idx = st.selectbox("اختر المنتج", range(len(product_names)), 
                                           format_func=lambda i: product_names[i],
                                           key="adj_product")
                product = products[selected_idx]
                
                with st.container(border=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**الكمية في النظام:** {product['quantity']}")
                        st.markdown(f"**سعر البيع:** {product['selling_price']}")
                    with col2:
                        st.markdown(f"**سعر الشراء:** {product['purchase_price']}")
                
                actual_qty = st.number_input("الكمية الفعلية (بعد الجرد)", 
                                             min_value=0.0, step=1.0,
                                             value=float(product['quantity']),
                                             key="actual_qty_input")
                
                difference = actual_qty - product['quantity']
                
                if difference > 0:
                    st.markdown(f"""
                    <div style="background:rgba(16,185,129,0.1); border:1px solid {GR}; 
                         border-radius:10px; padding:10px; text-align:center;">
                        <span style="color:{GR}; font-size:1.3rem; font-weight:700;">✅ فائض: +{difference:.2f} وحدة</span>
                    </div>
                    """, unsafe_allow_html=True)
                elif difference < 0:
                    st.markdown(f"""
                    <div style="background:rgba(239,68,68,0.1); border:1px solid {RD}; 
                         border-radius:10px; padding:10px; text-align:center;">
                        <span style="color:{RD}; font-size:1.3rem; font-weight:700;">⚠️ عجز: {difference:.2f} وحدة</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:rgba(59,130,246,0.1); border:1px solid {BL}; 
                         border-radius:10px; padding:10px; text-align:center;">
                        <span style="color:{BL}; font-size:1.3rem;">📊 الكمية متطابقة</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    unit_cost_input = st.number_input("تكلفة الوحدة (اختياري)", 
                                                      min_value=0.0, step=0.01,
                                                      value=0.0,
                                                      key="unit_cost_adj",
                                                      help="إذا تركت 0 سيحسبها النظام تلقائياً")
                with col_c2:
                    adj_date = st.date_input("تاريخ التسوية", value=date.today(), key="adj_date")
                
                reason = st.text_area("سبب التسوية", placeholder="مثال: جرد سنوي، تلف، سرقة...", key="adj_reason")
                reference = st.text_input("المرجع", placeholder="رقم محضر الجرد", key="adj_ref")
                
                if difference != 0:
                    total_cost = abs(difference) * (unit_cost_input if unit_cost_input > 0 else (product['purchase_price'] or product['selling_price']))
                    st.markdown(f"""
                    <div style="background:{GLASS_BG}; border-radius:8px; padding:10px; text-align:center; margin:10px 0;">
                        <span style="color:{OR}; font-weight:700;">التكلفة التقديرية: {total_cost:,.2f}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # ✅ حماية من التكرار
                    if "saving_adjustment" not in st.session_state:
                        st.session_state.saving_adjustment = False
                    
                    if st.button("💾 حفظ التسوية", type="primary", use_container_width=True, key="save_adj", disabled=st.session_state.saving_adjustment):
                        st.session_state.saving_adjustment = True
                        st.rerun()
                    
                    if st.session_state.saving_adjustment:
                        unit_cost = unit_cost_input if unit_cost_input > 0 else None
                        adj_id, err = create_adjustment(
                            product_id=product['id'],
                            expected_qty=product['quantity'],
                            actual_qty=actual_qty,
                            unit_cost=unit_cost,
                            reason=reason,
                            reference=reference,
                            created_by=st.session_state.user.get('username', 'admin'),
                            adjustment_date=adj_date.strftime("%Y-%m-%d")
                        )
                        if err:
                            st.error(f"فشل: {err}")
                        else:
                            st.success(f"تم تسجيل التسوية رقم {adj_id}")
                        st.session_state.saving_adjustment = False
                        st.rerun()
                else:
                    st.info("الكمية الفعلية تطابق المتوقعة، لا حاجة لتسوية")
            
            with col_info:
                st.markdown(f"<h4 style='color:{PR};'>📌 إرشادات</h4>", unsafe_allow_html=True)
                glass_card(f"""
                <ul style="color:{S}; font-size:0.9rem; line-height:1.8;">
                    <li>أدخل الكمية <b style="color:{GR};">الفعلية</b> من الجرد الميداني</li>
                    <li>النظام يقارنها تلقائياً بالكمية المسجلة</li>
                    <li><b style="color:{GR};">الفائض</b>: يضاف للمخزون وFIFO بقيد أرباح</li>
                    <li><b style="color:{RD};">العجز</b>: يخصم من المخزون وFIFO بقيد خسائر</li>
                    <li>اترك التكلفة فارغة ليحسبها النظام تلقائياً</li>
                </ul>
                """)

    # ---------- سجل التسويات ----------
    with tab2:
        st.markdown(f"<h3 style='color:{PR};\">📋 سجل التسويات المخزنية</h3>", unsafe_allow_html=True)
        adjustments = get_adjustments()
        if adjustments:
            df = pd.DataFrame(adjustments)
            df['النوع'] = df['difference'].apply(lambda x: '🟢 فائض' if x > 0 else '🔴 عجز')
            df['الفرق'] = df['difference'].apply(lambda x: f"+{x:.2f}" if x > 0 else f"{x:.2f}")
            
            df_display = df.rename(columns={
                'id': 'الرقم',
                'date': 'التاريخ',
                'product_name': 'المنتج',
                'expected_qty': 'المتوقعة',
                'actual_qty': 'الفعلية',
                'unit_cost': 'تكلفة الوحدة',
                'total_cost': 'الإجمالي',
                'reason': 'السبب',
                'reference': 'المرجع'
            })
            
            st.dataframe(df_display[['الرقم', 'التاريخ', 'النوع', 'المنتج', 'المتوقعة', 
                                     'الفعلية', 'الفرق', 'تكلفة الوحدة', 'الإجمالي', 'السبب', 'المرجع']],
                         use_container_width=True, hide_index=True,
                         column_config={
                             'الإجمالي': st.column_config.NumberColumn(format='%.2f')
                         })
            
            total_faed = df[df['difference'] > 0]['total_cost'].sum()
            total_ajz = df[abs(df['difference']) > 0][df['difference'] < 0]['total_cost'].sum()
            
            col_k1, col_k2, col_k3 = st.columns(3)
            with col_k1:
                kpi_card("إجمالي التسويات", str(len(adjustments)), "📋", BL)
            with col_k2:
                kpi_card("قيمة الفائض", f"{total_faed:,.2f}", "🟢", GR)
            with col_k3:
                kpi_card("قيمة العجز", f"{abs(total_ajz):,.2f}", "🔴", RD)
        else:
            glass_card("<p style='text-align:center; color:#888;'>لا توجد تسويات مسجلة بعد</p>")

    # ---------- تحليل الانحرافات ----------
    with tab3:
        st.markdown(f"<h3 style='color:{OR};\">📊 تحليل الانحرافات المخزنية</h3>", unsafe_allow_html=True)
        adjustments = get_adjustments()
        if adjustments:
            df = pd.DataFrame(adjustments)
            if not df.empty:
                col_ch1, col_ch2 = st.columns(2)
                
                with col_ch1:
                    df_chart = df.groupby('product_name')['total_cost'].sum().reset_index()
                    df_chart['type'] = df.groupby('product_name')['difference'].sum().apply(
                        lambda x: 'فائض' if x > 0 else 'عجز'
                    ).values
                    
                    fig = px.bar(df_chart, x='product_name', y='total_cost',
                                color='type',
                                color_discrete_map={'فائض': GR, 'عجز': RD},
                                title="قيمة الانحرافات حسب المنتج",
                                labels={'product_name': 'المنتج', 'total_cost': 'القيمة'})
                    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', 
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    font_color='white')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col_ch2:
                    pie_data = pd.DataFrame({
                        'النوع': ['فائض', 'عجز'],
                        'القيمة': [
                            df[df['difference'] > 0]['total_cost'].sum(),
                            abs(df[df['difference'] < 0]['total_cost'].sum())
                        ]
                    })
                    fig2 = px.pie(pie_data, names='النوع', values='القيمة',
                                 color='النوع',
                                 color_discrete_map={'فائض': GR, 'عجز': RD},
                                 title="توزيع الانحرافات",
                                 hole=0.5)
                    fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)',
                                     font_color='white')
                    st.plotly_chart(fig2, use_container_width=True)
        else:
            glass_card("<p style='text-align:center; color:#888;'>لا توجد بيانات كافية للتحليل</p>")
