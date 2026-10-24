# ui_flet/pages/chart.py
import flet as ft
import pandas as pd
from services.chart_service import (
    create_accounts_table, add_account, get_accounts_tree,
    build_tree, get_account_options, delete_account
)
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

FUNCTIONAL_TYPES = {
    "بدون (حساب عادي/فرعي)": None,
    "النقدية/الصندوق (cash)": "cash",
    "البنك (bank)": "bank",
    "المخزون (inventory)": "inventory",
    "العملاء/مدينون": "accounts_receivable",
    "الموردون/دائنون": "accounts_payable",
    "إيرادات المبيعات (sales_revenue)": "sales_revenue",
    "تكلفة البضاعة المباعة (cogs)": "cogs",
    "ضريبة المبيعات/مخرجات (sales_tax)": "sales_tax",
    "ضريبة المشتريات/مدخلات (purchase_tax)": "purchase_tax",
    "المصروفات العامة (operating_expense)": "operating_expense",
    "رأس المال (capital)": "capital",
    "الأرباح المبقاة (retained_earnings)": "retained_earnings",
    "مصروف الإهلاك (depreciation_expense)": "depreciation_expense",
    "مجمع الإهلاك (accumulated_depreciation)": "accumulated_depreciation",
    "مصروف الرواتب (salaries_expense)": "salaries_expense",
    "المصروفات المستحقة (accrued_expenses)": "accrued_expenses",
    "أرباح/زيادة المخزون (inventory_gain)": "inventory_gain",
    "خسائر/نقص الجرد (inventory_loss)": "inventory_loss",
    "فروق أسعار الصرف (exchange_difference)": "exchange_difference",
}

def temp_data_table(df: pd.DataFrame) -> ft.Control:
    """جدول مؤقت سيتم استبداله بالدالة الشاملة لاحقاً"""
    if df is None or df.empty:
        return ft.Text("لا توجد بيانات للعرض", color=TEXT_SECONDARY)
    columns = [ft.DataColumn(ft.Text(str(c), weight=ft.FontWeight.BOLD)) for c in df.columns]
    rows = [ft.DataRow(cells=[ft.DataCell(ft.Text(str(v))) for v in r]) for _, r in df.iterrows()]
    return ft.Row(
        controls=[ft.DataTable(
            columns=columns, rows=rows, border=ft.border.all(1, GLASS_BORDER),
            border_radius=10, vertical_lines=ft.border.BorderSide(1, GLASS_BORDER),
            horizontal_lines=ft.border.BorderSide(1, GLASS_BORDER),
            heading_row_color=ft.colors.with_opacity(0.15, ft.colors.WHITE),
        )], scroll=ft.ScrollMode.AUTO, expand=True
    )

class ChartPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        
        try:
            create_accounts_table()
        except Exception as e:
            print(f"Accounts table error: {e}")

        self.header = ft.Text("🧾 شجرة الحسابات", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("إدارة الحسابات الهرمية والربط الوظيفي للنظام المحاسبي", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="📊 عرض الشجرة", content=self.build_tree_tab()),
                ft.Tab(text="➕ إضافة حساب", content=self.build_add_tab()),
            ],
            expand=True,
        )

        self.controls = [
            ft.Column([self.header, self.subtitle], spacing=5),
            ft.Divider(color=GLASS_BORDER),
            self.tabs
        ]

    def _current_username(self):
        # بما أننا لم نربط Auth في Flet بعد، نعيد admin مؤقتاً
        return "admin"

    # ============================================================
    # 1. عرض الشجرة
    # ============================================================
    def build_tree_tab(self):
        self.show_system_cb = ft.Checkbox(label="🔧 عرض النظامية", value=False, on_change=self.refresh_tree)
        self.tree_table_container = ft.Container()
        self.delete_confirm_id = None # لتخزين الحساب المراد حذفه
        
        self.refresh_tree(None)

        return ft.Column([
            ft.Row([
                ft.Text("شجرة الحسابات", color=ACCENT_BLUE, size=20, weight=ft.FontWeight.BOLD),
                self.show_system_cb
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.tree_table_container
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def refresh_tree(self, e):
        all_accounts = get_accounts_tree()
        if not all_accounts:
            self.tree_table_container.content = ft.Text("لا توجد حسابات.", color=TEXT_SECONDARY)
            self.page.update()
            return

        # فلترة النظامية
        if not self.show_system_cb.value:
            accounts = [a for a in all_accounts if not a.get('is_system', 0)]
        else:
            accounts = all_accounts

        if not accounts:
            self.tree_table_container.content = ft.Text("لا توجد حسابات عادية للعرض.", color=TEXT_SECONDARY)
            self.page.update()
            return

        # فرز الشجرة
        accounts = sorted(accounts, key=lambda x: (len(x["code"]), x["code"]))
        tree = build_tree(accounts)
        df = pd.DataFrame(tree)
        
        # تجهيز الأعمدة
        df["display_name"] = df.apply(lambda r: "    " * r["indent"] + r["name"], axis=1)
        df["account_type"] = df["account_type"].fillna("غير محدد")
        df["functional_type"] = df["functional_type"].fillna("-")
        df["نظامي"] = df["is_system"].apply(lambda x: "🔧" if x else "")
        
        # نأخذ الأعمدة المطلوبة فقط
        df_display = df[["code", "display_name", "level", "account_type", "functional_type", "نظامي"]].rename(columns={
            "code": "الكود", "display_name": "اسم الحساب", "level": "المستوى",
            "account_type": "التصنيف", "functional_type": "النوع الوظيفي"
        })

        # بناء الجدول وإدارة الحذف
        table = temp_data_table(df_display)
        
        # قسم الحذف
        delete_section = ft.Column([ft.Text("🗑️ إدارة الحسابات", weight=ft.FontWeight.BOLD, color=ACCENT_RED)])
        for acc in accounts:
            is_sys = acc.get('is_system', 0)
            row_controls = [
                ft.Text(f"🔧 {acc['code']} - {acc['name']} (نظامي)" if is_sys else f"{acc['code']} - {acc['name']}")
            ]
            
            if is_sys:
                row_controls.append(ft.IconButton(icon=ft.icons.LOCK, disabled=True, tooltip="حساب نظامي"))
            else:
                row_controls.append(ft.IconButton(
                    icon=ft.icons.DELETE, icon_color=ACCENT_RED,
                    tooltip="حذف", data=acc['id'], on_click=self.confirm_delete
                ))
            
            delete_section.controls.append(ft.Row(row_controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        self.tree_table_container.content = ft.Column([table, ft.Divider(color=GLASS_BORDER), delete_section])
        self.page.update()

    def confirm_delete(self, e):
        acc_id = e.control.data
        # إنشاء نافذة تأكيد
        def close_dlg(e):
            self.page.dialog.open = False
            self.page.update()

        def do_delete(e):
            success, message = delete_account(acc_id, deleted_by=self._current_username())
            self.page.dialog.open = False
            if success:
                self.page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=ACCENT_GREEN)
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=ACCENT_RED)
            self.page.snack_bar.open = True
            self.refresh_tree(None)

        dlg = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف"),
            content=ft.Text("هل أنت متأكد من حذف هذا الحساب؟"),
            actions=[
                ft.TextButton("إلغاء", on_click=close_dlg),
                ft.TextButton("نعم، احذف", on_click=do_delete, style=ft.ButtonStyle(color=ACCENT_RED)),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    # ============================================================
    # 2. إضافة حساب
    # ============================================================
    def build_add_tab(self):
        # تجهيز القوائم
        account_options = get_account_options()
        all_tree = get_accounts_tree()
        
        filtered_options = {}
        for label, pid in account_options.items():
            if pid is None:
                filtered_options[label] = pid
                continue
            acc = next((a for a in all_tree if a['id'] == pid), None)
            if acc and not acc.get('is_system', 0):
                filtered_options[label] = pid

        self.parent_dd = ft.Dropdown(
            label="الحساب الأب",
            options=[ft.dropdown.Option(key=str(pid) if pid else "None", text=label) for label, pid in filtered_options.items()],
            value="None"
        )
        
        self.acc_code = ft.TextField(label="كود الحساب", expand=True)
        self.acc_name = ft.TextField(label="اسم الحساب", expand=True)
        
        self.acc_type = ft.Dropdown(
            label="تصنيف الحساب الرئيسي",
            options=[ft.dropdown.Option(t) for t in ["", "Asset - أصل", "Liability - خصم", "Equity - حقوق ملكية", "Revenue - إيراد", "Expense - مصروف"]],
            value=""
        )
        
        self.acc_func = ft.Dropdown(
            label="النوع الوظيفي للنظام",
            options=[ft.dropdown.Option(k) for k in FUNCTIONAL_TYPES.keys()],
            value="بدون (حساب عادي/فرعي)"
        )

        def save_account(e):
            if not self.acc_code.value or not self.acc_name.value:
                self.page.snack_bar = ft.SnackBar(ft.Text("الكود والاسم مطلوبان"), bgcolor=ACCENT_RED)
                self.page.snack_bar.open = True
                self.page.update()
                return

            parent_id = None if self.parent_dd.value == "None" else int(self.parent_dd.value)
            
            type_map = {"Asset - أصل": "Asset", "Liability - خصم": "Liability", "Equity - حقوق ملكية": "Equity", "Revenue - إيراد": "Revenue", "Expense - مصروف": "Expense"}
            selected_type = type_map.get(self.acc_type.value)
            func_type = FUNCTIONAL_TYPES.get(self.acc_func.value)

            success, error = add_account(
                self.acc_code.value, self.acc_name.value, parent_id,
                selected_type, functional_type=func_type, created_by=self._current_username()
            )
            
            if success:
                self.page.snack_bar = ft.SnackBar(ft.Text(f"تم إضافة الحساب {self.acc_code.value} بنجاح!"), bgcolor=ACCENT_GREEN)
                self.acc_code.value = ""
                self.acc_name.value = ""
                self.refresh_tree(None) # تحديث القائمة في التبويب الأول
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text(error), bgcolor=ACCENT_RED)
            
            self.page.snack_bar.open = True
            self.page.update()

        form = ft.Column([
            self.parent_dd,
            ft.Row([self.acc_code, self.acc_name]),
            ft.Row([self.acc_type, self.acc_func]),
            ft.ElevatedButton("💾 حفظ الحساب", on_click=save_account, bgcolor=ACCENT_GREEN, color=ft.colors.WHITE)
        ], spacing=15)

        return ft.Container(content=form, padding=20)

# تأكد من استيراد ft.icons في أعلى الملف إذا لم تكن مضمنة في shared
