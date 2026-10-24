# ui_flet/pages/audit_log.py
import flet as ft
import pandas as pd
from datetime import date, timedelta
import os
from services.audit_service import create_audit_table, get_audit_logs, get_audit_stats
from database import get_connection, close_connection
from ui_flet.shared import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BLUE, ACCENT_GREEN,
    ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, GLASS_BG, GLASS_BORDER
)

try:
    from flet_plotly import PlotlyChart
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

ACCENT_CYAN = "#06B6D4"

def temp_data_table(df: pd.DataFrame) -> ft.Control:
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

def _get_distinct_values(column):
    conn = get_connection()
    try:
        rows = conn.execute(f"SELECT DISTINCT {column} FROM audit_log WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}").fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception: return []
    finally: close_connection(conn)

def _is_meaningful_column(series):
    for val in series:
        if val is None or pd.isna(val): continue
        s = str(val).strip().lower()
        if s in ("", "none", "—", "nan"): continue
        return True
    return False

def _drop_empty_columns(df, keep_always=("رقم", "المستخدم", "الإجراء", "التوقيت")):
    cols_to_keep, cols_dropped = [], []
    for col in df.columns:
        if col in keep_always or _is_meaningful_column(df[col]): cols_to_keep.append(col)
        else: cols_dropped.append(col)
    return df[cols_to_keep], cols_dropped

class AuditLogPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True
        self.selected_id = None
        self.filtered_logs = []
        self.df_display = pd.DataFrame()
        
        try: create_audit_table()
        except Exception as e: print(f"Audit init: {e}")

        self.header = ft.Text("🛡️ سجل التدقيق", size=30, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD)
        self.subtitle = ft.Text("كل ما يحدث في النظام مسجل هنا", color=TEXT_SECONDARY, size=14)

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text="📋 السجلات", content=self.build_main_tab()),
            ], expand=True,
        )
        self.controls = [ft.Column([self.header, self.subtitle], spacing=5), ft.Divider(color=GLASS_BORDER), self.tabs]

    def show_snackbar(self, text, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(text), bgcolor=color)
        self.page.snack_bar.open = True
        self.page.update()

    def kpi_card(self, icon, title, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Text(icon, size=24, color=color),
                ft.Text(title, color=TEXT_SECONDARY, size=11),
                ft.Text(str(value), color=color, size=16, weight=ft.FontWeight.BOLD)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3),
            bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER), border_radius=16, padding=12, expand=True
        )

    def build_main_tab(self):
        stats = get_audit_stats()
        top_user = stats['top_users'][0]['username'] if stats['top_users'] else "-"
        top_action = stats['top_actions'][0]['action'] if stats['top_actions'] else "-"
        if len(str(top_action)) > 20: top_action = str(top_action)[:18] + "..."

        cards_row = ft.Row([
            self.kpi_card("📋", "إجمالي السجلات", stats['total'], ACCENT_BLUE),
            self.kpi_card("📅", "عمليات اليوم", stats['today'], ACCENT_GREEN),
            self.kpi_card("👤", "أكثر مستخدم", top_user, ACCENT_ORANGE),
            self.kpi_card("⚡", "أكثر إجراء", top_action, ACCENT_PURPLE),
        ], spacing=10)

        # الفلاتر
        tables = ["الكل"] + _get_distinct_values("table_name")
        users = ["الكل"] + _get_distinct_values("username")
        
        self.table_dd = ft.Dropdown(label="📁 الجدول", options=[ft.dropdown.Option(t) for t in tables], value="الكل", expand=True)
        self.user_dd = ft.Dropdown(label="👤 المستخدم", options=[ft.dropdown.Option(u) for u in users], value="الكل", expand=True)
        self.date_dd = ft.Dropdown(label="📅 الفترة", options=[ft.dropdown.Option(d) for d in ["الكل", "اليوم", "آخر 7 أيام", "آخر 30 يوماً"]], value="الكل", expand=True)
        self.limit_input = ft.TextField(label="📊 الحد الأقصى", value="500", keyboard_type=ft.KeyboardType.NUMBER, width=120)
        self.search_input = ft.TextField(label="🔍 بحث سريع", hint_text="اكتب أي كلمة للبحث...", expand=True)
        
        self.apply_btn = ft.ElevatedButton("🔍 تطبيق الفلاتر", bgcolor=ACCENT_BLUE, color=ft.colors.WHITE, on_click=lambda e: self.apply_filters())

        # حاوية الجدول
        self.table_container = ft.Container()
        self.info_text = ft.Text("", color=TEXT_SECONDARY, size=12)
        
        # التصدير
        self.export_btn = ft.ElevatedButton("📥 تصدير CSV", bgcolor=ACCENT_GREEN, color=ft.colors.WHITE, on_click=self.export_csv)
        
        # الرسوم البيانية
        self.charts_container = ft.Column(spacing=15)
        
        # التفاصيل
        self.detail_dd = ft.Dropdown(label="اختر رقم السجل", expand=True, on_change=self.on_detail_select)
        self.detail_container = ft.Container()
        
        self.apply_filters()  # تحميل أولي

        return ft.Column([
            cards_row,
            ft.Divider(color=GLASS_BORDER),
            ft.Row([self.table_dd, self.user_dd, self.date_dd, self.limit_input]),
            ft.Row([self.search_input, self.apply_btn]),
            self.info_text,
            ft.Row([self.export_btn], alignment=ft.MainAxisAlignment.END),
            self.table_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("📊 تحليلات بصرية", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.charts_container,
            ft.Divider(color=GLASS_BORDER),
            ft.Text("🔍 تفاصيل سجل كامل", color=TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            self.detail_dd, self.detail_container
        ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=15)

    def apply_filters(self):
        try: limit = int(self.limit_input.value or 500)
        except ValueError: limit = 500
        
        filter_table = None if self.table_dd.value == "الكل" else self.table_dd.value
        filter_user = None if self.user_dd.value == "الكل" else self.user_dd.value
        
        logs = get_audit_logs(filter_table=filter_table, filter_user=filter_user, limit=limit)
        
        # الفلترة النصية
        if self.search_input.value and self.search_input.value.strip():
            pattern = self.search_input.value.strip().lower()
            logs = [log for log in logs if pattern in str(log.get("action", "")).lower() or pattern in str(log.get("table_name", "")).lower() or pattern in str(log.get("old_value", "")).lower() or pattern in str(log.get("new_value", "")).lower() or pattern in str(log.get("username", "")).lower()]
        
        # الفلترة الزمنية
        date_range = self.date_dd.value
        today = date.today()
        date_from = date_to = None
        if date_range == "اليوم": date_from = date_to = today.strftime("%Y-%m-%d")
        elif date_range == "آخر 7 أيام": date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d"); date_to = today.strftime("%Y-%m-%d")
        elif date_range == "آخر 30 يوماً": date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d"); date_to = today.strftime("%Y-%m-%d")
        
        if date_from:
            logs = [log for log in logs if date_from <= str(log.get("timestamp", ""))[:10] <= date_to]

        self.filtered_logs = logs
        if not logs:
            self.table_container.content = ft.Text("ℹ️ لا توجد سجلات مطابقة للبحث.", color=TEXT_SECONDARY)
            self.info_text.value = ""
            self.page.update(); return

        df = pd.DataFrame(logs)
        # تعويض القيم
        df["record_id"] = df["record_id"].apply(lambda x: "—" if pd.isna(x) or x is None else str(x))
        df["old_value"] = df["old_value"].apply(lambda x: "—" if pd.isna(x) or not str(x).strip() or str(x).lower() == "none" else str(x))
        df["new_value"] = df["new_value"].apply(lambda x: "—" if pd.isna(x) or not str(x).strip() or str(x).lower() == "none" else str(x))
        df["username"] = df["username"].fillna("—").replace("", "—")
        df["action"] = df["action"].fillna("—")
        df["table_name"] = df["table_name"].fillna("—")
        
        df = df.rename(columns={"id": "رقم", "username": "المستخدم", "action": "الإجراء", "table_name": "الجدول", "record_id": "رقم السجل", "old_value": "القيمة القديمة", "new_value": "القيمة الجديدة", "timestamp": "التوقيت"})
        
        all_cols = [c for c in ["رقم", "المستخدم", "الإجراء", "الجدول", "رقم السجل", "القيمة القديمة", "القيمة الجديدة", "التوقيت"] if c in df.columns]
        df = df[all_cols]
        
        keep_always = ("رقم", "المستخدم", "الإجراء", "التوقيت")
        df_display, dropped = _drop_empty_columns(df, keep_always=keep_always)
        self.df_display = df_display
        
        self.table_container.content = temp_data_table(df_display)
        if dropped:
            self.info_text.value = f"ℹ️ تم إخفاء الأعمدة الفارغة: {', '.join(dropped)}"
        else:
            self.info_text.value = f"عرض {len(df_display)} سجل"

        # تحديث قائمة التفاصيل
        self.detail_dd.options = [ft.dropdown.Option(key=str(r['id']), text=f"#{r['id']}") for r in logs]
        if logs: self.detail_dd.value = str(logs[0]['id']); self.on_detail_select(None)

        self.build_charts(logs)
        self.page.update()

    def build_charts(self, logs):
        if not PLOTLY_AVAILABLE:
            self.charts_container.controls = [ft.Text("⚠️ لتثبيت الرسوم البيانية: pip install flet-plotly", color=ACCENT_ORANGE)]
            return

        df = pd.DataFrame(logs).copy()
        df["date"] = df["timestamp"].astype(str).str[:10]
        df["hour"] = df["timestamp"].astype(str).str[11:13]
        
        charts = []
        
        # 1. حسب اليوم
        daily = df.groupby("date").size().reset_index(name="count")
        if not daily.empty:
            fig = px.bar(daily, x="date", y="count", color_discrete_sequence=[ACCENT_CYAN])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=250, margin=dict(t=20, b=20, l=20, r=20))
            charts.append(ft.Container(content=PlotlyChart(fig, expand=True), height=250))
        
        # 2. حسب الجدول
        table_counts = df.groupby("table_name").size().reset_index(name="count").sort_values("count", ascending=False).head(10)
        if not table_counts.empty:
            fig = px.bar(table_counts, x="table_name", y="count", color_discrete_sequence=[ACCENT_BLUE])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=250, margin=dict(t=20, b=20, l=20, r=20))
            charts.append(ft.Container(content=PlotlyChart(fig, expand=True), height=250))
        
        # 3. حسب الساعة
        hour_counts = df.groupby("hour").size().reset_index(name="count").sort_values("hour")
        if not hour_counts.empty:
            fig = px.bar(hour_counts, x="hour", y="count", color_discrete_sequence=[ACCENT_ORANGE])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=250, margin=dict(t=20, b=20, l=20, r=20))
            charts.append(ft.Container(content=PlotlyChart(fig, expand=True), height=250))
        
        # 4. حسب المستخدم
        user_counts = df.groupby("username").size().reset_index(name="count").sort_values("count", ascending=False).head(10)
        if not user_counts.empty:
            fig = px.bar(user_counts, x="username", y="count", color_discrete_sequence=[ACCENT_PURPLE])
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=250, margin=dict(t=20, b=20, l=20, r=20))
            charts.append(ft.Container(content=PlotlyChart(fig, expand=True), height=250))

        self.charts_container.controls = charts

    def on_detail_select(self, e):
        if not self.detail_dd.value or not self.filtered_logs: return
        log = next((l for l in self.filtered_logs if str(l['id']) == self.detail_dd.value), None)
        if not log: return
        
        detail = pd.DataFrame([
            {"الحقل": "المستخدم", "القيمة": log.get("username") or "—"},
            {"الحقل": "الإجراء", "القيمة": log.get("action") or "—"},
            {"الحقل": "الجدول", "القيمة": log.get("table_name") or "—"},
            {"الحقل": "رقم السجل", "القيمة": str(log.get("record_id") or "—")},
            {"الحقل": "القيمة القديمة", "القيمة": log.get("old_value") or "—"},
            {"الحقل": "القيمة الجديدة", "القيمة": log.get("new_value") or "—"},
            {"الحقل": "التوقيت", "القيمة": log.get("timestamp") or "—"},
        ])
        self.detail_container.content = temp_data_table(detail)
        self.page.update()

    def export_csv(self, e):
        if self.df_display.empty:
            self.show_snackbar("لا توجد بيانات للتصدير", ACCENT_RED); return
        
        # حفظ في مجلد المستخدم
        user_home = os.path.expanduser("~")
        file_path = os.path.join(user_home, f"audit_log_{date.today().strftime('%Y%m%d')}.csv")
        try:
            self.df_display.to_csv(file_path, index=False, encoding="utf-8-sig")
            self.show_snackbar(f"✅ تم التصدير إلى: {file_path}", ACCENT_GREEN)
        except Exception as ex:
            self.show_snackbar(f"❌ فشل التصدير: {ex}", ACCENT_RED)
