# ui/pdf_reports.py – واجهة تقارير احترافية (تصميم ذهبي فاخر)
import streamlit as st
import os
from services.pdf_service import (
    generate_income_statement,
    generate_balance_sheet,
    generate_inventory_report,
    generate_audit_report,
    generate_invoice_html,
    generate_cash_report,
    generate_vat_report,
    generate_xbrl_income,
    generate_xbrl_balance,
    OUTPUT_DIR,
    ensure_output_dir
)

# ========== ألوان التصميم الذهبي الفاخر ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(212, 175, 55, 0.3)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_CYAN = "#06B6D4"

def glass_card(icon, title, desc, color):
    return f"""
    <div style="
        background: linear-gradient(145deg, rgba(20, 30, 50, 0.8), rgba(10, 15, 30, 0.9));
        backdrop-filter:blur(10px);
        border:1px solid {GLASS_BORDER}; border-radius:20px;
        padding:1.5rem; text-align:center; box-shadow:{GLASS_SHADOW};
        margin-bottom:1rem;
    ">
        <div style="font-size:2.5rem; margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{color}; font-size:1.2rem; font-weight:700;">{title}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.85rem;">{desc}</div>
    </div>
    """

def show():
    # ===== تصميم ذهبي فاخر =====
    st.markdown("""
    <style>
    .stButton > button {
        background: linear-gradient(135deg, rgba(212,175,55,0.2), rgba(212,175,55,0.05)) !important;
        border: 1px solid rgba(212,175,55,0.4) !important;
        color: #FCF6BA !important;
        font-weight: 700 !important;
        transition: all 0.3s ease !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #D4AF37, #AA771C) !important;
        color: #000 !important;
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(212,175,55,0.4) !important;
    }
    .report-download-btn > button {
        background: rgba(16, 185, 129, 0.2) !important;
        border: 1px solid rgba(16, 185, 129, 0.5) !important;
        color: #10B981 !important;
    }
    .report-download-btn > button:hover {
        background: #10B981 !important;
        color: #fff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    ensure_output_dir()

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{GOLD}; font-size:2.8rem; margin:0; text-shadow:0 0 20px rgba(212,175,55,0.3);">📄 التقارير المالية</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">تقارير HTML و XBRL احترافية بضغطة زر</p>
    </div>
    """, unsafe_allow_html=True)

    # ========== تبويبات ==========
    tab1, tab2, tab3 = st.tabs(["📊 تقارير مالية", "🏢 تقارير إدارية", "🌐 تقارير XBRL"])

    # ========== تبويب 1: تقارير مالية ==========
    with tab1:
        st.markdown(f"<h3 style='color:{GOLD};'>التقارير المالية</h3>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(glass_card("📊", "قائمة الدخل", "الإيرادات والمصروفات وصافي الدخل", ACCENT_GREEN), unsafe_allow_html=True)
        with col2:
            st.markdown(glass_card("⚖️", "الميزانية العمومية", "الأصول والخصوم وحقوق الملكية", ACCENT_CYAN), unsafe_allow_html=True)
        with col3:
            st.markdown(glass_card("🧾", "تقرير الضريبة", "ضريبة القيمة المضافة", ACCENT_RED), unsafe_allow_html=True)

        report_type = st.selectbox(
            "اختر التقرير",
            ["📊 قائمة الدخل", "⚖️ الميزانية العمومية", "🧾 تقرير الضريبة"],
            key="financial_report"
        )

        if st.button("🚀 توليد التقرير المالي", type="primary", use_container_width=True):
            with st.spinner("📄 جاري إنشاء التقرير..."):
                try:
                    path = None
                    if "قائمة الدخل" in report_type:
                        path = generate_income_statement()
                    elif "الميزانية" in report_type:
                        path = generate_balance_sheet()
                    elif "الضريبة" in report_type:
                        path = generate_vat_report()

                    if path:
                        filename = os.path.basename(path)
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        st.success(f"✅ تم إنشاء التقرير: {filename}")
                        st.download_button(
                            label=f"📥 تحميل {filename}",
                            data=content,
                            file_name=filename,
                            mime="text/html",
                            type="primary"
                        )
                    else:
                        st.warning("لا توجد بيانات كافية لإنشاء هذا التقرير")
                except Exception as e:
                    st.error(f"❌ فشل إنشاء التقرير: {e}")

    # ========== تبويب 2: تقارير إدارية ==========
    with tab2:
        st.markdown(f"<h3 style='color:{GOLD};'>التقارير الإدارية والرقابية</h3>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(glass_card("📦", "المخزون", "المنتجات والكميات", ACCENT_ORANGE), unsafe_allow_html=True)
        with col2:
            st.markdown(glass_card("🛡️", "سجل التدقيق", "آخر 100 عملية", ACCENT_PURPLE), unsafe_allow_html=True)
        with col3:
            st.markdown(glass_card("💰", "تقرير الصندوق", "أرصدة وحسابات النقدية", ACCENT_BLUE), unsafe_allow_html=True)

        col4, _ = st.columns(2)
        with col4:
            st.markdown(glass_card("🧾", "فاتورة محددة", "تفاصيل فاتورة برقم", GOLD), unsafe_allow_html=True)

        report_type2 = st.selectbox(
            "اختر التقرير",
            ["📦 تقرير المخزون", "🛡️ سجل التدقيق", "💰 تقرير الصندوق", "🧾 فاتورة محددة"],
            key="admin_report"
        )

        invoice_id = None
        if "فاتورة" in report_type2:
            invoice_id = st.number_input("رقم الفاتورة", min_value=1, step=1)

        if st.button("🚀 توليد التقرير الإداري", type="primary", use_container_width=True):
            with st.spinner("📄 جاري إنشاء التقرير..."):
                try:
                    path = None
                    if "المخزون" in report_type2:
                        path = generate_inventory_report()
                    elif "التدقيق" in report_type2:
                        path = generate_audit_report()
                    elif "الصندوق" in report_type2:
                        path = generate_cash_report()
                    elif "فاتورة" in report_type2:
                        if not invoice_id:
                            st.error("الرجاء إدخال رقم الفاتورة")
                        else:
                            path = generate_invoice_html(invoice_id)

                    if path:
                        filename = os.path.basename(path)
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        st.success(f"✅ تم إنشاء التقرير: {filename}")
                        st.download_button(
                            label=f"📥 تحميل {filename}",
                            data=content,
                            file_name=filename,
                            mime="text/html",
                            type="primary"
                        )
                    elif path is None and "فاتورة" not in report_type2:
                        st.warning("لا توجد بيانات كافية لإنشاء هذا التقرير")
                except Exception as e:
                    st.error(f"❌ فشل إنشاء التقرير: {e}")

    # ========== تبويب 3: XBRL ==========
    with tab3:
        st.markdown(f"<h3 style='color:{GOLD};'>تقارير XBRL (لغة تقارير الأعمال الموسعة)</h3>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, rgba(212,175,55,0.1), rgba(212,175,55,0.02));
                    border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.5rem; margin-bottom:1rem;
                    text-align:center;">
            <p style="color:{GOLD_LIGHT}; font-size:1.2rem; font-weight:700;">🌐 XBRL – المعيار العالمي للتقارير المالية</p>
            <p style="color:{TEXT_SECONDARY};">تقارير XML قابلة للقراءة آلياً من قبل الجهات الرقابية والبنوك وهيئات الضرائب</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(glass_card("📊", "XBRL قائمة الدخل", "Revenue, Expenses, NetIncome", ACCENT_GREEN), unsafe_allow_html=True)
            if st.button("توليد XBRL للدخل", type="primary", use_container_width=True):
                path = generate_xbrl_income()
                if path:
                    filename = os.path.basename(path)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    st.success(f"✅ {filename}")
                    st.download_button(label=f"📥 تحميل {filename}", data=content, file_name=filename, mime="application/xml")
        with col2:
            st.markdown(glass_card("⚖️", "XBRL الميزانية", "Assets, Liabilities, Equity", ACCENT_CYAN), unsafe_allow_html=True)
            if st.button("توليد XBRL للميزانية", type="primary", use_container_width=True):
                path = generate_xbrl_balance()
                if path:
                    filename = os.path.basename(path)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    st.success(f"✅ {filename}")
                    st.download_button(label=f"📥 تحميل {filename}", data=content, file_name=filename, mime="application/xml")

    # ========== التقارير السابقة ==========
    st.markdown("---")
    st.markdown(f"<h3 style='color:{GOLD};'>📋 التقارير السابقة</h3>", unsafe_allow_html=True)
    if os.path.exists(OUTPUT_DIR):
        all_files = sorted(os.listdir(OUTPUT_DIR), reverse=True)
        files = [f for f in all_files if f.endswith(('.html', '.xml'))]
        if files:
            for file in files[:10]:
                path = os.path.join(OUTPUT_DIR, file)
                size_kb = os.path.getsize(path) / 1024
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    icon = "🌐" if file.endswith('.xml') else "📄"
                    st.write(f"{icon} {file}")
                with col2:
                    st.write(f"{size_kb:.1f} KB")
                with col3:
                    mime = "application/xml" if file.endswith('.xml') else "text/html"
                    with open(path, "r", encoding="utf-8") as f:
                        st.download_button(label="📥", data=f.read(), file_name=file, mime=mime, key=f"dl_{file}")
        else:
            st.info("لا توجد تقارير سابقة")
    else:
        st.info("لا توجد تقارير سابقة")
