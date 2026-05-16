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

# تهيئة قاعدة البيانات
init_db()

# إعدادات الصفحة
st.set_page_config(page_title="نظام ERP المتكامل", layout="wide")

# ========== CSS ==========
st.markdown("""
<style>
    .metric-card { background: white; border-radius: 20px; padding: 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .metric-card h3 { margin: 0; color: #4a1d8c; }
    .stButton>button { background: #6f42c1; color: white; border-radius: 30px; }
</style>
""", unsafe_allow_html=True)

# ========== المصادقة ==========
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        role = authenticate(username, password)
        if role:
            st.session_state.authenticated = True
            st.session_state.role = role
            st.session_state.username = username
            st.rerun()
        else:
            st.error("بيانات غير صحيحة")
    st.stop()

# ========== القائمة الجانبية ==========
st.sidebar.markdown(f"**مرحباً {st.session_state.username}**")
st.sidebar.markdown("---")

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

# تصفية حسب الصلاحيات (اختياري)
if st.session_state.role == 'cashier':
    allowed = ["🏠 لوحة التحكم", "📦 المنتجات", "🛒 الكاشير", "📈 التقارير المتقدمة", "🔄 مرتجعات المبيعات"]
    menu_options = [m for m in menu_options if m in allowed]
elif st.session_state.role == 'accountant':
    allowed = ["🏠 لوحة التحكم", "👥 العملاء", "📦 الموردين", "📊 المحاسبة", "💰 الضريبة (VAT)", "📈 التقارير المتقدمة"]
    menu_options = [m for m in menu_options if m in allowed]

menu = st.sidebar.radio("القائمة الرئيسية", menu_options)

if st.sidebar.button("تسجيل الخروج"):
    st.session_state.authenticated = False
    st.rerun()

# ========== الصفحات ==========
if menu == "🏠 لوحة التحكم":
    products = get_all_products()
    sales_sum = get_sales_summary()
    low_stock = get_low_stock(5)
    customers = get_all_customers()
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"<div class='metric-card'><h3>{len(products)}</h3><p>المنتجات</p></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><h3>{sales_sum['total_revenue']:,.0f}</h3><p>الإيرادات</p></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><h3>{len(low_stock)}</h3><p>مخزون منخفض</p></div>", unsafe_allow_html=True)
    with col4: st.markdown(f"<div class='metric-card'><h3>{len(customers)}</h3><p>العملاء</p></div>", unsafe_allow_html=True)
    if low_stock:
        st.warning("⚠️ منتجات منخفضة المخزون: " + ", ".join([p['name'] for p in low_stock]))

elif menu == "📦 المنتجات":
    st.header("إدارة المنتجات")
    with st.expander("➕ إضافة منتج"):
        with st.form("add_prod"):
            name = st.text_input("الاسم")
            price = st.number_input("السعر", min_value=0.0, step=1.0)
            stock = st.number_input("المخزون", min_value=0, step=1)
            vat = st.number_input("الضريبة (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0)
            if st.form_submit_button("إضافة"):
                add_product(name, price, stock, vat/100)
                st.rerun()
    products = get_all_products()
    for p in products:
        col1, col2, col3, col4 = st.columns([3,1,1,1])
        col1.write(f"**{p['name']}** - {p['price']:.2f} - المخزون: {p['stock']}")
        if col2.button("تعديل المخزون", key=f"stock_{p['id']}"):
            st.session_state.stock_prod = p
        if col3.button("حذف", key=f"del_{p['id']}"):
            delete_product(p['id'])
            st.rerun()
    if 'stock_prod' in st.session_state:
        p = st.session_state.stock_prod
        with st.form("up_stock"):
            change = st.number_input(f"تغيير مخزون {p['name']}", step=1)
            if st.form_submit_button("تطبيق"):
                update_stock(p['name'], abs(change), 'in' if change>0 else 'out', "تعديل يدوي")
                del st.session_state.stock_prod
                st.rerun()

elif menu == "🛒 الكاشير":
    st.header("واجهة البيع")
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    products = {p['name']: p for p in get_all_products()}
    customers = get_all_customers()
    cust_opts = {c['id']: c['name'] for c in customers}
    cust_opts[None] = "بدون عميل (نقدي)"
    selected_cust = st.selectbox("العميل", list(cust_opts.keys()), format_func=lambda x: cust_opts[x])
    col1, col2 = st.columns([2,1])
    with col1:
        prod = st.selectbox("المنتج", list(products.keys()))
        qty = st.number_input("الكمية", min_value=1, step=1)
        if st.button("إضافة للسلة"):
            p = products[prod]
            if p['stock'] >= qty:
                st.session_state.cart.append({"name": prod, "price": p['price'], "qty": qty, "vat": p['vat_rate']})
                st.rerun()
            else:
                st.error("مخزون غير كاف")
    with col2:
        if st.session_state.cart:
            total = 0
            for i, item in enumerate(st.session_state.cart):
                sub = item['price'] * item['qty']
                vat_amt = sub * item['vat']
                total += sub + vat_amt
                st.write(f"{item['name']} x{item['qty']} = {sub+vat_amt:.2f}")
                if st.button(f"حذف", key=f"rem_{i}"):
                    st.session_state.cart.pop(i)
                    st.rerun()
            st.metric("الإجمالي", f"{total:.2f}")
            if st.button("إتمام البيع"):
                for item in st.session_state.cart:
                    sub = item['price'] * item['qty']
                    vat_amt = sub * item['vat']
                    add_sale_with_customer(item['name'], item['qty'], sub+vat_amt, vat_amt, item['vat'], selected_cust if selected_cust!=None else None)
                st.session_state.cart = []
                st.success("تم البيع")
                st.rerun()
        else:
            st.info("السلة فارغة")

elif menu == "👥 العملاء":
    st.header("العملاء والديون")
    tab1, tab2 = st.tabs(["القائمة", "إضافة عميل"])
    with tab1:
        for c in get_all_customers():
            with st.expander(f"{c['name']} - الرصيد: {c['balance']:.2f}"):
                st.write(f"{c['phone']} | {c['address']}")
                if st.button(f"كشف حساب", key=f"stmt_{c['id']}"):
                    stmt = get_customer_statement(c['id'])
                    st.dataframe(stmt)
                amt = st.number_input("مبلغ التحصيل", key=f"pay_{c['id']}", min_value=0.01)
                if st.button(f"تحصيل", key=f"rec_{c['id']}"):
                    receive_payment(c['id'], amt, "تحصيل يدوي")
                    st.rerun()
    with tab2:
        with st.form("add_cust"):
            name = st.text_input("الاسم")
            phone = st.text_input("الجوال")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة"):
                add_customer(name, phone, address)
                st.rerun()

elif menu == "📦 الموردين":
    st.header("الموردين والمشتريات")
    tab1, tab2, tab3 = st.tabs(["إضافة مورد", "قائمة الموردين", "فاتورة شراء"])
    with tab1:
        with st.form("add_sup"):
            name = st.text_input("اسم المورد")
            phone = st.text_input("الجوال")
            if st.form_submit_button("إضافة"):
                add_supplier(name, phone)
                st.rerun()
    with tab2:
        for s in get_all_suppliers():
            st.write(f"**{s['name']}** - {s['phone']} - الرصيد: {s['balance']:.2f}")
    with tab3:
        suppliers = get_all_suppliers()
        if suppliers:
            sup_map = {s['id']: s['name'] for s in suppliers}
            sup = st.selectbox("المورد", list(sup_map.keys()), format_func=lambda x: sup_map[x])
            if 'purchase_items' not in st.session_state:
                st.session_state.purchase_items = []
            prods = get_all_products()
            pnames = [p['name'] for p in prods]
            col1, col2, col3 = st.columns(3)
            with col1: pn = st.selectbox("المنتج", pnames)
            with col2: qt = st.number_input("الكمية", min_value=1, step=1)
            with col3: cost = st.number_input("سعر الشراء", min_value=0.01)
            if st.button("إضافة صنف"):
                st.session_state.purchase_items.append({"product_name": pn, "qty": qt, "unit_cost": cost})
                st.rerun()
            if st.session_state.purchase_items:
                tot = 0
                for idx, it in enumerate(st.session_state.purchase_items):
                    st.write(f"{it['product_name']} - {it['qty']} × {it['unit_cost']} = {it['qty']*it['unit_cost']}")
                    if st.button(f"حذف", key=f"del_{idx}"):
                        st.session_state.purchase_items.pop(idx)
                        st.rerun()
                    tot += it['qty']*it['unit_cost']
                st.metric("الإجمالي", f"{tot:.2f}")
                if st.button("حفظ الفاتورة"):
                    add_purchase(sup, st.session_state.purchase_items)
                    st.session_state.purchase_items = []
                    st.rerun()
        else:
            st.warning("لا يوجد موردون")

elif menu == "📊 المحاسبة":
    st.header("دليل الحسابات والقيود")
    tab1, tab2 = st.tabs(["الحسابات", "القيود"])
    with tab1:
        accs = get_accounts_tree()
        data = []
        for a in accs:
            bal = get_account_balance(a['id'])
            data.append({"الكود": a['code'], "الاسم": a['name'], "النوع": a['type'], "الرصيد": f"{bal:,.2f}"})
        st.dataframe(data)
    with tab2:
        entries = get_all_journal_entries()
        for entry in entries.values():
            with st.expander(f"{entry['date']} - {entry['description']}"):
                st.dataframe(entry['details'])

elif menu == "💰 الضريبة (VAT)":
    st.header("إعدادات الضريبة")
    settings = get_vat_settings()
    rate = st.number_input("نسبة الضريبة (%)", min_value=0.0, max_value=100.0, value=settings['default_rate']*100, step=0.5) / 100
    enabled = st.checkbox("تفعيل الضريبة", value=bool(settings['is_enabled']))
    if st.button("حفظ"):
        update_vat_settings(rate, enabled)
        st.rerun()

elif menu == "🏭 الأصول الثابتة":
    st.header("الأصول الثابتة")
    # يمكن إضافة كود مختصر هنا
    st.info("سيتم إضافة واجهة الأصول الثابتة لاحقاً")

elif menu == "🏚️ المستودعات":
    st.header("المستودعات")
    st.info("قيد التطوير")

elif menu == "👨‍💼 الموارد البشرية":
    st.header("الموارد البشرية")
    st.info("قيد التطوير")

elif menu == "🏭 الإنتاج (BOM)":
    st.header("الإنتاج")
    st.info("قيد التطوير")

elif menu == "📈 التقارير المتقدمة":
    st.header("التقارير المتقدمة")
    from database import advanced_report
    advanced_report()

elif menu == "🔄 مرتجعات المبيعات":
    st.header("مرتجعات المبيعات")
    invoices = get_all_sales_invoices()
    if not invoices:
        st.info("لا توجد فواتير")
    else:
        inv_options = {inv['id']: f"{inv['date']} - {inv['customer']}" for inv in invoices}
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

# ========== الأدوات المتقدمة (استدعاء الملف الثاني) ==========
elif menu == "🛠️ الأدوات المتقدمة":
    try:
        # تشغيل الملف advanced_tools.py (بدون set_page_config)
        exec(open("advanced_tools.py").read())
    except Exception as e:
        st.error(f"خطأ في تحميل الأدوات المتقدمة: {e}")

# ========== التذييل ==========
st.sidebar.markdown("---")
st.sidebar.caption("© 2025 - جميع الحقوق محفوظة")
