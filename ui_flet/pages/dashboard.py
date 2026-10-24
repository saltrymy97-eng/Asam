# ui_flet/pages/dashboard.py
import flet as ft
import pandas as pd
from datetime import datetime
from services.dashboard_service import (
    get_kpi_cards, get_quick_stats, get_alerts, get_inventory_by_category,
    get_monthly_sales, get_top_products, get_low_stock_products,
    get_recent_invoices, get_recent_activities
)
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

class DashboardPage(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.expand = True

        kpi = get_kpi_cards()
        quick = get_quick_stats()
        alerts = get_alerts()

        # ============================================================
        # 1. الهيدر الترحيبي
        # ============================================================
        header = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("ENTERPRISE HUB", color=ACCENT_PURPLE, size=11, weight=ft.FontWeight.BOLD),
                    ft.Text(f"مرحباً، مدير النظام", color=ft.colors.WHITE, size=26, weight=ft.FontWeight.BOLD),
                    ft.Text(f"نظرة عامة على مؤشرات الأداء، {datetime.now().strftime('%A %d %B %Y')}", color=TEXT_SECONDARY, size=13),
                ], spacing=3),
                ft.Container(
                    content=ft.Text("📊", size=40),
                    bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
                    border=ft.border.all(1, GLASS_BORDER),
                    border_radius=20, width=80, height=80,
                    alignment=ft.alignment.center
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                colors=["#171725", "#0A0A12"]
            ),
            border=ft.border.all(1, GLASS_BORDER),
            border_radius=24, padding=25, margin=ft.margin.only(bottom=20)
        )

        # ============================================================
        # 2. الإحصائيات السريعة
        # ============================================================
        def card(title, value, icon, color, delta=""):
            return ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(title, color=TEXT_SECONDARY, size=11, weight=ft.FontWeight.BOLD),
                        ft.Text(str(value), color=TEXT_PRIMARY, size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(delta, color=color, size=11) if delta else ft.Container()
                    ], spacing=3, expand=True),
                    ft.Container(
                        content=ft.Text(icon, size=24),
                        bgcolor=ft.colors.with_opacity(0.03, ft.colors.WHITE),
                        border_radius=16, width=50, height=50, alignment=ft.alignment.center
                    )
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER),
                border_radius=18, padding=18, expand=True
            )

        stock_status = "يحتاج طلب عاجل" if quick['low_stock'] > 0 else "الكل آمن ومستقر"
        stock_color = ACCENT_RED if quick['low_stock'] > 0 else ACCENT_GREEN

        quick_cards = ft.Row([
            card("مبيعات اليوم", f"{quick['today_sales']:,.0f} ر.ي", "💰", ACCENT_GREEN, "↑ 12% عن أمس"),
            card("مشتريات اليوم", f"{quick['today_purchases']:,.0f} ر.ي", "🛒", ACCENT_RED, "↓ 5% عن أمس"),
            card("منتجات منخفضة", str(quick['low_stock']), "⚠️", stock_color, stock_status),
            card("شركاء جدد", str(quick['total_customers']), "👥", ACCENT_BLUE, "+3 هذا الشهر"),
        ], spacing=15)

        # ============================================================
        # 3. التنبيهات
        # ============================================================
        alerts_controls = []
        if alerts:
            for alert in alerts:
                alerts_controls.append(ft.Container(
                    content=ft.Row([
                        ft.Text(alert['icon'], size=18),
                        ft.Text(f"{alert['title']}: {alert['message']}", color=TEXT_PRIMARY, size=13)
                    ]),
                    bgcolor=ft.colors.with_opacity(0.06, ACCENT_ORANGE),
                    border=ft.border.only(left=ft.border.BorderSide(4, ACCENT_ORANGE)),
                    border_radius=10, padding=12
                ))

        # ============================================================
        # 4. الأداء المالي
        # ============================================================
        net_val = kpi['net_income']
        financial_cards = ft.Row([
            card("إجمالي المبيعات", f"{kpi['total_sales']:,.0f}", "💵", ACCENT_GREEN),
            card("إجمالي المشتريات", f"{kpi['total_purchases']:,.0f}", "📦", ACCENT_RED),
            card("صافي الأرباح", f"{net_val:,.0f}", "💎", ACCENT_GREEN if net_val >= 0 else ACCENT_RED),
            card("دليل المنتجات", str(kpi['products_count']), "🏷️", ACCENT_BLUE),
            card("قاعدة العملاء", str(kpi['customers_count']), "👥", ACCENT_ORANGE),
        ], spacing=15)

        # ============================================================
        # 5. الرسوم البيانية
        # ============================================================
        charts_row = ft.Row(spacing=15)
        if PLOTLY_AVAILABLE:
            # رسم المبيعات الشهرية
            sales_data = get_monthly_sales()
            if sales_data:
                df_sales = pd.DataFrame(sales_data).sort_values('month')
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_sales['month'], y=df_sales['total'], marker_color=ACCENT_BLUE, name='المبيعات'))
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=TEXT_PRIMARY), margin=dict(t=10, b=10, l=10, r=10),
                    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
                )
                charts_row.controls.append(ft.Container(
                    content=PlotlyChart(fig, expand=True),
                    bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER),
                    border_radius=16, padding=15, expand=True, height=320
                ))
            else:
                charts_row.controls.append(ft.Container(content=ft.Text("لا توجد سجلات مالية", color=TEXT_SECONDARY), padding=20))

            # رسم توزيع المخزون
            inv_data = get_inventory_by_category()
            if inv_data:
                df_inv = pd.DataFrame(inv_data)
                fig2 = px.pie(df_inv, names='category', values='total', hole=0.7,
                              color_discrete_sequence=['#8B5CF6', '#3B82F6', '#06B6D4', '#10B981', '#F59E0B'])
                fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT_PRIMARY),
                                   margin=dict(t=10, b=10, l=10, r=10))
                charts_row.controls.append(ft.Container(
                    content=PlotlyChart(fig2, expand=True),
                    bgcolor=GLASS_BG, border=ft.border.all(1, GLASS_BORDER),
                    border_radius=16, padding=15, expand=True, height=320
                ))
            else:
                charts_row.controls.append(ft.Container(content=ft.Text("المخازن فارغة", color=TEXT_SECONDARY), padding=20))
        else:
            charts_row.controls.append(ft.Container(
                content=ft.Text("⚠️ لتثبيت الرسوم البيانية: pip install flet-plotly", color=ACCENT_ORANGE),
                padding=20
            ))

        # ============================================================
        # 6. القوائم التنفيذية
        # ============================================================
        low_stock_controls = []
        low = get_low_stock_products()
        if low:
            for item in low:
                low_stock_controls.append(ft.Container(
                    content=ft.Row([
                        ft.Text(item['name'], color=TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                        ft.Container(
                            content=ft.Text(f"{item['quantity']} / {item['reorder_level']}", color=ACCENT_RED, size=12, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.colors.with_opacity(0.15, ACCENT_RED),
                            border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=3)
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    bgcolor=ft.colors.with_opacity(0.04, ACCENT_RED),
                    border=ft.border.all(1, ft.colors.with_opacity(0.1, ACCENT_RED)),
                    border_radius=14, padding=14
                ))
        else:
            low_stock_controls.append(ft.Container(
                content=ft.Text("🛡️ تأمين جرد المخازن مكتمل. جميع الأصناف بمستويات آمنة.", color=ACCENT_GREEN),
                padding=20, alignment=ft.alignment.center
            ))

        activities_controls = []
        activities = get_recent_activities()
        if activities:
            for act in activities[:5]:
                action = str(act.get('action', ''))
                dot_color = ACCENT_PURPLE if 'فاتورة' in action else (ACCENT_BLUE if 'قيد' in action else ACCENT_ORANGE)
                time_value = act.get('time') or act.get('created_at') or act.get('timestamp') or ''
                activities_controls.append(ft.Container(
                    content=ft.Row([
                        ft.Container(width=8, height=8, bgcolor=dot_color, border_radius=4),
                        ft.Text(action, color=TEXT_PRIMARY, size=13, expand=True),
                        ft.Text(str(time_value), color=TEXT_SECONDARY, size=11)
                    ]),
                    padding=ft.padding.symmetric(vertical=8, horizontal=12),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, GLASS_BORDER))
                ))
        else:
            activities_controls.append(ft.Container(
                content=ft.Text("لا توجد مستجدات في سجل العمليات حالياً", color=TEXT_SECONDARY),
                padding=20, alignment=ft.alignment.center
            ))

        lists_row = ft.Row([
            ft.Column([
                ft.Text("⚠️ رقابة المخزون والحدود الحرجة", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                ft.Column(low_stock_controls, spacing=8)
            ], expand=True),
            ft.Column([
                ft.Text("🕐 سجل العمليات والأنشطة الأخيرة", color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                ft.Column(activities_controls, spacing=5)
            ], expand=True)
        ], spacing=20)

        # ============================================================
        # التجميع النهائي
        # ============================================================
        self.controls = [
            header,
            ft.Text("الإحصائيات السريعة", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            quick_cards,
            *alerts_controls,
            ft.Text("📊 الأداء العام والمالي", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            financial_cards,
            ft.Text("الرسوم البيانية الاستراتيجية", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            charts_row,
            ft.Text("القوائم التنفيذية", color=TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            lists_row,
        ]
        self.scroll = ft.ScrollMode.AUTO
        self.spacing = 15
