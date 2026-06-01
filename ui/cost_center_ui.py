import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from services import cost_center_service as ccs
from services import closing_service
import database

# ================== تصميم زجاجي مبهر (بدون مستطيلات غامضة) ==================
def apply_glass_design():
    st.markdown("""
    <style>
    /* إخفاء أي عنصر فارغ داخل الأعمدة */
    div[data-testid="stVerticalBlock"] > div:empty,
    div[data-testid="stHorizontalBlock"] > div:empty {
        display: none !important;
    }
    /* إزالة حدود النماذج الافتراضية */
    div[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    /* البطاقة الزجاجية الأساسية */
    .glass-card {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: all 0.3s ease;
    }
    .glass-card:hover {
        background: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.25);
        transform: translateY(-3px);
    }
    /* رأس الصفحة الزجاجي */
    .glass-header {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(59, 130, 246, 0.3));
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 24px;
        padding: 28px;
        text-align: center;
        margin-bottom: 32px;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
    }
    /* أرقام KPI */
    .kpi-number {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #a78bfa, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 8px 0;
    }
    /* تبويبات محسنة */
    div[data-testid="stTabs"] button {
        background: rgba(255, 255, 255, 0.06) !important;
        backdrop-filter: blur(12px);
        border-radius: 14px 14px 0 0 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        color: #ddd !important;
        font-weight: 500;
        padding: 10px 22px !important;
        margin: 0 5px !important;
        transition: all 0.2s ease;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(59, 130, 246, 0.35)) !important;
        border-bottom: 2px solid #a78bfa !important;
        color: #fff !important;
        font-weight: 600;
    }
    /* حقول الإدخال الزجاجية */
    div[data-baseweb="input"] {
        background: rgba(255, 255, 255, 0.06) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
        transition: all 0.2s ease;
    }
    div[data-baseweb="input"] input {
        background: transparent !important;
        color: #fff !important;
        padding: 12px 14px !important;
    }
    div[data-baseweb="select"] {
        background: rgba(255, 255, 255, 0.06) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
    }
    /* أزرار زجاجية */
    button {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: #fff !important;
        border-radius: 12px !important;
        transition: all 0.3s ease;
    }
    button:hover {
        background: rgba(139, 92, 246, 0.35) !important;
        border-color: #a78bfa !important;
    }
    </style>
    """, unsafe_allow_html=True)

def show():
    apply_glass_design()
    
    # ========== الرأس ==========
    st.markdown("""
    <div class="glass-header">
        <h1 style="color: #fff; font-size: 3rem; margin: 0;">:material/account_balance: مراكز التكلفة</h1>
        <p style="color: #ccc; font-size: 1.2rem; margin-top: 8px;">إدارة متطورة لتحليل الأداء المالي حسب القطاعات</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ========== التبويبات ==========
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        ":material/edit_note: إدارة المراكز",
        ":material/account_tree: توزيع المعاملات",
        ":material/analytics: تحليل وتقارير",
        ":material/request_quote: الموازنات",
        ":material/lock: إقفال المراكز"
    ])
    
    # ---------- تبويب 1: إدارة ----------
    with tab1:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.subheader("➕ إضافة مركز جديد")
            with st.form("add_cc_form"):
                code = st.text_input("رمز المركز", placeholder="مثال: SALES-NORTH")
                name = st.text_input("اسم المركز", placeholder="مبيعات المنطقة الشمالية")
                all_centers = ccs.get_all_cost_centers(active_only=True)
                parent_map = {0: "لا يوجد (مركز رئيسي)"}
                for c in all_centers:
                    parent_map[c['id']] = f"{c['code']} - {c['name']}"
                parent_id = st.selectbox("المركز الأب", options=list(parent_map.keys()),
                                         format_func=lambda x: parent_map[x])
                parent_id = None if parent_id == 0 else parent_id
                
                if st.form_submit_button("✅ إضافة"):
                    if not code or not name:
                        st.error("الرجاء إدخال الرمز والاسم")
                    else:
                        try:
                            ccs.create_cost_center(code, name, parent_id)
                            st.success("تمت الإضافة بنجاح")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.subheader("📌 الشجرة التنظيمية")
            tree = ccs.get_cost_center_tree()
            def render_tree(nodes, indent=0):
                for node in nodes:
                    icon = "📁" if node['children'] else "📄"
                    active_badge = "🟢" if node['is_active'] else "🔴"
                    line = "&nbsp;&nbsp;&nbsp;&nbsp;" * indent + f"{icon} {active_badge} {node['code']} - {node['name']}"
                    st.markdown(f"<div style='padding:4px 0; color:#eee;'>{line}</div>", unsafe_allow_html=True)
                    if node['children']:
                        render_tree(node['children'], indent+1)
            if not tree:
                st.info("لا توجد مراكز تكلفة حتى الآن")
            else:
                render_tree(tree)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # قائمة المراكز
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📋 جميع المراكز")
        centers = ccs.get_all_cost_centers(active_only=False)
        if centers:
            df = pd.DataFrame(centers)
            df['الحالة'] = df['is_active'].map({1: '🟢 نشط', 0: '🔴 غير نشط'})
            st.dataframe(df[['id', 'code', 'name', 'الحالة']], use_container_width=True, hide_index=True)
            
            with st.expander("✏️ تعديل مركز"):
                edit_id = st.selectbox("اختر المركز للتعديل", options=df['id'].tolist(),
                                       format_func=lambda x: df[df['id']==x]['code'].values[0])
                selected = df[df['id']==edit_id].iloc[0]
                new_name = st.text_input("الاسم الجديد", value=selected['name'])
                new_code = st.text_input("الرمز الجديد", value=selected['code'])
                new_active = st.checkbox("نشط", value=bool(selected['is_active']))
                if st.button("💾 حفظ التعديلات"):
                    ccs.update_cost_center(edit_id, code=new_code, name=new_name, is_active=1 if new_active else 0)
                    st.success("تم التحديث")
                    st.rerun()
        else:
            st.info("لا توجد بيانات")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ---------- تبويب 2: توزيع ----------
    with tab2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📌 توزيع سطر قيد على مراكز التكلفة")
        
        conn = database.get_connection()
        entries = conn.execute(
            "SELECT id, date, description FROM journal_entries ORDER BY id DESC LIMIT 20"
        ).fetchall()
        conn.close()
        
        if not entries:
            st.info("لا توجد قيود مسجلة")
            st.stop()
        
        entry_map = {e['id']: f"{e['id']} - {e['date']} - {e['description']}" for e in entries}
        selected_entry = st.selectbox("اختر القيد", options=list(entry_map.keys()),
                                      format_func=lambda x: entry_map[x], key="dist_entry")
        
        conn = database.get_connection()
        lines = conn.execute(
            "SELECT id, account_name, debit, credit FROM journal_lines WHERE entry_id = ?",
            (selected_entry,)
        ).fetchall()
        conn.close()
        
        if not lines:
            st.warning("القيد لا يحتوي على سطور")
            st.stop()
        
        line_options = {l['id']: f"{l['account_name']} (مدين: {l['debit']:,.2f}, دائن: {l['credit']:,.2f})" for l in lines}
        selected_line_id = st.selectbox("اختر السطر", options=list(line_options.keys()),
                                        format_func=lambda x: line_options[x], key="dist_line")
        
        selected_line = next(l for l in lines if l['id'] == selected_line_id)
        line_amount = selected_line['debit'] if selected_line['debit'] > 0 else selected_line['credit']
        st.write(f"المبلغ الإجمالي للسطر: **{line_amount:,.2f}**")
        
        centers_list = ccs.get_all_cost_centers(active_only=True)
        if not centers_list:
            st.warning("لا توجد مراكز تكلفة نشطة")
            st.stop()
        
        if 'alloc_rows' not in st.session_state:
            st.session_state.alloc_rows = 1
        
        center_map = {c['id']: f"{c['code']} - {c['name']}" for c in centers_list}
        alloc_data = []
        remaining = line_amount
        
        for i in range(st.session_state.alloc_rows):
            cols = st.columns([3, 2, 1, 1])
            with cols[0]:
                center = st.selectbox(
                    f"المركز {i+1}",
                    options=["-- اختر مركز --"] + list(center_map.keys()),
                    format_func=lambda x: center_map.get(x, x) if x != "-- اختر مركز --" else x,
                    key=f"cc_{i}"
                )
            with cols[1]:
                amount = st.number_input(
                    f"المبلغ {i+1}",
                    min_value=0.0,
                    max_value=float(remaining),
                    step=0.01,
                    key=f"amt_{i}"
                )
            with cols[2]:
                perc = st.number_input(
                    f"% {i+1}",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    key=f"perc_{i}"
                )
            with cols[3]:
                if i > 0 and st.button("🗑️", key=f"del_{i}"):
                    st.session_state.alloc_rows = max(1, st.session_state.alloc_rows - 1)
                    st.rerun()
            
            if center != "-- اختر مركز --" and amount > 0:
                alloc_data.append({
                    'cost_center_id': center,
                    'amount': amount,
                    'percentage': perc
                })
                remaining -= amount
        
        total_alloc = sum(a['amount'] for a in alloc_data)
        if total_alloc > 0:
            diff = line_amount - total_alloc
            if abs(diff) < 0.01:
                st.success("المبلغ موزع بالكامل ✅")
            else:
                st.warning(f"المتبقي: {diff:,.2f}")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("➕ إضافة مركز توزيع آخر", use_container_width=True):
                st.session_state.alloc_rows += 1
                st.rerun()
        with col_btn2:
            if st.button("💾 حفظ التوزيعات", type="primary", use_container_width=True):
                if abs(total_alloc - line_amount) > 0.01:
                    st.error("يجب أن يساوي مجموع التوزيعات المبلغ الأصلي")
                elif not alloc_data:
                    st.error("لم يتم إدخال أي توزيع")
                else:
                    try:
                        ccs.allocate_journal_line(selected_line_id, alloc_data)
                        st.success("تم حفظ التوزيعات بنجاح")
                    except Exception as e:
                        st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ---------- تبويب 3: تحليل ----------
    with tab3:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📊 تحليل الأداء حسب المركز")
        centers = ccs.get_all_cost_centers(active_only=True)
        if centers:
            center_choice = st.selectbox("اختر المركز", options=[c['id'] for c in centers],
                                          format_func=lambda x: next(c['name'] for c in centers if c['id']==x))
            from_date = st.date_input("من تاريخ")
            to_date = st.date_input("إلى تاريخ")
            
            if st.button("📈 عرض التحليل", use_container_width=True):
                balance = ccs.get_cost_center_balance(center_choice, from_date, to_date)
                income_stmt = ccs.get_cost_center_income_statement(center_choice, from_date, to_date)
                
                kpi1, kpi2, kpi3 = st.columns(3)
                with kpi1:
                    st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
                    st.markdown(f"<span class='kpi-number'>{balance['net']:,.2f}</span>", unsafe_allow_html=True)
                    st.caption("صافي التدفق")
                    st.markdown('</div>', unsafe_allow_html=True)
                with kpi2:
                    st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
                    st.markdown(f"<span class='kpi-number'>{income_stmt['income']:,.2f}</span>", unsafe_allow_html=True)
                    st.caption("الإيرادات")
                    st.markdown('</div>', unsafe_allow_html=True)
                with kpi3:
                    st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
                    st.markdown(f"<span class='kpi-number'>{income_stmt['expenses']:,.2f}</span>", unsafe_allow_html=True)
                    st.caption("المصروفات")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                fig = go.Figure(data=[
                    go.Bar(name='الإيرادات', x=['الإيرادات'], y=[income_stmt['income']], marker_color='#a78bfa'),
                    go.Bar(name='المصروفات', x=['المصروفات'], y=[income_stmt['expenses']], marker_color='#60a5fa')
                ])
                fig.update_layout(title="الإيرادات مقابل المصروفات", paper_bgcolor='rgba(0,0,0,0)',
                                  plot_bgcolor='rgba(0,0,0,0)', font_color='white')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد مراكز")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ---------- تبويب 4: موازنات ----------
    with tab4:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("💰 الموازنة التقديرية للمراكز")
        centers = ccs.get_all_cost_centers(active_only=True)
        if centers:
            center_id = st.selectbox("المركز", options=[c['id'] for c in centers],
                                     format_func=lambda x: next(c['name'] for c in centers if c['id']==x),
                                     key="budget_center")
            fiscal_year = st.number_input("السنة المالية", min_value=2020, max_value=2030, value=2025, key="budget_year")
            if st.button("🔍 عرض الموازنة والانحرافات", use_container_width=True):
                data = ccs.get_budget_variance(center_id, fiscal_year)
                if data and data.get('details'):
                    df = pd.DataFrame(data['details'])
                    df_display = df[['account_name', 'budget', 'actual', 'variance', 'variance_pct']]
                    df_display.columns = ['الحساب', 'الموازنة', 'الفعلي', 'الانحراف', 'نسبة الانحراف %']
                    st.dataframe(df_display.style.format({
                        'الموازنة': '{:,.2f}',
                        'الفعلي': '{:,.2f}',
                        'الانحراف': '{:,.2f}',
                        'نسبة الانحراف %': '{:.1f}%'
                    }), use_container_width=True)
                    
                    fig = px.bar(df, x='account_name', y=['budget', 'actual'], barmode='group',
                                 color_discrete_map={'budget': '#a78bfa', 'actual': '#60a5fa'},
                                 labels={'value': 'المبلغ', 'variable': 'النوع'})
                    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("لا توجد موازنات مسجلة لهذا المركز. أضف موازنة أدناه.")
            
            st.markdown("---")
            with st.form("budget_form"):
                st.subheader("➕ إضافة/تحديث موازنة")
                conn = database.get_connection()
                accounts = conn.execute("SELECT id, name FROM accounts ORDER BY name").fetchall()
                conn.close()
                account_id = st.selectbox("الحساب", options=[a['id'] for a in accounts],
                                          format_func=lambda x: next(a['name'] for a in accounts if a['id']==x),
                                          key="budget_account")
                amount = st.number_input("المبلغ المخطط", min_value=0.0, step=100.0, key="budget_amount")
                if st.form_submit_button("💾 حفظ الموازنة"):
                    ccs.set_budget(center_id, account_id, fiscal_year, amount)
                    st.success("تم حفظ الموازنة")
                    st.rerun()
        else:
            st.info("لا توجد مراكز")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ---------- تبويب 5: إقفال ----------
    with tab5:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("🔒 إقفال مركز تكلفة لسنة مالية")
        st.markdown("""
        هذه العملية تنشئ قيد إغلاق لمركز التكلفة المحدد، 
        حيث يتم تصفير أرصدة الإيرادات والمصروفات المرتبطة به 
        وتوجيه صافي الدخل إلى حساب الأرباح المحتجزة.
        """)
        
        centers = ccs.get_all_cost_centers(active_only=True)
        if not centers:
            st.info("لا توجد مراكز تكلفة نشطة")
        else:
            center_options = {c['id']: f"{c['code']} - {c['name']}" for c in centers}
            closing_center_id = st.selectbox(
                "اختر المركز لإقفاله",
                options=list(center_options.keys()),
                format_func=lambda x: center_options[x],
                key="closing_center"
            )
            closing_year = st.number_input("السنة المالية للإقفال", min_value=2020, max_value=2030, value=2025, key="closing_year")
            retained_earnings = st.text_input("كود حساب الأرباح المحتجزة", value="310000")
            
            if st.button("🔒 تنفيذ إقفال المركز", type="primary", use_container_width=True):
                with st.spinner("جارٍ إنشاء قيد الإقفال..."):
                    success, net_income, error = closing_service.create_cost_center_closing_entry(
                        year=closing_year,
                        cost_center_id=closing_center_id,
                        retained_earnings_code=retained_earnings
                    )
                    
                if success:
                    st.success(f"""
                    ✅ تم إقفال المركز بنجاح!
                    
                    **صافي الدخل:** {net_income:,.2f}
                    **السنة المالية:** {closing_year}
                    
                    تم إنشاء قيد إغلاق خاص بالمركز وتم توزيع جميع أسطره على المركز المحدد.
                    """)
                    st.balloons()
                else:
                    st.error(f"❌ فشل الإقفال: {error}")
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    show()
