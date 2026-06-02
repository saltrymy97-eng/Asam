# ui/attachment_ui.py – واجهة المرفقات (تصميم زجاجي فخم)
import streamlit as st
import pandas as pd
import os
from services import attachment_service as att

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

def show():
    # ========== الرأس الزجاجي ==========
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.3), rgba(59, 130, 246, 0.3));
         backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
         border-radius: 20px; padding: 28px; text-align: center; margin-bottom: 30px;
         border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 12px 40px rgba(0,0,0,0.4);">
        <h1 style="color: #fff; font-size: 3rem; margin: 0;">:material/attach_file: المرفقات</h1>
        <p style="color: #ccc; font-size: 1.2rem; margin-top: 8px;">أرشفة المستندات وربطها بالسجلات</p>
    </div>
    """, unsafe_allow_html=True)

    # ========== بطاقات إحصائية ==========
    all_attachments = att.get_attachments()
    total_count = len(all_attachments)
    total_size_kb = sum(a['file_size'] for a in all_attachments) / 1024 if all_attachments else 0

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; 
                    border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_BLUE};">:material/inventory_2:</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">عدد المرفقات</div>
            <div style="color:{ACCENT_BLUE}; font-size:1.8rem; font-weight:800;">{total_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; 
                    border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_GREEN};">:material/sd_storage:</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">الحجم الإجمالي</div>
            <div style="color:{ACCENT_GREEN}; font-size:1.8rem; font-weight:800;">{total_size_kb:.1f} KB</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2 = st.tabs([":material/upload: رفع مرفق", ":material/folder: المرفقات الحالية"])

    # ---------- تبويب الرفع ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>رفع مرفق جديد</h3>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("اختر الملف", type=["pdf", "jpg", "jpeg", "png", "xlsx", "docx", "zip"])
        
        col1, col2 = st.columns(2)
        with col1:
            linked_table = st.selectbox("نوع السجل", [
                "invoices", "journal_entries", "customers", "suppliers",
                "employees", "products", "cost_centers"
            ], format_func=lambda x: {
                "invoices": "فاتورة", "journal_entries": "قيد", "customers": "عميل",
                "suppliers": "مورد", "employees": "موظف", "products": "منتج",
                "cost_centers": "مركز تكلفة"
            }[x])
        with col2:
            linked_id = st.number_input("رقم السجل", min_value=1, step=1)
        
        if st.button("📤 رفع المرفق", type="primary", disabled=not uploaded_file):
            try:
                success, name = att.upload_attachment(
                    uploaded_file, linked_table, linked_id,
                    st.session_state.user.get('username', 'admin')
                )
                st.success(f"تم رفع الملف بنجاح")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # ---------- تبويب المرفقات الحالية ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>المرفقات الحالية</h3>", unsafe_allow_html=True)
        
        # فلترة
        filter_table = st.selectbox("تصفية حسب النوع", ["الكل", "فواتير", "قيود", "عملاء", "موردون", "موظفون", "منتجات", "مراكز تكلفة"])
        table_map = {"فواتير": "invoices", "قيود": "journal_entries", "عملاء": "customers", "موردون": "suppliers", "موظفون": "employees", "منتجات": "products", "مراكز تكلفة": "cost_centers"}
        link_table = table_map.get(filter_table) if filter_table != "الكل" else None
        
        attachments = att.get_attachments(linked_table=link_table)
        if attachments:
            df = pd.DataFrame(attachments)
            df['نوع السجل'] = df['linked_table'].map({
                "invoices": "فاتورة", "journal_entries": "قيد", "customers": "عميل",
                "suppliers": "مورد", "employees": "موظف", "products": "منتج",
                "cost_centers": "مركز تكلفة"
            })
            df_display = df.rename(columns={"id": "رقم", "original_name": "اسم الملف", "file_size": "الحجم (بايت)", "linked_id": "رقم السجل", "uploaded_at": "تاريخ الرفع"})
            st.dataframe(df_display[["رقم", "اسم الملف", "الحجم (بايت)", "نوع السجل", "رقم السجل", "تاريخ الرفع"]], use_container_width=True, hide_index=True)
            
            # تحميل وحذف
            attach_ids = [a['id'] for a in attachments]
            selected_id = st.selectbox("اختر مرفقًا", attach_ids, format_func=lambda x: next((a['original_name'] for a in attachments if a['id'] == x), ""))
            selected = att.get_attachment_by_id(selected_id)
            if selected and os.path.exists(selected['file_path']):
                col1, col2 = st.columns(2)
                with col1:
                    with open(selected['file_path'], "rb") as f:
                        st.download_button(":material/download: تحميل", f, file_name=selected['original_name'])
                with col2:
                    if st.button(":material/delete: حذف", key=f"del_{selected_id}"):
                        att.delete_attachment(selected_id)
                        st.success("تم الحذف")
                        st.rerun()
        else:
            st.info("لا توجد مرفقات")
