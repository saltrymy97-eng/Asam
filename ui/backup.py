# ui/backup.py - النسخ الاحتياطي (واجهة زجاجية فخمة + تحميل النسخ)
import streamlit as st
import pandas as pd
import os
from services.backup_service import (
    create_backup,
    get_backup_list,
    restore_backup,
    get_backup_stats,
    BACKUP_DIR
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
ACCENT_PURPLE = "#8B5CF6"
ACCENT_RED = "#EF4444"

def show():
    st.markdown(f"""
    <div style="margin-bottom: 2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_BLUE};">💾 النسخ الاحتياطي</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">حماية بيانات النظام من الضياع</p>
    </div>
    """, unsafe_allow_html=True)

    # ---------- بطاقات إحصائية ----------
    stats = get_backup_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_BLUE};">📋</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">عدد النسخ</div>
            <div style="color:{ACCENT_BLUE}; font-size:1.8rem; font-weight:800;">{stats['total']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_GREEN};">🕐</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">آخر نسخة</div>
            <div style="color:{ACCENT_GREEN}; font-size:1.2rem; font-weight:800;">{stats['latest_time']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background:{GLASS_BG}; backdrop-filter:blur(10px); border:1px solid {GLASS_BORDER}; border-radius:16px; padding:1.2rem; text-align:center; box-shadow:{GLASS_SHADOW};">
            <div style="font-size:2rem; color:{ACCENT_ORANGE};">📦</div>
            <div style="color:{TEXT_SECONDARY}; font-size:0.9rem;">حجم آخر نسخة</div>
            <div style="color:{ACCENT_ORANGE}; font-size:1.8rem; font-weight:800;">{stats['latest_size']:.1f} KB</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ---------- إنشاء نسخة احتياطية ----------
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>إنشاء نسخة احتياطية جديدة</h3>", unsafe_allow_html=True)
    with col2:
        if st.button("💾 إنشاء نسخة الآن", type="primary", use_container_width=True):
            filename, size = create_backup()
            st.success(f"✅ تم إنشاء النسخة: {filename} ({size:.1f} KB)")
            st.rerun()

    st.markdown("---")

    # ---------- سجل النسخ الاحتياطية ----------
    st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📋 سجل النسخ الاحتياطية</h3>", unsafe_allow_html=True)
    backups = get_backup_list()
    if backups:
        df = pd.DataFrame(backups)
        df = df.rename(columns={
            "id": "رقم",
            "filename": "اسم الملف",
            "size_kb": "الحجم (KB)",
            "created_at": "تاريخ الإنشاء",
            "type": "النوع"
        })
        st.dataframe(df[["رقم", "اسم الملف", "الحجم (KB)", "تاريخ الإنشاء", "النوع"]], use_container_width=True, hide_index=True)

        # ---------- تحميل نسخة على الجهاز ----------
        st.markdown("---")
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>📥 تحميل نسخة على الجهاز</h3>", unsafe_allow_html=True)
        
        backup_files = [b['filename'] for b in backups]
        selected_download = st.selectbox("اختر نسخة للتحميل", backup_files, key="download_select")
        
        filepath = os.path.join(BACKUP_DIR, selected_download)
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                st.download_button(
                    label=f"📥 تحميل {selected_download}",
                    data=f,
                    file_name=selected_download,
                    mime="application/octet-stream",
                    key="download_btn"
                )
        else:
            st.error("الملف غير موجود على القرص. ربما تم حذفه.")

        # ---------- استعادة نسخة احتياطية ----------
        st.markdown("---")
        st.markdown(f"<h3 style='color:{TEXT_PRIMARY};'>🔄 استعادة نسخة احتياطية</h3>", unsafe_allow_html=True)
        
        selected_backup = st.selectbox("اختر نسخة للاستعادة", backup_files, key="restore_select")
        
        if st.button("⚠️ استعادة هذه النسخة", type="secondary"):
            # إجراء الاستعادة يتطلب تأكيداً
            st.warning("سيتم استبدال قاعدة البيانات الحالية. هل أنت متأكد؟")
            if st.button("نعم، استعد النسخة", key="confirm_restore"):
                success = restore_backup(selected_backup)
                if success:
                    st.success(f"✅ تم استعادة النسخة: {selected_backup} بنجاح")
                    st.rerun()
                else:
                    st.error("فشل في استعادة النسخة")
    else:
        st.info("ℹ️ لا توجد نسخ احتياطية بعد")
