# ui/pdf_reports.py – واجهة تقارير PDF (تصميم زجاجي فخم وألوان زاهية)
import streamlit as st
import os
from datetime import datetime
from services.pdf_service import (
    generate_income_statement,
    generate_balance_sheet,
    generate_inventory_report,
    generate_audit_report,
    generate_invoice_pdf,
    OUTPUT_DIR,
    ensure_output_dir
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
ACCENT_CYAN = "#06B6D4"
ACCENT_PINK = "#EC4899"

def card(icon, title, desc, color):
    return f"""
    <div style="
        background:{GLASS_BG}; backdrop-filter:blur(10px);
        border:1px solid {GLASS_BORDER}; border-radius:20px;
        padding:1.5rem; text-align:center; box-shadow:{GLASS_SHADOW};
        margin-bottom:1rem; transition:transform 0.2s;
    ">
        <div style="font-size:2.5rem; margin-bottom:0.5rem;">{icon}</div>
        <div style="color:{color}; font-size:1.2rem; font-weight:700;">{title}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.9rem; margin-top:0.3rem;">{desc}</div>
    </div>
    """

def show():
    ensure_output_dir()

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_CYAN};">📄 تقارير PDF</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">حمّل تقاريرك المالية والإدارية بصيغة PDF بضغطة زر</p>
    </div>
    """, unsafe_allow_html=True)

    # اختيار نوع التقرير
    report_type = st.selectbox(
        "اختر نوع التقرير",
        [
            "📊 قائمة الدخل",
            "⚖️ الميزانية العمومية",
            "📦 تقرير المخزون",
            "🛡️ سجل التدقيق",
            "🧾 فاتورة محددة"
        ]
    )

    invoice_id = None
    if "فاتورة" in report_type:
        invoice_id = st.number_input("رقم الفاتورة", min_value=1, step=1)

    # زر التوليد
    if st.button("🚀 توليد التقرير PDF", type="primary", use_container_width=True):
        with st.spinner("📄 جاري إنشاء التقرير..."):
            try:
                if report_type == "📊 قائمة الدخل":
                    path = generate_income_statement()
                elif report_type == "⚖️ الميزانية العمومية":
                    path = generate_balance_sheet()
                elif report_type == "📦 تقرير المخزون":
                    path = generate_inventory_report()
                elif report_type == "🛡️ سجل التدقيق":
                    path = generate_audit_report()
                elif report_type == "🧾 فاتورة محددة":
                    if not invoice_id:
                        st.error("الرجاء إدخال رقم الفاتورة")
                        st.stop()
                    path = generate_invoice_pdf(invoice_id)
                    if path is None:
                        st.error("الفاتورة غير موجودة")
                        st.stop()
                else:
                    st.stop()

                # عرض نجاح مع رابط تحميل
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    st.download_button(
                        label=f"📥 تحميل {filename}",
                        data=f,
                        file_name=filename,
                        mime="application/pdf",
                        type="primary"
                    )
                st.success(f"✅ تم إنشاء التقرير بنجاح: {filename}")

            except Exception as e:
                st.error(f"❌ فشل إنشاء التقرير: {e}")

    # عرض التقارير السابقة
    st.markdown("---")
    st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 التقارير السابقة</h3>", unsafe_allow_html=True)
    if os.path.exists(OUTPUT_DIR):
        files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")], reverse=True)
        if files:
            for file in files[:10]:  # آخر 10 تقارير
                path = os.path.join(OUTPUT_DIR, file)
                size_kb = os.path.getsize(path) / 1024
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"📄 {file}")
                with col2:
                    st.write(f"{size_kb:.1f} KB")
                with col3:
                    with open(path, "rb") as f:
                        st.download_button(
                            label="📥",
                            data=f,
                            file_name=file,
                            key=f"dl_{file}"
                        )
        else:
            st.info("لا توجد تقارير سابقة")
    else:
        st.info("لا توجد تقارير سابقة")
