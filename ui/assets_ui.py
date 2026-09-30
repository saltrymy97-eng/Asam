# ui/assets_ui.py – واجهة الأصول الثابتة والإهلاكات (v2.1)
# ✅ دعم صندوق/بنك + فحص الرصيد
# ✅ v2.1: نسبة الإهلاك قابلة للتحكم + إصلاح تجمد زر الحفظ
import streamlit as st
import pandas as pd
from datetime import date, datetime
from services.assets_service import (
    create_assets_tables,
    add_asset,
    get_all_assets,
    run_depreciation,
    run_all_depreciations,
    get_depreciation_history,
    get_assets_summary,
    update_asset_depreciation,
)
from services.expenses_service import get_payment_accounts


# ========== ألوان التصميم ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"


def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">إدارة الأصول الثابتة وجدولة الإهلاكات</p>
    </div>""", unsafe_allow_html=True)


def h3(title, color=BL):
    st.markdown(f"""<h3 style="color:{color};text-align:right;margin-bottom:1rem;">{title}</h3>""",
                unsafe_allow_html=True)


def kpi_card(icon, title, value, color):
    return f"""<div style="background:rgba(255,255,255,0.10);backdrop-filter:blur(12px);
        border:1px solid rgba(255,255,255,0.20);border-radius:16px;padding:1.2rem;
        text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.37);margin-bottom:0.8rem;">
        <div style="font-size:2rem;margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{S};font-size:0.8rem;">{title}</div>
        <div style="color:{color};font-size:1.6rem;font-weight:800;">{value}</div>
    </div>"""


def _format_account_label(acc):
    """تنسيق عرض الحساب مع الرصيد والنوع"""
    icon = "💵" if acc["type"] == "cash" else "🏦"
    return (
        f"{icon} {acc['name']} ({acc['currency']}) — "
        f"الرصيد: {acc['balance']:,.2f}"
    )


def _reset_add_form():
    """إعادة تعيين حقول نموذج الإضافة"""
    keys = [
        "add_asset_name", "add_asset_category", "add_asset_date",
        "add_asset_cost", "add_asset_salvage", "add_asset_method",
        "add_asset_dep_mode", "add_asset_useful_life",
        "add_asset_annual_rate", "add_asset_manual_monthly",
        "add_asset_notes", "add_asset_payment_choice", "add_asset_account_sel",
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]


def show():
    create_assets_tables()
    h1("🏢 الأصول الثابتة والإهلاكات")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 الأصول",
        "➕ إضافة أصل",
        "📉 تشغيل الإهلاك",
        "📊 لوحة التحكم",
    ])

    # ============================================================
    # تبويب 1: الأصول + تعديل الإهلاك
    # ============================================================
    with tab1:
        h3("قائمة الأصول الثابتة", BL)
        assets = get_all_assets()
        if assets:
            df = pd.DataFrame(assets)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أصول ثابتة بعد")

        # ============================================================
        # ✅ تعديل إهلاك أصل موجود
        # ============================================================
        if assets:
            st.markdown("---")
            h3("✏️ تعديل إهلاك أصل موجود", OR)

            asset_labels = [
                f"#{a['id']} — {a['name']} "
                f"(إهلاك شهري: {a.get('monthly_depreciation') or 0:,.2f})"
                for a in assets
            ]
            selected_label = st.selectbox(
                "اختر الأصل",
                asset_labels,
                key="edit_dep_asset_sel"
            )
            idx = asset_labels.index(selected_label)
            sel_asset = assets[idx]

            # عرض الوضع الحالي
            col1, col2, col3 = st.columns(3)
            col1.metric("النسبة السنوية الحالية",
                        f"{sel_asset.get('annual_depreciation_rate') or 0:.2f}%")
            col2.metric("الإهلاك الشهري الحالي",
                        f"{sel_asset.get('monthly_depreciation') or 0:,.2f}")
            col3.metric("العمر الإنتاجي",
                        f"{sel_asset.get('useful_life_years') or 0} سنة")

            with st.expander("🛠️ تعديل الإهلاك", expanded=False):
                st.caption(
                    "⚠️ التعديل يسري على الإهلاكات القادمة فقط، "
                    "ولا يعيد حساب الإهلاكات السابقة."
                )

                new_mode = st.radio(
                    "طريقة التحديد الجديدة",
                    ["📅 بالعمر الإنتاجي", "📊 بنسبة سنوية %",
                     "💵 بقيمة شهرية يدوية"],
                    horizontal=True,
                    key="edit_dep_mode"
                )

                new_life = None
                new_rate = None
                new_manual = None

                if new_mode.startswith("📅"):
                    new_life = st.number_input(
                        "العمر الإنتاجي الجديد (سنوات)",
                        min_value=1, max_value=50,
                        value=int(sel_asset.get('useful_life_years') or 5),
                        key="edit_life"
                    )
                    new_rate = 0.0
                    new_manual = 0.0
                elif new_mode.startswith("📊"):
                    new_rate = st.number_input(
                        "النسبة السنوية الجديدة (%)",
                        min_value=0.1, max_value=100.0,
                        value=float(sel_asset.get('annual_depreciation_rate') or 20.0),
                        step=0.5,
                        key="edit_rate"
                    )
                    new_manual = 0.0
                else:
                    new_manual = st.number_input(
                        "القيمة الشهرية الجديدة",
                        min_value=0.01,
                        value=float(sel_asset.get('monthly_depreciation') or 100.0),
                        step=10.0,
                        key="edit_manual"
                    )
                    new_rate = 0.0

                if st.button("💾 حفظ التعديل", key="save_dep_edit",
                             type="primary"):
                    ok, msg = update_asset_depreciation(
                        asset_id=sel_asset['id'],
                        annual_depreciation_rate=new_rate,
                        manual_monthly_depreciation=new_manual,
                        useful_life_years=new_life,
                        updated_by=st.session_state.user.get('username', 'admin'),
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        st.markdown("---")
        h3("سجل الإهلاكات", PR)
        history = get_depreciation_history()
        if history:
            df = pd.DataFrame(history)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد إهلاكات مسجلة بعد")

    # ============================================================
    # تبويب 2: إضافة أصل (بدون st.form — لحل مشكلة الزر)
    # ============================================================
    with tab2:
        h3("إضافة أصل ثابت جديد", GR)

        # ============ البيانات الأساسية ============
        col_a, col_b = st.columns(2)
        name = col_a.text_input("اسم الأصل", key="add_asset_name")
        category = col_b.selectbox(
            "الفئة",
            ["أثاث ومعدات", "مباني", "آلات", "مركبات",
             "أجهزة كمبيوتر", "أخرى"],
            key="add_asset_category"
        )

        col_c, col_d = st.columns(2)
        purchase_date = col_c.date_input(
            "تاريخ الشراء", value=date.today(), key="add_asset_date"
        )
        purchase_cost = col_d.number_input(
            "تكلفة الشراء", min_value=0.0, step=100.0,
            value=0.0, key="add_asset_cost"
        )

        col_e, col_f = st.columns(2)
        salvage_value = col_e.number_input(
            "قيمة الخردة (الإنقاذ)", min_value=0.0, step=100.0,
            value=0.0, key="add_asset_salvage"
        )
        method = col_f.selectbox(
            "طريقة الإهلاك", ["قسط ثابت", "متناقص"],
            key="add_asset_method"
        )

        # ============ طريقة احتساب الإهلاك ============
        st.markdown("---")
        st.markdown("### 📉 طريقة احتساب الإهلاك الشهري")

        dep_mode = st.radio(
            "اختر طريقة التحديد",
            [
                "📅 بالعمر الإنتاجي (سنوات)",
                "📊 بنسبة سنوية %",
                "💵 بقيمة شهرية يدوية",
            ],
            horizontal=True,
            key="add_asset_dep_mode"
        )

        useful_life = 5
        annual_rate = 0.0
        manual_monthly = 0.0

        if dep_mode.startswith("📅"):
            useful_life = st.number_input(
                "العمر الإنتاجي (سنوات)",
                min_value=1, max_value=50, value=5, step=1,
                key="add_asset_useful_life"
            )
            if purchase_cost > 0 and salvage_value < purchase_cost:
                auto_monthly = (purchase_cost - salvage_value) / (useful_life * 12)
                st.info(f"💡 الإهلاك الشهري المتوقع: **{auto_monthly:,.2f}**")

        elif dep_mode.startswith("📊"):
            annual_rate = st.number_input(
                "النسبة السنوية (%)",
                min_value=0.1, max_value=100.0, value=20.0, step=0.5,
                key="add_asset_annual_rate",
                help="مثال: 20% تعني إهلاك 20% من القيمة سنوياً"
            )
            if purchase_cost > 0 and salvage_value < purchase_cost:
                auto_monthly = (purchase_cost - salvage_value) * (annual_rate / 100) / 12
                st.info(
                    f"💡 الإهلاك الشهري المتوقع: **{auto_monthly:,.2f}** "
                    f"(سنوي: **{auto_monthly * 12:,.2f}**)"
                )
        else:  # قيمة يدوية
            manual_monthly = st.number_input(
                "القيمة الشهرية للإهلاك",
                min_value=0.01, value=100.0, step=10.0,
                key="add_asset_manual_monthly"
            )
            if purchase_cost > 0 and salvage_value < purchase_cost:
                months_needed = (purchase_cost - salvage_value) / manual_monthly
                st.info(
                    f"💡 سيُستنفد الأصل خلال **{months_needed:,.1f}** شهر "
                    f"(~{months_needed/12:,.1f} سنة)"
                )

        notes = st.text_area("ملاحظات", key="add_asset_notes")

        # ============ طريقة الدفع ============
        st.markdown("---")
        st.markdown("### 💳 كيف تم شراء الأصل؟")

        payment_choice = st.radio(
            "طريقة الدفع",
            ["بنكي (تحويل)", "نقدي (من صندوق)", "بدون قيد شراء"],
            horizontal=True,
            key="add_asset_payment_choice"
        )

        payment_account_code = None
        payment_method_for_service = None
        balance_ok = True
        selected_acc = None

        if "بدون" not in payment_choice:
            all_accounts = get_payment_accounts()

            if "بنكي" in payment_choice:
                filtered = [a for a in all_accounts if a["type"] == "bank"]
                payment_method_for_service = "bank"
                if not filtered:
                    st.error("⚠️ لا يوجد حساب بنكي نشط.")
                    balance_ok = False
            else:
                filtered = [a for a in all_accounts if a["type"] == "cash"]
                payment_method_for_service = "cash"
                if not filtered:
                    st.error("⚠️ لا يوجد صندوق نشط.")
                    balance_ok = False

            if filtered:
                labels = [_format_account_label(a) for a in filtered]
                selected_label = st.selectbox(
                    "من أي حساب تم الدفع؟",
                    labels,
                    key="add_asset_account_sel"
                )
                idx = labels.index(selected_label)
                selected_acc = filtered[idx]
                payment_account_code = selected_acc["code"]

                # ✅ فحص الرصيد الفوري
                if purchase_cost > 0:
                    if purchase_cost > selected_acc["balance"]:
                        st.error(
                            f"⚠️ **الرصيد غير كافٍ**\n\n"
                            f"المتاح في **{selected_acc['name']}**: "
                            f"**{selected_acc['balance']:,.2f}** {selected_acc['currency']}\n\n"
                            f"المطلوب: **{purchase_cost:,.2f}** {selected_acc['currency']}\n\n"
                            f"❌ لن تتم العملية"
                        )
                        balance_ok = False
                    else:
                        st.info(
                            f"✅ الرصيد كافٍ — سيتبقى "
                            f"**{selected_acc['balance'] - purchase_cost:,.2f}** "
                            f"{selected_acc['currency']}"
                        )

        # ============ فحص نهائي قبل الحفظ ============
        st.markdown("---")

        # قائمة الأخطاء
        errors = []
        if not name.strip():
            errors.append("اسم الأصل مطلوب")
        if purchase_cost <= 0:
            errors.append("تكلفة الشراء يجب أن تكون أكبر من صفر")
        if salvage_value >= purchase_cost and purchase_cost > 0:
            errors.append("قيمة الخردة يجب أن تكون أقل من تكلفة الشراء")
        if not balance_ok:
            errors.append("الرصيد غير كافٍ في الحساب المختار")

        if errors:
            st.warning("⚠️ " + " | ".join(errors))

        can_submit = len(errors) == 0

        col_save, col_reset = st.columns([3, 1])
        with col_save:
            if st.button(
                "💾 حفظ الأصل",
                type="primary",
                disabled=not can_submit,
                use_container_width=True,
                key="add_asset_submit_btn"
            ):
                try:
                    asset_id, err = add_asset(
                        name=name,
                        category=category,
                        purchase_date=purchase_date.strftime("%Y-%m-%d"),
                        purchase_cost=purchase_cost,
                        salvage_value=salvage_value,
                        useful_life_years=useful_life,
                        method=method,
                        notes=notes,
                        payment_account_code=payment_account_code,
                        payment_method=payment_method_for_service,
                        created_by=st.session_state.user.get('username', 'admin'),
                        annual_depreciation_rate=annual_rate,
                        manual_monthly_depreciation=manual_monthly,
                    )
                    if err:
                        st.error(f"❌ فشل: {err}")
                    else:
                        st.success(f"✅ تم إضافة الأصل '{name}' برقم {asset_id}")
                        _reset_add_form()
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ خطأ غير متوقع: {e}")

        with col_reset:
            if st.button("🔄 تفريغ", use_container_width=True,
                         key="add_asset_reset_btn"):
                _reset_add_form()
                st.rerun()

    # ============================================================
    # تبويب 3: تشغيل الإهلاك
    # ============================================================
    with tab3:
        h3("تشغيل الإهلاك الشهري", OR)

        assets = get_all_assets()
        active_assets = [
            a for a in assets
            if a['status'] == 'نشط' and (a.get('monthly_depreciation') or 0) > 0
        ]

        # ✅ تنبيه الأصول غير المُهلكة هذا الشهر
        current_month = date.today().strftime("%Y-%m")
        not_depreciated = [
            a['name'] for a in active_assets
            if (a.get('last_depreciation_date') or "")[:7] != current_month
        ]

        if not_depreciated:
            st.warning(
                f"⚠️ **{len(not_depreciated)}** أصل لم يُهلك بعد هذا الشهر: "
                f"{', '.join(not_depreciated[:5])}"
                + (" ..." if len(not_depreciated) > 5 else "")
            )
        elif active_assets:
            st.success("✅ جميع الأصول النشطة تم إهلاكها هذا الشهر")

        if "saving_all_dep" not in st.session_state:
            st.session_state.saving_all_dep = False

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "🚀 تشغيل إهلاك جميع الأصول النشطة",
                type="primary",
                disabled=st.session_state.saving_all_dep or not active_assets,
                use_container_width=True,
                key="run_all_dep_btn"
            ):
                st.session_state.saving_all_dep = True
                st.rerun()

            if st.session_state.saving_all_dep:
                results = run_all_depreciations()
                success_count = sum(1 for r in results if r[1])
                st.success(f"✅ تم تشغيل الإهلاك لـ {success_count} أصل")
                st.session_state.saving_all_dep = False
                st.rerun()

        if "saving_single_dep" not in st.session_state:
            st.session_state.saving_single_dep = False

        with col2:
            if active_assets:
                asset_names = [
                    f"{a['name']} (إهلاك شهري: {a.get('monthly_depreciation') or 0:,.2f})"
                    for a in active_assets
                ]
                selected = st.selectbox(
                    "اختر أصلاً للتشغيل الفردي",
                    asset_names,
                    key="single_dep_sel"
                )
                if st.button(
                    "📉 تشغيل إهلاك هذا الأصل",
                    disabled=st.session_state.saving_single_dep,
                    use_container_width=True,
                    key="run_single_dep_btn"
                ):
                    st.session_state.saving_single_dep = True
                    st.rerun()

                if st.session_state.saving_single_dep:
                    idx = asset_names.index(selected)
                    success, msg = run_depreciation(active_assets[idx]['id'])
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
                    st.session_state.saving_single_dep = False
                    st.rerun()
            else:
                st.info("لا توجد أصول نشطة قابلة للإهلاك")

    # ============================================================
    # تبويب 4: لوحة التحكم
    # ============================================================
    with tab4:
        h3("ملخص الأصول الثابتة", CY)
        summary = get_assets_summary()
        assets = get_all_assets()  # ✅ إعادة الجلب لضمان عدم الاعتماد على tab1

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                kpi_card("🏢", "إجمالي الأصول",
                         summary['total_count'], BL),
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                kpi_card("💰", "تكلفة الشراء",
                         f"{summary['total_cost']:,.0f}", GR),
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                kpi_card("📉", "الإهلاك المتراكم",
                         f"{summary['total_depreciation']:,.0f}", OR),
                unsafe_allow_html=True
            )
        with col4:
            st.markdown(
                kpi_card("📊", "القيمة الدفترية",
                         f"{summary['total_book_value']:,.0f}", PR),
                unsafe_allow_html=True
            )

        st.markdown("---")
        h3("الأصول النشطة", GR)
        active = [a for a in assets if a['status'] == 'نشط']
        if active:
            df = pd.DataFrame(active)
            cols = ['name', 'category', 'purchase_cost',
                    'monthly_depreciation', 'accumulated_depreciation',
                    'book_value']
            cols = [c for c in cols if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أصول نشطة")
