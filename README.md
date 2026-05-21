```markdown
# XD ERP – AI-Powered Open Source ERP

![XD ERP](https://img.shields.io/badge/XD-ERP-8B5CF6?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57+-red?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey?style=flat-square)
![Groq AI](https://img.shields.io/badge/AI-Groq_Llama_3.3-purple?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Ready_for_Production-brightgreen?style=flat-square)

> **"XD – Where Accounting Meets AI"**

**XD ERP** is a complete, enterprise‑grade Enterprise Resource Planning system built entirely in **Python**. It delivers a full accounting cycle, inventory, sales, purchasing, HR, and a unique **8‑function AI assistant** powered by Groq. The entire system features a stunning **glassmorphism UI**, strict **transaction management**, and a clean **Services/UI separation** – ready for real business use or as a hackathon‑winning project.

---

## 🎯 Why XD ERP?

| Problem | Solution |
|---------|----------|
| No free, Arabic‑native ERP for SMBs | **XD ERP – open source, Arabic‑first** |
| Most ERPs lack true AI integration | **8 AI functions live inside the system** |
| Complex, expensive licensing | **Zero cost, MIT license** |
| Difficult to customize | **Clean Python codebase, modular design** |

---

## 🚀 Key Features

### 📊 Accounting & Finance
- **Full accounting cycle** – journal entries, general ledger, trial balance
- **Chart of accounts** – hierarchical 4‑level tree with parent/child
- **Income statement & balance sheet** – auto‑generated from journal entries
- **Period closing** – lock months/years to prevent unauthorized edits
- **Closing entries** – automatic revenue/expense closing at year‑end
- **FIFO inventory valuation** – batch tracking, automatic cost calculation

### 🛒 Sales & Purchasing
- **Sales invoices** – create invoices, auto‑deduct stock, log audit trails
- **Purchase invoices** – auto‑add stock, supplier management
- **Customer & Supplier management**
- **Returns management** – sales returns, purchase returns with reason tracking

### 👥 HR & Payroll
- **Employee management** – records, attendance tracking
- **Payroll** – salary config (basic + allowances – deductions)
- **Auto‑generated journal entries** on payroll runs

### 🛡️ Security & Compliance
- **Audit log** – every create/update/delete tracked with username & timestamp
- **Role‑based access control** – admin, accountant, inventory manager, cashier
- **Backup & restore** – one‑click backup, download, and restore
- **Transaction management** – all financial operations use `BEGIN/COMMIT/ROLLBACK`

### 🤖 AI Assistant (8 Functions)
| Tab | Function |
|-----|----------|
| 🧠 Smart Accountant | Deep chat with live system data |
| 📊 Financial Analyst | Comprehensive ratio analysis & recommendations |
| 📦 Inventory Predictor | Stock depletion forecasting & purchase suggestions |
| 💬 Employee Chat | Salary & personal info queries |
| 📝 Auto Journal Entry | Arabic text → compound journal entry → save to system |
| 🔍 Fraud Detection | Audits entries for suspicious patterns |
| 🔮 Future Forecasting | Sales, cash flow, inventory & profit predictions |
| 📈 Deep Analysis | Financial ratios, trends, top customers/suppliers |

### 🎨 UI/UX
- **Glassmorphism design** – modern, blur‑effect cards
- **Responsive** – works on desktop and mobile
- **Arabic‑first** – full Arabic support throughout
- **Clean dashboard** – KPI cards, charts, recent activity

---

## 🏗️ Architecture

```

XD ERP
├── services/          # Business Logic Layer
│   ├── accounting_service.py
│   ├── sales_service.py
│   ├── ai_service.py
│   └── ... (16 services total)
├── ui/                # User Interface Layer
│   ├── accounting_ui.py
│   ├── sales_ui.py
│   ├── ai_ui.py
│   └── ... (16 UIs total)
├── app.py             # Main router & session management
├── database.py        # SQLite schema (19 tables) & connection
└── requirements.txt

```

**Every module is fully separated** – business logic never touches the UI. This makes the system:

- ✅ Easy to maintain
- ✅ Easy to test
- ✅ Ready for API conversion (FastAPI)
- ✅ Ready for database migration (PostgreSQL)

---

## 🗄️ Database

**19 tables** covering the entire ERP domain:

`users`, `products`, `stock_movements`, `customers`, `suppliers`, `invoices`, `invoice_items`, `journal_entries`, `journal_lines`, `employees`, `attendance`, `accounts`, `inventory_batches`, `fifo_consumptions`, `employee_salaries`, `payroll_runs`, `closed_periods`, `roles`, `role_permissions`, `audit_log`

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit |
| Backend | Python 3.10+ |
| Database | SQLite |
| Data | Pandas, Plotly |
| Security | bcrypt |
| AI | Groq API (Llama 3.3 70B) |
| Deployment | Streamlit Cloud |

---

## 📦 Installation

```bash
# 1. Clone the repository
git clone https://github.com/saltrymy97-eng/Asam.git
cd Asam

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
streamlit run app.py
```

---

☁️ Live Demo

URL: https://asam.streamlit.app

Credentials:

· Username: admin
· Password: admin

⚠️ After first login, please change the default password using the "Forgot Password" button.

---

📂 Project Structure (Full)

```
Asam/
├── app.py                       # Main entry point
├── database.py                  # 19 tables schema
├── requirements.txt             # Python dependencies
├── manifest.json                # PWA icon configuration
├── services/                    # 16 business logic modules
│   ├── auth_service.py
│   ├── accounting_service.py
│   ├── sales_service.py
│   ├── purchases_service.py
│   ├── returns_service.py
│   ├── payroll_service.py
│   ├── financial_service.py
│   ├── audit_service.py
│   ├── backup_service.py
│   ├── pdf_service.py
│   ├── ai_service.py
│   ├── chart_service.py
│   ├── fifo_service.py
│   ├── hr_service.py
│   ├── inventory_service.py
│   ├── period_service.py
│   ├── roles_service.py
│   ├── closing_service.py
│   └── dashboard_service.py
├── ui/                          # 16 user interface modules
│   ├── auth_ui.py
│   ├── accounting_ui.py
│   ├── sales_ui.py
│   ├── purchases_ui.py
│   ├── returns.py
│   ├── payroll_ui.py
│   ├── financial_ui.py
│   ├── audit_log.py
│   ├── backup.py
│   ├── pdf_reports.py
│   ├── ai_ui.py
│   ├── chart_ui.py
│   ├── fifo_ui.py
│   ├── hr_ui.py
│   ├── inventory_ui.py
│   ├── period_ui.py
│   ├── roles_ui.py
│   ├── closing_ui.py
│   └── dashboard_ui.py
└── fonts/                       # Arabic font for PDF
```

---

🏆 Achievements

· ✅ 16 fully separated modules (Services + UI)
· ✅ 8 AI functions integrated with live data
· ✅ Full accounting cycle – entries → ledger → trial balance → financial statements → closing
· ✅ Transaction management on all financial operations
· ✅ 19 database tables designed for real‑world use
· ✅ Audit log – every action tracked
· ✅ Glassmorphism UI – modern, professional design
· ✅ Ready for production – deployed on Streamlit Cloud

---

🚀 Roadmap

· API Layer – FastAPI for mobile & third‑party integration
· PostgreSQL Migration – for concurrent users
· Multi‑Currency support
· Fixed Assets management
· Cost Centers tracking
· Mobile App – Flutter‑based
· PDF Reports with proper Arabic rendering

---

🤝 Hackathon

This project is submitted to ALGOfest 2026 Hackathon under the FinTech Innovations track.

· Project: XD ERP
· Track: FinTech
· Tagline: "XD – Where Accounting Meets AI"
· Demo: https://asam.streamlit.app

---

📄 License

MIT License – free to use, modify, and distribute.

---

👤 Author

Saltrymy97 – Solo Developer

· GitHub: @saltrymy97-eng
· Project: Asam

---

⚔️ XD ERP – Your Business Intelligence.
