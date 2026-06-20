# ui/backup.py - واجهة النسخ الاحتياطي الفاخرة (إصدار إنتاجي)
import streamlit as st
import pandas as pd
import os
import zipfile
import io
from services.backup_service import (
    create_backup, get_backup_list, restore_backup, get_backup_stats,
    delete_old_backups, start_scheduler, stop_scheduler,
    get_all_tables, BACKUP_DIR, METADATA_DIR
)

# ========== ألوان التصميم الملكي ==========
GOLD = "#D4AF37"
GOLD_LIGHT = "#FCF6BA"
GOLD_DARK = "#AA771C"
BG_CARD = "rgba(20, 20, 10, 0.7)"
BORDER_GOLD = "rgba(212, 175, 55, 0.2)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_GREEN = "#10B981"
ACCENT_RED = "#EF4444"
ACCENT_BLUE = "#3B82F6"
ACCENT_ORANGE = "#F59E0B"
ACCENT_PURPLE = "#8B5CF6"

def glass_card(title, value, icon, color, sub_text=""):
    """بطاقة زجاجية ذهبية"""
    return f"""
    <div style="
        background: linear-gradient(145deg, rgba(20, 20, 10, 0.7), rgba(10, 10, 5, 0.85));
        backdrop-filter: blur(30px); -webkit-backdrop-filter: blur(30px);
        border: 1px solid rgba(212, 175, 55, 0.2); border-top: 1px solid rgba(212, 175, 55, 0.35);
        border-radius: 24px; padding: 1.5rem; text-align: center; box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4), 0 0 15px rgba(212,175,55,0.05);
        transition: all 0.5s ease; margin-bottom: 1rem;
    ">
        <div style="font-size:2.2rem; margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.85rem; margin-bottom:4px;">{title}</div>
        <div style="color:{color}; font-size:1.8rem; font-weight:800;">{value}</div>
        <div style="color:{TEXT_SECONDARY}; font-size:0.75rem; margin-top:4px;">{sub_text}</div>
    </div>
    """

def show():
    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{GOLD}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {GOLD};">💾 مركز النسخ الاحتياطي</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">حماية مؤسسية متكاملة مع تشفير وجدولة وتتبع كامل</p>
    </div>
    """, unsafe_allow_html=True)

    stats = get_backup_stats()

    # ---------- تنبيه هام إذا تأخر النسخ ----------
    if stats.get('alert'):
        st.warning(f"⚠️ {stats.get('alert_msg')}")

    # ---------- صف البطاقات الإحصائية ----------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(glass_card("إجمالي النسخ", str(stats['total']), "📋", ACCENT_BLUE), unsafe_allow_html=True)
    with col2:
        st.markdown(glass_card("آخر نسخة", stats['latest_time'], "🕐", ACCENT_GREEN), unsafe_allow_html=True)
    with col3:
        st.markdown(glass_card("حجم آخر نسخة", f"{stats['latest_size']:.1f} KB", "📦", ACCENT_ORANGE), unsafe_allow_html=True)
    with col4:
        st.markdown(glass_card("آخر مستخدم", stats.get('latest_user', 'غير معروف'), "👤", ACCENT_PURPLE), unsafe_allow_html=True)

    st.markdown("---")

    # ---------- إنشاء نسخة جديدة (إعدادات متقدمة) ----------
    st.markdown(f"<h3 style='color:{GOLD}'>✨ إنشاء نسخة احتياطية جديدة</h3>", unsafe_allow_html=True)
    
    with st.expander("⚙️ إعدادات النسخ المتقدمة", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            backup_user = st.text_input("اسم المستخدم", value="مدير النظام", help="سيتم تسجيل هذا الاسم في سجل النسخة")
            backup_type = st.selectbox("نوع النسخة", ["يدوي", "تلقائي", "قبل تحديث"])
        with col2:
            encrypt = st.checkbox("🔐 تشفير النسخة (AES-256)", value=False)
            compress = st.checkbox("📦 ضغط النسخة (ZIP)", value=True)
        
        # اختيار جداول محددة (اختياري)
        all_tables = get_all_tables()
        selected_tables = st.multiselect(
            "اختر جداول محددة للنسخ (اتركه فارغًا لنسخ الكل)",
            options=all_tables,
            default=[],
            help="إذا تركت الحقل فارغًا، سيتم نسخ جميع الجداول."
        )
        notes = st.text_area("ملاحظات", placeholder="أي ملاحظات تود إضافتها لهذه النسخة...")

        if st.button("🚀 إنشاء النسخة الآن", type="primary", use_container_width=True):
            with st.spinner("جاري إنشاء النسخة..."):
                try:
                    filename, size = create_backup(
                        user=backup_user,
                        backup_type=backup_type,
                        tables=selected_tables if selected_tables else None,
                        encrypt=encrypt,
                        compress=compress,
                        notes=notes
                    )
                    st.success(f"✅ تم إنشاء النسخة بنجاح: {filename} ({size:.1f} KB)")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ فشل إنشاء النسخة: {e}")

    # ---------- أدوات النظام (جدولة وحذف تلقائي) ----------
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("⏰ تشغيل النسخ التلقائي اليومي", use_container_width=True):
            start_scheduler()
            st.success("✅ تم تشغيل المجدول التلقائي")
    with col_b:
        if st.button("⏹️ إيقاف النسخ التلقائي", use_container_width=True):
            stop_scheduler()
            st.info("⏹️ تم إيقاف المجدول التلقائي")
    with col_c:
        if st.button("🗑️ حذف النسخ القديمة (أقدم من 30 يومًا)", use_container_width=True):
            delete_old_backups()
            st.success("✅ تم حذف النسخ القديمة")
            st.rerun()

    st.markdown("---")

    # ---------- سجل النسخ الاحتياطية ----------
    st.markdown(f"<h3 style='color:{GOLD}'>📋 سجل النسخ الاحتياطية</h3>", unsafe_allow_html=True)
    backups = get_backup_list()
    if backups:
        df = pd.DataFrame(backups)
        # تنسيق العرض
        df_display = df.rename(columns={
            "id": "رقم",
            "filename": "اسم الملف",
            "size_kb": "الحجم (KB)",
            "created_at": "تاريخ الإنشاء",
            "type": "النوع",
            "user": "المستخدم",
            "tables_count": "عدد الجداول",
            "is_encrypted": "مشفر",
            "is_compressed": "مضغوط",
            "notes": "ملاحظات"
        })
        st.dataframe(
            df_display[["رقم", "اسم الملف", "تاريخ الإنشاء", "النوع", "المستخدم", "الحجم (KB)", "عدد الجداول", "مشفر", "مضغوط", "ملاحظات"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "مشفر": st.column_config.CheckboxColumn(),
                "مضغوط": st.column_config.CheckboxColumn(),
            }
        )

        # ---------- استعادة نسخة ----------
        st.markdown("---")
        st.markdown(f"<h3 style='color:{ACCENT_RED}'>🔄 استعادة نسخة احتياطية</h3>", unsafe_allow_html=True)
        selected_restore = st.selectbox("اختر نسخة للاستعادة", [b['filename'] for b in backups], key="restore_select")
        
        if st.button("⚠️ استعادة هذه النسخة (سيتم استبدال قاعدة البيانات الحالية)", type="secondary"):
            with st.spinner("جاري الاستعادة..."):
                success, msg = restore_backup(selected_restore)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        # ---------- تحميل نسخة ----------
        st.markdown("---")
        st.markdown(f"<h3 style='color:{ACCENT_BLUE}'>📥 تحميل نسخة</h3>", unsafe_allow_html=True)
        selected_download = st.selectbox("اختر نسخة للتحميل", [b['filename'] for b in backups], key="download_select")
        
        filepath = os.path.join(BACKUP_DIR, selected_download)
        if os.path.exists(filepath):
            # تحميل الملف مباشرة بصيغته الأصلية دون إعادة ضغط
            with open(filepath, "rb") as f:
                file_data = f.read()
            
            # تحديد نوع MIME المناسب
            if selected_download.endswith('.zip'):
                mime_type = "application/zip"
            elif selected_download.endswith('.enc'):
                mime_type = "application/octet-stream"
            else:
                mime_type = "application/octet-stream"
            
            st.download_button(
                label=f"📥 تحميل {selected_download}",
                data=file_data,
                file_name=selected_download,
                mime=mime_type,
                key="download_btn"
            )
        else:
            st.error("الملف غير موجود على القرص.")

        # ---------- رفع نسخة من الجهاز ----------
        st.markdown("---")
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE}'>📤 استيراد نسخة احتياطية</h3>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("ارفع ملف قاعدة البيانات (.db أو .zip)", type=["db", "zip", "enc"], key="upload_backup")
        if uploaded_file:
            save_path = os.path.join(BACKUP_DIR, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            st.success(f"✅ تم رفع الملف: {uploaded_file.name}")
            
            # --- منطق ذكي للتعامل مع الملف المرفوع ---
            file_to_restore = None

            # 1. إذا كان الملف .db مباشرة
            if uploaded_file.name.endswith('.db'):
                file_to_restore = uploaded_file.name

            # 2. إذا كان الملف .zip، نبحث داخله عن .db
            elif uploaded_file.name.endswith('.zip'):
                with zipfile.ZipFile(save_path, 'r') as zf:
                    db_files = [f for f in zf.namelist() if f.endswith('.db')]
                    if db_files:
                        zf.extract(db_files[0], BACKUP_DIR)
                        file_to_restore = db_files[0]
                        st.success(f"✅ تم استخراج: {file_to_restore}")

            # 3. إذا كان الملف .enc (مشفر)، نعتمد على restore_backup لفك التشفير
            elif uploaded_file.name.endswith('.enc'):
                file_to_restore = uploaded_file.name

            if file_to_restore:
                if st.button("🔄 استعادة النسخة المستوردة", key="restore_uploaded"):
                    success, msg = restore_backup(file_to_restore)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(f"❌ فشلت الاستعادة: {msg}")
            else:
                st.error("لم يتم العثور على ملف قاعدة بيانات (.db) صالح في الملف المرفوع.")
    else:
        st.info("ℹ️ لا توجد نسخ احتياطية بعد. قم بإنشاء أول نسخة الآن.")
