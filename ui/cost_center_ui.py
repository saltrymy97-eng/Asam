import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from services import cost_center_service as ccs

# ================== CSS زجاجي ==================
def glass_style():
    st.markdown("""
    <style>
    .glass-container {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 25px;
        padding: 30px;
        margin-bottom: 25px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    }
    .glass-header {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(59, 130, 246, 0.3));
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        margin-bottom: 30px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 18px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid rgba(255,255,255,0.12);
        transition: all 0.3s ease;
    }
    .glass-card:hover {
        background: rgba(255, 255, 255, 0.12);
        transform: translateY(-3px);
    }
    .kpi-number {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #a78bfa, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    div[data-testid="stTabs"] button {
        background: rgba(255,255,255,0.05) !important;
        backdrop-filter: blur(10px);
        border-radius: 15px 15px 0 0 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: #ddd !important;
        font-weight: 500;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: linear-gradient(135deg, rgba(139,92,246,0.3), rgba(59,130,246,0.3)) !important;
        border-bottom: 2px solid #a78bfa !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

def show():
    glass_style()
    
    # ================ الرأس ================
    st.markdown("""
    <div class="glass-header">
        <h1 style="color: white; font-size: 2.8rem; margin: 0;">🏢 مراكز التكلفة</h1>
        <p style="color: #ccc; font-size: 1.1rem; margin-top: 5px;">إدارة متطورة لتحليل الأداء المالي حسب القطاعات</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ================ التبويبات ================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 إدارة المراكز",
        "📊 توزيع المعاملات",
        "📈 تحليل وتقارير",
        "💰 الموازنات التقديرية"
    ])
    
    # ------------------------ تبويب 1: إدارة المراكز ------------------------
    with tab1:
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            with st.container():
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                st.subheader("➕ إضافة مركز جديد")
                with st.form("add_cc_form"):
                    code = st.text_input("رمز المركز", placeholder="مثال: SALES-NORTH")
                    name = st.text_input("اسم المركز", placeholder="مبيعات المنطقة الشمالية")
                    # اختيار الأب
                    all_centers = ccs.get_all_cost_centers(active_only=True)
                    parent_map = {0: "لا يوجد (مركز رئيسي)"}
                    for c in all_centers:
                        parent_map[c['id']] = f"{c['code']} - {c['name']}"
                    parent_id = st.selectbox("المركز الأب", options=list(parent_map.keys()),
                                             format_func=lambda x: parent_map[x])
                    parent_id = None if parent_id == 0 else parent_id
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        submitted = st.form_submit_button("✅ إضافة", use_container_width=True)
                    if submitted:
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
        
        with col_right:
            with st.container():
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
        
        # قائمة المراكز مع إجراءات
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📋 جميع المراكز")
        centers = ccs.get_all_cost_centers(active_only=False)
        if centers:
            df = pd.DataFrame(centers)
            df['الحالة'] = df['is_active'].map({1: '🟢 نشط', 0: '🔴 غير نشط'})
            df_display = df[['id', 'code', 'name', 'الحالة']]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # تعديل سريع
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
    
    # ------------------------ تبويب 2: توزيع المعاملات ------------------------
    with tab2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📌 توزيع سطر قيد على مراكز التكلفة")
        st.markdown("هذه الواجهة ستُستخدم داخل وحدة الحسابات عند إنشاء القيد، ولكن يمكنك هنا تجربة التوزيع يدوياً.")
        
        # جلب قيود حديثة لاختيار سطر
        import database
        conn = database.get_connection()
        journal_entries = conn.execute("""
            SELECT id, entry_date, description FROM journal_entries ORDER BY id DESC LIMIT 20
        """).fetchall()
        conn.close()
        
        if journal_entries:
            entry_options = {e['id']: f"{e['id']} - {e['entry_date']} - {e['description']}" for e in journal_entries}
            selected_entry_id = st.selectbox("اختر القيد", options=list(entry_options.keys()),
                                             format_func=lambda x: entry_options[x])
            # جلب سطور القيد
            conn = database.get_connection()
            lines = conn.execute("""
                SELECT jl.id, a.name as account_name, jl.debit, jl.credit, jl.description
                FROM journal_lines jl JOIN accounts a ON jl.account_id = a.id
                WHERE jl.journal_entry_id = ?
            """, (selected_entry_id,)).fetchall()
            conn.close()
            
            if lines:
                line_options = {l['id']: f"{l['account_name']} (مدين: {l['debit']}, دائن: {l['credit']})" for l in lines}
                selected_line_id = st.selectbox("اختر السطر", options=list(line_options.keys()),
                                                format_func=lambda x: line_options[x])
                line_amount = next(l['debit'] if l['debit'] else l['credit'] for l in lines if l['id']==selected_line_id)
                st.write(f"المبلغ الإجمالي للسطر: **{line_amount:,.2f}**")
                
                # توزيع
                with st.form("alloc_form"):
                    st.markdown("#### حدد المراكز والنسب")
                    centers_list = ccs.get_all_cost_centers(active_only=True)
                    alloc_data = []
                    # نسمح حتى 5 مراكز
                    for i in range(5):
                        cols = st.columns([3,2,1])
                        with cols[0]:
                            center_opt = {c['id']: f"{c['code']} - {c['name']}" for c in centers_list}
                            center_opt[0] = "-- لا شيء --"
                            center = st.selectbox(f"المركز {i+1}", options=list(center_opt.keys()),
                                                  format_func=lambda x: center_opt[x], key=f"cc_{i}")
                        with cols[1]:
                            amount = st.number_input(f"المبلغ {i+1}", min_value=0.0, value=0.0, step=100.0, key=f"amt_{i}")
                        with cols[2]:
                            perc = st.number_input(f"%{i+1}", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key=f"perc_{i}")
                        if center != 0 and amount > 0:
                            alloc_data.append({'cost_center_id': center, 'amount': amount, 'percentage': perc})
                    
                    total_alloc = sum(a['amount'] for a in alloc_data)
                    if total_alloc > 0:
                        st.write(f"مجموع التوزيعات: {total_alloc:,.2f} (المتبقي: {line_amount - total_alloc:,.2f})")
                    if st.form_submit_button("💾 حفظ التوزيعات"):
                        if abs(total_alloc - line_amount) > 0.01:
                            st.error("مجموع التوزيعات يجب أن يساوي مبلغ السطر!")
                        else:
                            try:
                                ccs.allocate_journal_line(selected_line_id, alloc_data)
                                st.success("تم توزيع السطر على مراكز التكلفة بنجاح")
                            except Exception as e:
                                st.error(str(e))
            else:
                st.warning("القيد لا يحتوي على سطور")
        else:
            st.info("لا توجد قيود مسجلة")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ------------------------ تبويب 3: تحليل وتقارير ------------------------
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
                
                # بطاقات KPI
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
                
                # رسم بياني
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
    
    # ------------------------ تبويب 4: الموازنات التقديرية ------------------------
    with tab4:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("💰 الموازنة التقديرية للمراكز")
        centers = ccs.get_all_cost_centers(active_only=True)
        if centers:
            center_id = st.selectbox("المركز", options=[c['id'] for c in centers],
                                     format_func=lambda x: next(c['name'] for c in centers if c['id']==x))
            fiscal_year = st.number_input("السنة المالية", min_value=2020, max_value=2030, value=2025)
            if st.button("🔍 عرض الموازنة والانحرافات", use_container_width=True):
                data = ccs.get_budget_variance(center_id, fiscal_year)
                if data:
                    df = pd.DataFrame(data)
                    df.columns = ['الحساب', 'الموازنة', 'الفعلي']
                    df['الانحراف'] = df['الفعلي'] - df['الموازنة']
                    st.dataframe(df.style.applymap(lambda x: 'color: red' if x < 0 else 'color: green', subset=['الانحراف']), use_container_width=True)
                    
                    # رسم بياني
                    fig = px.bar(df, x='الحساب', y=['الموازنة', 'الفعلي'], barmode='group',
                                 color_discrete_map={'الموازنة': '#a78bfa', 'الفعلي': '#60a5fa'})
                    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("لا توجد موازنات مسجلة لهذا المركز. أضف موازنة أدناه.")
            
            st.markdown("---")
            with st.form("budget_form"):
                st.subheader("➕ إضافة/تحديث موازنة")
                # جلب الحسابات
                conn = database.get_connection()
                accounts = conn.execute("SELECT id, name FROM accounts ORDER BY name").fetchall()
                conn.close()
                account_id = st.selectbox("الحساب", options=[a['id'] for a in accounts],
                                          format_func=lambda x: next(a['name'] for a in accounts if a['id']==x))
                amount = st.number_input("المبلغ المخطط", min_value=0.0, step=100.0)
                if st.form_submit_button("💾 حفظ الموازنة"):
                    ccs.set_budget(center_id, account_id, fiscal_year, amount)
                    st.success("تم حفظ الموازنة")
                    st.rerun()
        else:
            st.info("لا توجد مراكز")
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    show()
