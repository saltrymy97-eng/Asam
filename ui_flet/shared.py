# ui_flet/shared.py
import flet as ft
import pandas as pd

# ========== ألوان التصميم (مطابقة لما في Streamlit) ==========
GLASS_BG = ft.colors.with_opacity(0.12, ft.colors.WHITE)
GLASS_BORDER = ft.colors.with_opacity(0.25, ft.colors.WHITE)
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

# ========== دالة مساعدة لتحويل DataFrame إلى جدول Flet ==========
def build_data_table(df: pd.DataFrame) -> ft.Control:
    """
    تحول جدول Pandas إلى جدول Flet احترافي.
    ستوفر هذه الدالة مئات الأسطر عند ترحيل الصفحات.
    """
    if df is None or df.empty:
        return ft.Text("لا توجد بيانات للعرض", color=TEXT_SECONDARY)

    columns = [ft.DataColumn(ft.Text(str(col), weight=ft.FontWeight.BOLD)) for col in df.columns]
    rows = []
    for _, row in df.iterrows():
        cells = [ft.DataCell(ft.Text(str(val))) for val in row]
        rows.append(ft.DataRow(cells=cells))

    return ft.DataTable(
        columns=columns,
        rows=rows,
        border=ft.border.all(1, GLASS_BORDER),
        border_radius=10,
        vertical_lines=ft.border.BorderSide(1, GLASS_BORDER),
        horizontal_lines=ft.border.BorderSide(1, GLASS_BORDER),
        heading_row_color=GLASS_BG,
        data_row_color={"hovered": ft.colors.with_opacity(0.1, ft.colors.WHITE)},
  )
