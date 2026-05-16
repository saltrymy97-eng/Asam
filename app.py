import streamlit as st
from database import init_db, get_all_products, get_all_customers, get_all_suppliers, get_low_stock, get_sales_summary
from database import add_product, delete_product, update_stock
from database import add_customer, get_customer_statement, receive_payment
from database import add_supplier, add_purchase
from database import add_sale_with_customer
from database import get_accounts_tree, get_account_balance, get_all_journal_entries
from database import get_vat_settings, update_vat_settings
from database import get_all_sales_invoices, process_return
from auth import authenticate

init_db()

st.set_page_config(page_title="المتكامل - نظام ERP", page_icon="🎭", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
    html, body, .stApp { font-family: 'Cairo', sans-serif; background: linear-gradient(135deg, #f5f7fc 0%, #eef2f7 100%); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); border-radius: 0 30px 30px 0; }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stSelectbox label { color: #f1f5f9 !important; }
    [data-testid="stSidebar"] .stSelectbox > div > div { background-color: #334155; border-radius: 30px; color: white; }
    .metric-card { background: white; border-radius: 28px; padding: 25px 15px; text-align: center; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); transition: transform 0.25s ease; border: 1px solid rgba(106, 13, 173, 0.1); }
    .metric-card:hover { transform: translateY(-6px); box-shadow: 0 20px 35px -10px rgba(106, 13, 173, 0.2); border-color: #8b5cf6; }
    .metric-card h3 { font-size: 2.3rem; font-weight: 800; margin: 12px 0; background: linear-gradient(135deg, #6a0dad, #8b5cf6); background-clip: text; -webkit-background-clip: text; color: transparent; }
    .metric-card p { font-size: 1rem; font-weight: 600; color: #334155; margin: 0; }
    .stButton > button { background: linear-gradient(135deg, #6a0dad, #8b5cf6); color: white; border-radius: 40px; border: none; padding: 10px 24px; font-weight: 600; transition: all 0.2s ease; width: 100%; }
    .stButton > button:hover { transform: scale(1.02); box-shadow: 0 8px 20px rgba(106, 13, 173, 0.4); }
    .dataframe { border-radius: 20px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .dataframe th { background: linear-gradient(135deg, #6a0dad, #8b5cf6); color: white; padding: 12px; }
    .stTabs [data-baseweb="tab"] { background: white; border-radius: 40px; padding: 8px 28px; font-weight: 600; color: #334155; border: 1px solid #e2e8f0; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #6a0dad, #8b5cf6); color: white; border: none; }
    .section-title { font-size: 1.8rem; font-weight: 700; margin-bottom: 30px; border-right: 5px solid #6a0dad; padding-right: 20px; color: #1e293b; display: inline-block; }
    .footer { text-align: center; margin-top: 55px; padding: 20px; background: white; border-radius: 50px; color: #64748b; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.markdown("<div style='text-align: center; margin-top: 15vh;'><h1>🎭 المتكامل</h1><p style='margin-bottom: 30px;'>نظام ERP متكامل</p></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.container():
            st.markdown("<div style='background: white; padding: 30px; border-radius: 30px; box-shadow: 0 8px 25px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            username = st.text_input("👤 اسم المستخدم")
            password = st.text_input("🔒 كلمة المرور", type="password")
            if st.button("🚪 دخول", use_container_width=True):
                role = authenticate(username, password)
                if role:
                    st.session_state.authenticated = True
                    st.session_state.role = role
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ بيانات غير صحيحة")
            st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

with st.sidebar:
    st.markdown("<div style='text-align: center; margin-top: 20px;'><h2 style='color: white;'>🎭 المتكامل</h2></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align: center; color: #a5b4fc; margin-bottom: 20px;'>👋 مرحباً {st.session_state.username}</div>", unsafe_allow_html=True)
    st.markdown("---")
    
    menu_options = [
        "🏠 لوحة التحكم",
        "📦 المنتجات",
        "🛒 الكاشير",
        "👥 العملاء",
        "📦 الموردين",
        "📊 المحاسبة",
        "💰 الضريبة (VAT)",
        "🏭 الأصول الثابتة",
        "🏚️ المستودعات",
        "👨‍💼 الموارد البشرية",
        "🏭 الإنتاج (BOM)",
        "📈 التقارير المتقدمة",
        "🔄 مرتجعات المبيعات",
        "🛠️ الأدوات المتقدمة"
    ]
    
    if st.session_state.role == 'cashier':
        allowed = ["🏠 لوحة التحكم", "📦 المنتجات", "🛒 الكاشير", "📈 التقارير المتقدمة", "🔄 مرتجعات المبيعات"]
        menu_options = [m for m in menu_options if m in allowed]
    elif st.session_state.role == 'accountant':
        allowed = ["🏠 لوحة التحكم", "👥 العملاء", "📦 الموردين", "📊 المحاسبة", "💰 الضريبة (VAT)", "📈 التقارير المتقدمة"]
        menu_options = [m for m in menu_options if m in allowed]
    
    menu = st.radio("📌 القائمة الرئيسية", menu_options, label_visibility="collapsed")
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.caption("© 2025 - جميع الحقوق محفوظة")

# ============================== لوحة التحكم ==============================
if menu == "🏠 لوحة التحكم":
    st.markdown("<div class='section-title'>🏠 لوحة القيادة</div>", unsafe_allow_html=True)
    products = get_all_products()
    sales_sum = get_sales_summary()
    low_stock = get_low_stock(5)
    customers = get_all_customers()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"<div class='metric-card'><p>📦 المنتجات</p><h3>{len(products)}</h3></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><p>💰 الإيرادات</p><h3>{sales_sum['total_revenue']:,.0f}</h3></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><p>⚠️ مخزون منخفض</p><h3>{len(low_stock)}</h3></div>", unsafe_allow_html=True)
    with col4: st.markdown(f"<div class='metric-card'><p>👥 العملاء</p><h3>{len(customers)}</h3></div>", unsafe_allow_html=True)
    
    if low_stock:
        st.warning("⚠️ المنتجات منخفضة المخزون (≤5): " + ", ".join([p['name'] for p in low_stock]))
    else:
        st.success("✅ جميع المنتجات بمخزون جيد")

# ============================== المنتجات ==============================
elif menu == "📦 المنتجات":
    st.markdown("<div class='section-title'>📦 إدارة المنتجات</div>", unsafe_allow_html=True)
    with st.expander("➕ إضافة منتج جديد", expanded=False):
        with st.form("add_prod"):
            name = st.text_input("اسم المنتج")
            price = st.number_input("السعر", min_value=0.0, step=1.0)
            stock = st.number_input("المخزون الأولي", min_value=0, step=1)
            vat = st.number_input("نسبة الضريبة (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0)
            if st.form_submit_button("إضافة"):
                if name.strip():
                    add_product(name, price, stock, vat/100)
                    st.success(f"تم إضافة {name}")
                    st.rerun()
                else:
                    st.error("الاسم مطلوب")
    products = get_all_products()
    if products:
        for p in products:
            cols = st.columns([3,1,1,1])
            cols[0].write(f"**{p['name']}** - السعر: {p['price']:.2f} - المخزون: {p['stock']} - ضريبة: {p['vat_rate']*100:.0f}%")
            if cols[1].button("تعديل المخزون", key=f"stock_{p['id']}"):
                st.session_state.stock_prod = p
            if cols[2].button("حذف", key=f"del_{p['id']}"):
                delete_product(p['id'])
                st.rerun()
            if cols[3].button("تعديل السعر", key=f"edit_{p['id']}"):
                st.session_state.edit_prod = p
        if 'stock_prod' in st.session_state:
            p = st.session_state.stock_prod
            with st.form("up_stock"):
                change = st.number_input(f"تغيير مخزون {p['name']} (موجب للإضافة، سالب للسحب)", step=1)
                notes = st.text_input("سبب الحركة")
                if st.form_submit_button("تطبيق"):
                    update_stock(p['name'], abs(change), 'in' if change>0 else 'out', notes)
                    del st.session_state.stock_prod
                    st.rerun()
        if 'edit_prod' in st.session_state:
            p = st.session_state.edit_prod
            with st.form("edit_price"):
                new_price = st.number_input("السعر الجديد", value=p['price'], step=1.0)
                if st.form_submit_button("تحديث"):
                    from database import update_product
                    update_product(p['id'], p['name'], new_price)
                    del st.session_state.edit_prod
                    st.rerun()
    else:
        st.info("لا توجد منتجات. أضف منتجاً أولاً.")

# ============================== الكاشير ==============================
elif menu == "🛒 الكاشير":
    st.markdown("<div class='section-title'>🛒 واجهة البيع</div>", unsafe_allow_html=True)
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    products = {p['name']: p for p in get_all_products()}
    customers = get_all_customers()
    cust_opts = {c['id']: c['name'] for c in customers}
    cust_opts[None] = "بدون عميل (نقدي)"
    selected_cust = st.selectbox("👤 اختر العميل", list(cust_opts.keys()), format_func=lambda x: cust_opts[x])
    col1, col2 = st.columns([2,1])
    with col1:
        if products:
            prod = st.selectbox("📦 المنتج", list(products.keys()))
            qty = st.number_input("🔢 الكمية", min_value=1, step=1)
            if st.button("➕ إضافة إلى السلة"):
                p = products[prod]
                if p['stock'] >= qty:
                    st.session_state.cart.append({"name": prod, "price": p['price'], "qty": qty, "vat": p['vat_rate']})
                    st.rerun()
                else:
                    st.error("المخزون غير كافٍ")
        else:
            st.warning("لا توجد منتجات. أضف منتجاً أولاً.")
    with col2:
        if st.session_state.cart:
            total = 0
            for i, item in enumerate(st.session_state.cart):
                sub = item['price'] * item['qty']
                vat_amt = sub * item['vat']
                total += sub + vat_amt
                st.markdown(f"<div style='background:#f8fafc; padding:8px; border-radius:15px; margin:5px 0;'><b>{item['name']}</b> x{item['qty']} = {sub+vat_amt:.2f}</div>", unsafe_allow_html=True)
                if st.button(f"🗑️ حذف", key=f"rem_{i}"):
                    st.session_state.cart.pop(i)
                    st.rerun()
            st.metric("💰 الإجمالي", f"{total:.2f} ﷼")
            if st.button("✅ إتمام البيع"):
                for item in st.session_state.cart:
                    sub = item['price'] * item['qty']
                    vat_amt = sub * item['vat']
                    add_sale_with_customer(item['name'], item['qty'], sub+vat_amt, vat_amt, item['vat'], selected_cust if selected_cust!=None else None)
                st.session_state.cart = []
                st.success("تم البيع بنجاح")
                st.rerun()
        else:
            st.info("السلة فارغة")

# ============================== العملاء ==============================
elif menu == "👥 العملاء":
    st.markdown("<div class='section-title'>👥 العملاء والديون</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 قائمة العملاء", "➕ إضافة عميل"])
    with tab1:
        customers = get_all_customers()
        if customers:
            for c in customers:
                with st.expander(f"{c['name']} - الرصيد: {c['balance']:.2f} ﷼"):
                    st.write(f"📞 {c['phone']} | 🏠 {c['address']}")
                    if st.button(f"📜 كشف حساب", key=f"stmt_{c['id']}"):
                        stmt = get_customer_statement(c['id'])
                        if stmt:
                            st.dataframe(stmt)
                        else:
                            st.info("لا توجد معاملات")
                    amt = st.number_input("💵 مبلغ التحصيل", key=f"pay_{c['id']}", min_value=0.01, step=100.0)
                    if st.button(f"💰 تحصيل", key=f"rec_{c['id']}"):
                        receive_payment(c['id'], amt, "تحصيل يدوي")
                        st.rerun()
        else:
            st.info("لا يوجد عملاء")
    with tab2:
        with st.form("add_cust"):
            name = st.text_input("الاسم")
            phone = st.text_input("الجوال")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة"):
                if name.strip():
                    add_customer(name, phone, address)
                    st.rerun()
                else:
                    st.error("الاسم مطلوب")

# ============================== الموردين ==============================
elif menu == "📦 الموردين":
    st.markdown("<div class='section-title'>📦 الموردين والمشتريات</div>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["➕ إضافة مورد", "📋 قائمة الموردين", "➕ فاتورة شراء"])
    with tab1:
        with st.form("add_sup"):
            name = st.text_input("اسم المورد")
            phone = st.text_input("الجوال")
            if st.form_submit_button("إضافة"):
                if name.strip():
                    add_supplier(name, phone)
                    st.rerun()
                else:
                    st.error("الاسم مطلوب")
    with tab2:
        suppliers = get_all_suppliers()
        if suppliers:
            for s in suppliers:
                st.write(f"**{s['name']}** - 📞 {s['phone']} - الرصيد: {s['balance']:.2f}")
        else:
            st.info("لا يوجد موردون")
    with tab3:
        suppliers = get_all_suppliers()
        if suppliers:
            sup_map = {s['id']: s['name'] for s in suppliers}
            sup = st.selectbox("اختر المورد", list(sup_map.keys()), format_func=lambda x: sup_map[x])
            if 'purchase_items' not in st.session_state:
                st.session_state.purchase_items = []
            prods = get_all_products()
            if prods:
                pnames = [p['name'] for p in prods]
                col1, col2, col3 = st.columns(3)
                with col1: pn = st.selectbox("المنتج", pnames)
                with col2: qt = st.number_input("الكمية", min_value=1, step=1)
                with col3: cost = st.number_input("سعر الشراء", min_value=0.01, step=0.01)
                if st.button("➕ إضافة صنف"):
                    st.session_state.purchase_items.append({"product_name": pn, "qty": qt, "unit_cost": cost})
                    st.rerun()
                if st.session_state.purchase_items:
                    tot = 0
                    for idx, it in enumerate(st.session_state.purchase_items):
                        st.write(f"{it['product_name']} - {it['qty']} × {it['unit_cost']} = {it['qty']*it['unit_cost']}")
                        if st.button(f"❌ حذف", key=f"del_{idx}"):
                            st.session_state.purchase_items.pop(idx)
                            st.rerun()
                        tot += it['qty']*it['unit_cost']
                    st.metric("إجمالي الفاتورة", f"{tot:.2f}")
                    if st.button("💾 حفظ الفاتورة"):
                        add_purchase(sup, st.session_state.purchase_items)
                        st.session_state.purchase_items = []
                        st.rerun()
            else:
                st.warning("لا توجد منتجات لإضافتها")
        else:
            st.warning("لا يوجد موردون. أضف مورداً أولاً.")

# ============================== المحاسبة ==============================
elif menu == "📊 المحاسبة":
    st.markdown("<div class='section-title'>📊 المحاسبة</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📒 دليل الحسابات", "📜 القيود اليومية"])
    with tab1:
        accs = get_accounts_tree()
        if accs:
            data = []
            for a in accs:
                bal = get_account_balance(a['id'])
                data.append({"الكود": a['code'], "الحساب": a['name'], "النوع": a['type'], "الرصيد": f"{bal:,.2f}"})
            st.dataframe(data, use_container_width=True)
        else:
            st.info("لا توجد حسابات")
    with tab2:
        entries = get_all_journal_entries()
        if entries:
            for entry in entries.values():
                with st.expander(f"📌 {entry['date']} - {entry['description']} {entry['reference']}"):
                    st.dataframe(entry['details'], use_container_width=True)
        else:
            st.info("لا توجد قيود محاسبية بعد")

# ============================== الضريبة ==============================
elif menu == "💰 الضريبة (VAT)":
    st.markdown("<div class='section-title'>💰 إعدادات الضريبة</div>", unsafe_allow_html=True)
    settings = get_vat_settings()
    rate = st.number_input("نسبة الضريبة الافتراضية (%)", min_value=0.0, max_value=100.0, value=settings['default_rate']*100, step=0.5) / 100
    enabled = st.checkbox("تفعيل الضريبة", value=bool(settings['is_enabled']))
    if st.button("حفظ الإعدادات"):
        update_vat_settings(rate, enabled)
        st.rerun()

# ============================== الأصول الثابتة ==============================
elif menu == "🏭 الأصول الثابتة":
    st.markdown("<div class='section-title'>🏭 الأصول الثابتة</div>", unsafe_allow_html=True)
    st.info("⚙️ قيد التطوير – سيتم إضافة واجهة الأصول الثابتة والإهلاك قريباً.")

# ============================== المستودعات ==============================
elif menu == "🏚️ المستودعات":
    st.markdown("<div class='section-title'>🏚️ المستودعات</div>", unsafe_allow_html=True)
    st.info("⚙️ قيد التطوير – سيتم إضافة إدارة المستودعات المتعددة قريباً.")

# ============================== الموارد البشرية ==============================
elif menu == "👨‍💼 الموارد البشرية":
    st.markdown("<div class='section-title'>👨‍💼 الموارد البشرية</div>", unsafe_allow_html=True)
    st.info("⚙️ قيد التطوير – سيتم إضافة إدارة الموظفين والرواتب قريباً.")

# ============================== الإنتاج ==============================
elif menu == "🏭 الإنتاج (BOM)":
    st.markdown("<div class='section-title'>🏭 الإنتاج (BOM)</div>", unsafe_allow_html=True)
    st.info("⚙️ قيد التطوير – سيتم إضافة قوائم المكونات وأوامر الإنتاج قريباً.")

# ============================== التقارير المتقدمة ==============================
elif menu == "📈 التقارير المتقدمة":
    st.markdown("<div class='section-title'>📈 التقارير المتقدمة</div>", unsafe_allow_html=True)
    from database import advanced_report
    advanced_report()

# ============================== مرتجعات المبيعات ==============================
elif menu == "🔄 مرتجعات المبيعات":
    st.markdown("<div class='section-title'>🔄 مرتجعات المبيعات</div>", unsafe_allow_html=True)
    invoices = get_all_sales_invoices()
    if not invoices:
        st.info("لا توجد فواتير بيع مسجلة")
    else:
        inv_options = {inv['id']: f"{inv['date']} - {inv['customer']} ({len(inv['items'])} منتج)" for inv in invoices}
        inv_id = st.selectbox("اختر فاتورة", list(inv_options.keys()), format_func=lambda x: inv_options[x])
        inv = next((i for i in invoices if i['id'] == inv_id), None)
        if inv:
            for item in inv['items']:
                remaining = item['qty'] - item.get('returned',0)
                if remaining > 0:
                    ret_qty = st.number_input(f"كمية مرتجع {item['product']} (متاح {remaining})", min_value=1, max_value=remaining, key=item['product'])
                    if st.button(f"استرجاع {item['product']}"):
                        process_return(inv_id, item['product'], ret_qty)
                        st.rerun()

# ============================== الأدوات المتقدمة ==============================
elif menu == "🛠️ الأدوات المتقدمة":
    try:
        exec(open("advanced_tools.py").read())
    except Exception as e:
        st.error(f"خطأ في تحميل الأدوات المتقدمة: {e}")

st.markdown("---")
st.markdown("<div class='footer'>🎭 نظام المتكامل - ERP | تصميم وتطوير سالم التريمي | جميع الحقوق محفوظة © 2025</div>", unsafe_allow_html=True)
