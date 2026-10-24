# ui_flet/shared.py
import flet as ft
import pandas as pd

# ============================================================
# 🎨 LIGHT GLASS LUXURY THEME
# ============================================================

TEXT_PRIMARY   = "#0F172A"
TEXT_SECONDARY = "#475569"
TEXT_MUTED     = "#94A3B8"

BG_MAIN           = "#F1F5F9"
BG_GRADIENT_START = "#EFF6FF"
BG_GRADIENT_END   = "#F5F3FF"

GLASS_BG        = ft.colors.with_opacity(0.65, ft.colors.WHITE)
GLASS_BG_SOFT   = ft.colors.with_opacity(0.45, ft.colors.WHITE)
GLASS_BORDER    = ft.colors.with_opacity(0.35, "#94A3B8")
GLASS_HEADER    = ft.colors.with_opacity(0.85, "#F1F5F9")
GLASS_ROW_ALT   = ft.colors.with_opacity(0.30, "#E2E8F0")
GLASS_HOVER     = ft.colors.with_opacity(0.45, "#DBEAFE")

SHADOW_SOFT = ft.BoxShadow(
    blur_radius=20,
    color=ft.colors.with_opacity(0.06, "#0F172A"),
    offset=ft.Offset(0, 4),
)
SHADOW_MEDIUM = ft.BoxShadow(
    blur_radius=30,
    color=ft.colors.with_opacity(0.10, "#0F172A"),
    offset=ft.Offset(0, 8),
)
SHADOW_LARGE = ft.BoxShadow(
    blur_radius=40,
    color=ft.colors.with_opacity(0.14, "#0F172A"),
    offset=ft.Offset(0, 12),
)

ACCENT_BLUE   = "#2563EB"
ACCENT_GREEN  = "#059669"
ACCENT_ORANGE = "#D97706"
ACCENT_RED    = "#DC2626"
ACCENT_PURPLE = "#7C3AED"
ACCENT_CYAN   = "#0891B2"
ACCENT_PINK   = "#DB2777"
ACCENT_GOLD   = "#B45309"


# ============================================================
# 📊 جدول بيانات احترافي عريض (Odoo / Xtra-like)
# ============================================================

MIN_COL_WIDTH = 140

def build_data_table(df: pd.DataFrame, min_col_width: int = MIN_COL_WIDTH) -> ft.Control:
    if df is None or df.empty:
        return ft.Container(
            content=ft.Text("لا توجد بيانات للعرض", color=TEXT_SECONDARY, size=14),
            padding=30,
            alignment=ft.alignment.center,
        )

    columns = []
    for col_name in df.columns:
        columns.append(
            ft.DataColumn(
                label=ft.Container(
                    content=ft.Text(
                        str(col_name),
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY,
                        size=13,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    width=min_col_width,
                    alignment=ft.alignment.center_right,
                )
            )
        )

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        row_bg = GLASS_ROW_ALT if (i % 2 == 1) else None
        cells = []
        for val in row:
            display = "" if pd.isna(val) else str(val)
            cells.append(
                ft.DataCell(
                    ft.Container(
                        content=ft.Text(
                            display,
                            color=TEXT_PRIMARY,
                            size=12,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        width=min_col_width,
                        alignment=ft.alignment.center_right,
                    )
                )
            )
        rows.append(ft.DataRow(cells=cells, color=row_bg))

    table = ft.DataTable(
        columns=columns,
        rows=rows,
        border=ft.border.all(1, GLASS_BORDER),
        border_radius=14,
        vertical_lines=ft.border.BorderSide(1, GLASS_BORDER),
        horizontal_lines=ft.border.BorderSide(1, GLASS_BORDER),
        heading_row_color=GLASS_HEADER,
        heading_row_height=52,
        data_row_min_height=46,
        data_row_max_height=54,
        column_spacing=12,
        horizontal_margin=16,
    )

    return ft.Container(
        content=ft.Row(
            controls=[table],
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
        ),
        expand=True,
        border_radius=14,
        shadow=SHADOW_MEDIUM,
        bgcolor=GLASS_BG,
        padding=8,
    )

# --- توافق مع الاسم القديم ---
temp_data_table = build_data_table


# ============================================================
# 💎 Helper: بطاقة زجاجية
# ============================================================
def glass_card(content, padding: int = 20, expand: bool = False) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=GLASS_BG,
        border=ft.border.all(1, GLASS_BORDER),
        border_radius=20,
        padding=padding,
        shadow=SHADOW_SOFT,
        expand=expand,
    )


# ============================================================
# 📈 Helper: بطاقة KPI
# ============================================================
def kpi_card(icon: str, title: str, value: str, color: str = ACCENT_BLUE) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Text(icon, size=28),
            ft.Text(title, size=11, color=TEXT_SECONDARY, weight=ft.FontWeight.W_500),
            ft.Text(value, size=20, color=color, weight=ft.FontWeight.BOLD),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        bgcolor=GLASS_BG,
        border=ft.border.all(1, GLASS_BORDER),
        border_radius=20,
        padding=18,
        shadow=SHADOW_SOFT,
        expand=True,
    )
