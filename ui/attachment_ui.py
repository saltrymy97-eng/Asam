# ui/attachment_ui.py – واجهة المرفقات (تصميم زجاجي فخم ومبهر)
import streamlit as st
import pandas as pd
import os
from services import attachment_service as att

# ========== ألوان التصميم الفاخر ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"

def glass_card(content, padding="1.5rem"):
    return f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.25);border-radius:20px;padding:{padding};margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{T};">{content}</div>"""

def kpi_box(icon, label, value, color):
    return f"""<div style="background:rgba(255,255,255,0.08);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.18);border-radius:20px;padding:1.5rem;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,0.3);height:100%;">
        <div style="font-size:2.8rem;margin-bottom:0.5rem;">{icon}</div>
        <div style="color:{S};font-size:0.85rem;margin-bottom:0.3rem;">{label}</div>
        <div style="color:{color};font-size:2rem;font-weight:800;">{value}</div>
    </div>"""

def show():
    # ========== رأس الصفحة ==========
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(139,92,246,0.4),rgba(59,130,246,0.4));backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-radius:25px;padding:35px;text-align:center;margin-bottom:35px;border:1px solid rgba(255,255,255,0.25);box-shadow:0 15px 50px rgba(0,0,0,0.5);">
        <div style="font-size:4rem;margin-bottom:10px;">📎</div>
        <h1 style="color:{T};font-size:3.2rem;margin:0;font-weight:800;">إدارة المرفقات</h1>
        <p style="color:{S};font-size:1.2rem;margin-top:10px;">أرشفة المستندات وربطها بالسجلات بكل سهولة</p>
    </div>
    """, unsafe_allow_html=True)

    # ========== بطاقات إحصائية ==========
    all_attachments = att.get_attachments()
    total_count = len(all_attachments)
    total_size_kb = sum(a['file_size'] for a in all_attachments) / 1024 if all_attachments else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(kpi_box("📦", "عدد المرفقات", str(total_count), BL), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_box("💾", "الحجم الإجمالي", f"{total_size_kb:.1f} ك.ب", GR), unsafe_allow_html=True)
    with col3:
        st.markdown(kpi_box("📁", "الصيغ المدعومة", "6 صيغ", OR), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ========== التبويبات ==========
    tab1, tab2 = st.tabs(["📤 رفع مرفق جديد", "📁 تصفح المرفقات"])

    # ---------- رفع مرفق ----------
    with tab1:
        st.markdown(glass_card(f"""
            <h3 style="color:{BL};margin-top:0;font-size:1.5rem;">📤 رفع مرفق جديد</h3>
            <p style="color:{S};">ارفع ملفاً وأرفقه بأي سجل في النظام</p>
        """), unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "اختر ملفاً للرفع",
            type=["pdf", "jpg", "jpeg", "png", "xlsx", "docx", "zip"],
            help="الصيغ المدعومة: PDF، صور، Excel، Word، ZIP"
        )

        col1, col2 = st.columns(2)
        with col1:
            linked_table = st.selectbox("نوع السجل المرتبط", [
                "invoices", "journal_entries", "customers", "suppliers",
                "employees", "products", "cost_centers"
            ], format_func=lambda x: {
                "invoices": "🧾 فاتورة", "journal_entries": "📝 قيد", "customers": "👤 عميل",
                "suppliers": "🚚 مورد", "employees": "👔 موظف", "products": "📦 منتج",
                "cost_centers": "🏢 مركز تكلفة"
            }[x])
        with col2:
            linked_id = st.number_input("رقم السجل", min_value=1, step=1, value=1)

        if st.button("🚀 رفع المرفق الآن", type="primary", disabled=not uploaded_file, use_container_width=True):
            try:
                success, name = att.upload_attachment(
                    uploaded_file, linked_table, linked_id,
                    st.session_state.user.get('username', 'admin')
                )
                st.success(f"✅ تم رفع الملف '{uploaded_file.name}' بنجاح")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"❌ فشل الرفع: {str(e)}")

    # ---------- تصفح المرفقات ----------
    with tab2:
        st.markdown(glass_card(f"""
            <h3 style="color:{GR};margin-top:0;font-size:1.5rem;">📁 المرفقات الحالية</h3>
        """), unsafe_allow_html=True)

        filter_table = st.selectbox(
            "تصفية حسب النوع",
            ["الكل", "فواتير", "قيود", "عملاء", "موردون", "موظفون", "منتجات", "مراكز تكلفة"]
        )
        table_map = {
            "فواتير": "invoices", "قيود": "journal_entries", "عملاء": "customers",
            "موردون": "suppliers", "موظفون": "employees", "منتجات": "products",
            "مراكز تكلفة": "cost_centers"
        }
        link_table = table_map.get(filter_table) if filter_table != "الكل" else None

        attachments = att.get_attachments(linked_table=link_table)
        if attachments:
            df = pd.DataFrame(attachments)
            df['نوع السجل'] = df['linked_table'].map({
                "invoices": "🧾 فاتورة", "journal_entries": "📝 قيد", "customers": "👤 عميل",
                "suppliers": "🚚 مورد", "employees": "👔 موظف", "products": "📦 منتج",
                "cost_centers": "🏢 مركز تكلفة"
            })
            df_display = df.rename(columns={
                "id": "رقم", "original_name": "اسم الملف",
                "file_size": "الحجم", "linked_id": "رقم السجل",
                "uploaded_at": "تاريخ الرفع"
            })
            st.dataframe(
                df_display[["رقم", "اسم الملف", "الحجم", "نوع السجل", "رقم السجل", "تاريخ الرفع"]],
                use_container_width=True,
                hide_index=True
            )

            attach_ids = [a['id'] for a in attachments]
            selected_id = st.selectbox(
                "اختر مرفقاً للإجراءات",
                attach_ids,
                format_func=lambda x: next((a['original_name'] for a in attachments if a['id'] == x), "")
            )
            selected = att.get_attachment_by_id(selected_id)
            if selected and os.path.exists(selected['file_path']):
                col1, col2 = st.columns(2)
                with col1:
                    with open(selected['file_path'], "rb") as f:
                        st.download_button(
                            "📥 تحميل الملف",
                            f,
                            file_name=selected['original_name'],
                            use_container_width=True
                        )
                with col2:
                    if st.button("🗑️ حذف المرفق", key=f"del_{selected_id}", use_container_width=True):
                        att.delete_attachment(selected_id)
                        st.success("تم حذف المرفق بنجاح")
                        st.rerun()
        else:
            st.markdown(glass_card("ℹ️ لا توجد مرفقات حالياً. ابدأ برفع ملفاتك الآن!"), unsafe_allow_html=True)
