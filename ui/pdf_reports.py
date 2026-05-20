# ui/pdf_reports.py – واجهة تقارير PDF (مع معالجة الجداول الفارغة)
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

def show():
    ensure_output_dir()

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_CYAN};">📄 تقارير PDF</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">حمّل تقاريرك المالية والإدارية بصيغة PDF بضغطة زر</p>
    </div>
    """, unsafe_allow_html=True)

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

    if st.button("🚀 توليد التقرير PDF", type="primary", use_container_width=True):
        with st.spinner("📄 جاري إنشاء التقرير..."):
            try:
                path = None
                if report_type == "📊 قائمة الدخل":
                    path = generate_income_statement()
                    if path is None:
                        st.warning("لا توجد قيود محاسبية لإنشاء قائمة الدخل")
                elif report_type == "⚖️ الميزانية العمومية":
                    path = generate_balance_sheet()
                    if path is None:
                        st.warning("لا توجد قيود محاسبية لإنشاء الميزانية العمومية")
                elif report_type == "📦 تقرير المخزون":
                    path = generate_inventory_report()
                    if path is None:
                        st.warning("لا توجد منتجات لإنشاء تقرير المخزون")
                elif report_type == "🛡️ سجل التدقيق":
                    path = generate_audit_report()
                    if path is None:
                        st.warning("لا توجد سجلات تدقيق لإنشاء التقرير")
                elif report_type == "🧾 فاتورة محددة":
                    if not invoice_id:
                        st.error("الرجاء إدخال رقم الفاتورة")
                    else:
                        path = generate_invoice_pdf(invoice_id)
                        if path is None:
                            st.error("الفاتورة غير موجودة")

                if path:
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
            for file in files[:10]:
                path = os.path.join(OUTPUT_DIR, file)
                size_kb = os.path.getsize(path) / 1024
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"📄 {file}")
                with col2:
                    st.write(f"{size_kb:.1f} KB")
                with col3:
                    with open(path, "rb") as f:
                        st.download_button(label="📥", data=f, file_name=file, key=f"dl_{file}")
        else:
            st.info("لا توجد تقارير سابقة")
    else:
        st.info("لا توجد تقارير سابقة")
