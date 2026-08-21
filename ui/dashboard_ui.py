# ui/dashboard_ui.py – لوحة معلومات ERP (نسخة الفخامة المطلقة - Premium Glassmorphism)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# ================= ألوان الهوية الفاخرة (Premium Palette) =================
BG_DEEP = "#05070A"           # أسود ليلي عميق جداً
GLASS_BG = "rgba(18, 23, 35, 0.45)" # زجاج داكن شبه شفاف
GLASS_BORDER = "rgba(255, 255, 255, 0.08)" # حدود زجاجية ناعمة

GOLD_ACCENT = "#D4AF37"       # ذهبي ملكي (Royal Gold)
GOLD_GLOW = "rgba(212, 175, 55, 0.4)"
PURPLE_ACCENT = "#9333EA"     # بنفسجي مخملي
PURPLE_GLOW = "rgba(147, 51, 234, 0.4)"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#64748B"

def render_html(html_code: str):
    st.markdown(html_code, unsafe_allow_html=True)

def inject_premium_css():
    """CSS فائق الفخامة يدمج الزجاج المصنفر، الإضاءة المحيطية، والحركات الناعمة"""
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');

    * {{ font-family: 'Tajawal', sans-serif !important; box-sizing: border-box; }}

    /* خلفية النظام - إضاءة محيطية مخفية (Ambient Glow) */
    .stApp {{
        background-color: {BG_DEEP} !important;
        background-image: 
            radial-gradient(circle at 15% 0%, {PURPLE_GLOW} 0%, transparent 25%),
            radial-gradient(circle at 85% 100%, {GOLD_GLOW} 0%, transparent 25%) !important;
        background-attachment: fixed;
    }}

    .block-container {{ direction: rtl; text-align: right; padding-top: 1rem !important; max-width: 1400px; }}
    #MainMenu, footer, header {{ visibility: hidden; display: none; }}

    /* ================= النصوص الفاخرة ================= */
    .premium-title {{
        color: {TEXT_PRIMARY};
        font-size: clamp(2rem, 5vw, 3.2rem);
        font-weight: 900;
        letter-spacing: -1px;
        margin: 0;
        background: linear-gradient(to left, #FFFFFF, #94A3B8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 10px 30px rgba(147, 51, 234, 0.3);
    }}

    .premium-subtitle {{
        color: {GOLD_ACCENT};
        font-size: 1.1rem;
        font-weight: 500;
        letter-spacing: 1px;
        margin-top: 5px;
        text-shadow: 0 0 15px {GOLD_GLOW};
    }}

    /* ================= البطاقات الزجاجية (Glassmorphism Cards) ================= */
    .glass-card {{
        background: {GLASS_BG};
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid {GLASS_BORDER};
        border-top: 1px solid rgba(255,255,255,0.15); /* إضاءة علوية طفيفة */
        border-radius: 24px;
        padding: 1.8rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }}

    /* تأثير الانعكاس عند تمرير الماوس */
    .glass-card::before {{
        content: ""; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent);
        transition: left 0.7s ease;
    }}
    
    .glass-card:hover::before {{ left: 150%; }}
    .glass-card:hover {{
        transform: translateY(-5px);
        border-color: rgba(147, 51, 234, 0.3);
        box-shadow: 0 30px 60px -10px rgba(147, 51, 234, 0.2);
    }}

    /* ================= الأزرار الاحترافية ================= */
    .nav-container {{
        display: flex; gap: 12px; justify-content: center; margin: 2rem 0 3rem 0;
        background: rgba(10, 15, 25, 0.5); padding: 8px; border-radius: 100px;
        border: 1px solid {GLASS_BORDER};
        backdrop-filter: blur(10px);
        width: fit-content; margin-left: auto; margin-right: auto;
    }}

    .nav-btn {{
        padding: 12px 28px; border-radius: 100px; font-weight: 700; font-size: 0.95rem;
        transition: all 0.3s ease; display: inline-flex; align-items: center; gap: 8px;
        cursor: pointer; color: {TEXT_PRIMARY}; border: 1px solid transparent;
    }}

    .nav-btn.active {{
        background: linear-gradient(135deg, {GOLD_ACCENT}, #B48600);
        color: #000 !important;
        box-shadow: 0 0 20px {GOLD_GLOW};
    }}

    .nav-btn:not(.active):hover {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid {GLASS_BORDER};
    }}

    /* ================= الجداول الفاخرة ================= */
    .lux-table-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 16px 20px; margin-bottom: 8px;
        background: rgba(255,255,255,0.02);
        border: 1px solid transparent;
        border-radius: 16px;
        transition: all 0.3s ease;
    }}
    .lux-table-row:hover {{
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        transform: scale(1.01);
    }}
    
    .status-badge {{
        padding: 4px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: 700;
    }}
    </style>
    """
    render_html(css)

def build_metric(label, value, icon, trend, trend_color, glow_color):
    return f"""
    <div class="glass-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
            <div style="color: {TEXT_SECONDARY}; font-weight: 600; font-size: 1rem;">{label}</div>
            <div style="background: linear-gradient(135deg, {glow_color}20, transparent); padding: 10px; border-radius: 12px; border: 1px solid {glow_color}40; color: {glow_color}; font-size: 1.2rem; box-shadow: 0 0 15px {glow_color}20;">
                {icon}
            </div>
        </div>
        <div style="color: {TEXT_PRIMARY}; font-size: 2.2rem; font-weight: 900; letter-spacing: 0.5px; margin-bottom: 0.5rem; text-shadow: 0 2px 10px rgba(255,255,255,0.1);">
            {value}
        </div>
        <div style="display: inline-flex; align-items: center; gap: 6px; background: {trend_color}15; color: {trend_color}; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 700;">
            {trend}
        </div>
    </div>
    """

def show():
    inject_premium_css()
    
    # 1. الترويسة الرئيسية (مركزة ومبهرة)
    render_html(f"""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 class="premium-title">مركز التحكم الاستراتيجي</h1>
        <div class="premium-subtitle">نظرة مالية ومخزنية شاملة • {datetime.now().strftime('%d %B %Y')}</div>
    </div>
    """)

    # 2. شريط التنقل الزجاجي
    render_html(f"""
    <div class="nav-container">
        <div class="nav-btn active"><span>💰</span> إدارة الصندوق</div>
        <div class="nav-btn"><span>📦</span> التسويات المخزنية</div>
        <div class="nav-btn"><span>🔀</span> فروق الصرف</div>
        <div class="nav-btn"><span>🏛️</span> حوكمة</div>
    </div>
    """)

    # 3. شبكة المؤشرات (4 بطاقات فائقة الجودة)
    render_html("<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;'>")
    render_html(build_metric("السيولة النقدية المتاحة", "185,400 <span style='font-size:1.2rem; color:#64748B;'>YER</span>", "💵", "↑ 5.4% نمو أسبوعي", "#10B981", GOLD_ACCENT))
    render_html(build_metric("العمليات المنفذة اليوم", "24", "⚡", "معدل طبيعي", "#3B82F6", PURPLE_ACCENT))
    render_html(build_metric("تسويات معلقة", "3", "⚠️", "يتطلب إجراء فوري", "#EF4444", "#EF4444"))
    render_html(build_metric("فروق تقييم العملات", "-5,450 <span style='font-size:1.2rem; color:#64748B;'>SAR</span>", "🔀", "تمت المعالجة الآلية", "#A855F7", PURPLE_ACCENT))
    render_html("</div>")

    # 4. الرسوم البيانية المتطورة (لا توجد خطوط شبكة مزعجة، منحنيات ناعمة)
    col1, col2 = st.columns([6, 4])
    chart_font = dict(color=TEXT_SECONDARY, family='Tajawal', size=13)

    with col1:
        render_html(f"<h3 style='color: {TEXT_PRIMARY}; font-weight: 800; font-size: 1.3rem; margin-bottom: 1rem; border-right: 4px solid {PURPLE_ACCENT}; padding-right: 10px;'>التدفقات النقدية (آخر أسبوع)</h3>")
        
        # رسم بياني خطي احترافي (Spline Area)
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=['السبت', 'الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس'],
            y=[12000, 19000, 15000, 28000, 22000, 34000],
            fill='tozeroy',
            mode='lines+markers',
            line=dict(color=PURPLE_ACCENT, width=4, shape='spline'),
            marker=dict(size=10, color=GOLD_ACCENT, line=dict(width=2, color=BG_DEEP)),
            fillcolor='rgba(147, 51, 234, 0.1)'
        ))
        fig1.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=chart_font, margin=dict(t=10, b=10, l=0, r=0),
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor=GLASS_BORDER, zeroline=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})

    with col2:
        render_html(f"<h3 style='color: {TEXT_PRIMARY}; font-weight: 800; font-size: 1.3rem; margin-bottom: 1rem; border-right: 4px solid {GOLD_ACCENT}; padding-right: 10px;'>مراكز العملات الأجنبية</h3>")
        
        # رسم بياني دائري احترافي (Thin Donut)
        fig2 = go.Figure(data=[go.Pie(
            labels=['دولار أمريكي (USD)', 'ريال سعودي (SAR)', 'يورو (EUR)'],
            values=[55, 35, 10],
            hole=0.8, # حلقة نحيفة جداً لفخامة أكثر
            marker=dict(colors=[PURPLE_ACCENT, GOLD_ACCENT, '#3B82F6'], line=dict(color=BG_DEEP, width=4))
        )])
        fig2.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=chart_font, margin=dict(t=10, b=10, l=10, r=10),
            showlegend=True, legend=dict(orientation="h", y=-0.1)
        )
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

    # 5. سجل العمليات (تصميم قوائم فاخر بدلاً من الجداول التقليدية)
    render_html(f"""
    <div class="glass-card" style="margin-top: 1rem; padding: 2rem;">
        <h3 style="color: {TEXT_PRIMARY}; font-weight: 800; font-size: 1.4rem; margin-top: 0; margin-bottom: 1.5rem;">
            سجل العمليات والتسويات الحديثة
        </h3>
        
        <!-- صف العناوين -->
        <div style="display: flex; justify-content: space-between; padding: 0 20px 10px 20px; color: {TEXT_SECONDARY}; font-weight: 600; font-size: 0.9rem; border-bottom: 1px solid {GLASS_BORDER}; margin-bottom: 10px;">
            <div style="flex: 1;">المرجع</div>
            <div style="flex: 2;">نوع العملية</div>
            <div style="flex: 1; text-align: left;">القيمة</div>
        </div>

        <!-- السجلات -->
        <div class="lux-table-row">
            <div style="flex: 1; color: {TEXT_SECONDARY}; font-family: monospace !important;">#REC-010000</div>
            <div style="flex: 2; color: {TEXT_PRIMARY}; font-weight: 600;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#EF4444; margin-left:8px;"></span>
                تسوية عجز مخزني
            </div>
            <div style="flex: 1; text-align: left; color: #EF4444; font-weight: 800;">- 100.00 <span style="font-size:0.8rem;">SAR</span></div>
        </div>

        <div class="lux-table-row">
            <div style="flex: 1; color: {TEXT_SECONDARY}; font-family: monospace !important;">#REC-010002</div>
            <div style="flex: 2; color: {TEXT_PRIMARY}; font-weight: 600;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#10B981; margin-left:8px;"></span>
                إعادة تقييم عملة (أرباح)
            </div>
            <div style="flex: 1; text-align: left; color: #10B981; font-weight: 800;">+ 450.00 <span style="font-size:0.8rem;">USD</span></div>
        </div>

        <div class="lux-table-row">
            <div style="flex: 1; color: {TEXT_SECONDARY}; font-family: monospace !important;">#REC-010005</div>
            <div style="flex: 2; color: {TEXT_PRIMARY}; font-weight: 600;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:{GOLD_ACCENT}; margin-left:8px;"></span>
                حركة صندوق منصرفة
            </div>
            <div style="flex: 1; text-align: left; color: {GOLD_ACCENT}; font-weight: 800;">- 5,000.00 <span style="font-size:0.8rem;">YER</span></div>
        </div>
    </div>
    """)
