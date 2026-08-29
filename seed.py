"""Seed the database with initial data."""
import asyncio
from datetime import date, datetime
from database import init_db, async_session
from models import User, Client, ServiceItem, CompanySettings, Document, DocumentLineItem, ActivityLog
from auth import hash_password


async def seed():
    await init_db()
    async with async_session() as db:
        from sqlalchemy import select, func
        count = await db.scalar(select(func.count()).select_from(User))
        if count and count > 0:
            print("Database already seeded.")
            return

        # Users
        admin = User(id="user_admin", email="admin@alunamda.co.za", name="Admin",
                     password_hash=hash_password("Admin@123"), role="admin")
        staff = User(id="user_staff", email="staff@alunamda.co.za", name="Staff",
                     password_hash=hash_password("Staff@123"), role="staff")
        db.add_all([admin, staff])

        # Company Settings
        settings = CompanySettings(
            id="settings_main",
            company_name="ALUNAMDA Accounting Services (Pty) Ltd",
            trading_as="ALUNAMDA",
            registration_number="2024/123456/07",
            vat_number="4123456789",
            email="info@alunamda.co.za",
            phone="+27 11 234 5678",
            whatsapp="+27 11 234 5678",
            website="www.alunamda.co.za",
            address="123 Business Park, Sandton",
            city="Johannesburg",
            postal_code="2196",
            postal_address="PO Box 1234, Sandton, 2196",
            bank_name="First National Bank",
            bank_account_name="ALUNAMDA Accounting Services (Pty) Ltd",
            bank_account="62123456789",
            bank_branch="250655",
            bank_swift="FIRNZAJJ",
            primary_color="#002060",
            secondary_color="#C9A227",
            footer_text="Thank you for your business.",
            default_vat_rate=15.0,
            default_payment_terms="30_days",
            default_quote_validity="30_days",
            default_notes="Thank you for your business.",
            default_terms="Payment is due within 30 days of invoice date.\nLate payments may be subject to interest at the prescribed rate.\nAll prices are exclusive of VAT unless stated otherwise.",
            next_quote_number=5,
            next_invoice_number=3,
            counter_year=2026,
        )
        db.add(settings)

        # Clients
        clients_data = [
            ("TechCorp Solutions", "John Smith", "john@techcorp.co.za", "+27 11 000 1001", "45 Tech Lane, Sandton, Johannesburg", "2196", "4120000001"),
            ("Green Valley Farms", "Sarah Johnson", "sarah@greenvalley.co.za", "+27 12 000 1002", "78 Farm Road, Pretoria", "0001", "4120000002"),
            ("Metro Construction", "David Williams", "david@metroconst.co.za", "+27 21 000 1003", "12 Builder St, Cape Town", "8001", "4120000003"),
            ("Sunrise Medical", "Dr. Patel", "patel@sunrisemed.co.za", "+27 31 000 1004", "90 Health Ave, Durban", "4001", "4120000004"),
            ("Ocean Logistics", "Mike Brown", "mike@oceanlog.co.za", "+27 41 000 1005", "55 Harbor Rd, Port Elizabeth", "6001", "4120000005"),
        ]
        clients = []
        for i, (company, contact, email, phone, address, postal, vat) in enumerate(clients_data, 1):
            c = Client(id=f"client_{i:03d}", company_name=company, contact_name=contact,
                       email=email, phone=phone, address=address, postal_code=postal, vat_number=vat)
            clients.append(c)
        db.add_all(clients)

        # Services (comprehensive catalog from old app)
        services_data = [
            # CIPC
            ("Private Company Registration (Pty Ltd)", "Full CIPC registration including name reservation, MOI, and COIDA registration", 3500.0, 15.0, "CIPC"),
            ("Cooperative Registration", "CIPC cooperative registration and compliance", 2800.0, 15.0, "CIPC"),
            ("NPO Registration", "Non-profit organization registration with CIPC and NPO Directorate", 4500.0, 15.0, "CIPC"),
            ("NPC Registration", "Non-profit company registration with CIPC", 4500.0, 15.0, "CIPC"),
            ("Company Name Reservation", "CIPC name reservation application", 750.0, 15.0, "CIPC"),
            # Accounting
            ("Monthly Bookkeeping", "Full monthly bookkeeping service including bank reconciliation and management reports", 4500.0, 15.0, "Accounting"),
            ("Payroll Administration", "Monthly payroll processing per employee including payslips and EMP201", 350.0, 15.0, "Accounting"),
            ("Annual Financial Statements", "Compilation of annual financial statements (IFRS for SMEs)", 8500.0, 15.0, "Accounting"),
            ("Accounting Consultation", "Professional accounting consultation and advice", 1500.0, 15.0, "Accounting"),
            ("Management Accounts", "Monthly management accounts preparation with variance analysis", 6000.0, 15.0, "Accounting"),
            # Business Maintenance
            ("Director Changes", "CIPC director appointment/resignation changes", 1200.0, 15.0, "Business Maintenance"),
            ("Address Changes", "CIPC registered address change", 800.0, 15.0, "Business Maintenance"),
            ("Company Name Changes", "CIPC company name change application", 1500.0, 15.0, "Business Maintenance"),
            ("Annual Returns Submission", "CIPC annual return filing and compliance", 1200.0, 15.0, "Business Maintenance"),
            # Department of Labour
            ("UIF Registration", "UIF registration for employer and employees", 1500.0, 15.0, "Department of Labour"),
            ("UFiling Registration", "Online UFiling portal registration and setup", 1000.0, 15.0, "Department of Labour"),
            ("Declarations & Submissions", "Monthly UIF declarations and submissions", 800.0, 15.0, "Department of Labour"),
            ("Compensation Commissioner Registration", "COIDA/COMPULSORY registration with Compensation Commissioner", 2000.0, 15.0, "Department of Labour"),
            ("ROE Submission", "Return of Earnings submission to Compensation Commissioner", 1500.0, 15.0, "Department of Labour"),
            ("Letter of Good Standing", "Application for Letter of Good Standing from COIDA", 1000.0, 15.0, "Department of Labour"),
            # SARS
            ("Business Income Tax Registration", "SARS income tax registration for businesses", 2000.0, 15.0, "SARS"),
            ("Individual Income Tax Registration", "SARS income tax registration for individuals", 1000.0, 15.0, "SARS"),
            ("Individual Tax Return (ITR12)", "Annual individual tax return preparation and submission", 2500.0, 15.0, "SARS"),
            ("Company Tax Return (ITR14)", "Annual company tax return preparation and submission", 5500.0, 15.0, "SARS"),
            ("Tax Representative Appointment", "SARS tax representative appointment/activation", 1500.0, 15.0, "SARS"),
            ("eFiling Registration", "SARS eFiling profile registration and setup", 500.0, 15.0, "SARS"),
            ("VAT Registration", "SARS VAT registration for businesses", 2000.0, 15.0, "SARS"),
            ("VAT201 Submission", "Monthly/Quarterly VAT return preparation and submission", 1800.0, 15.0, "SARS"),
            ("EMP Registration", "SARS EMP registration for payroll taxes", 1500.0, 15.0, "SARS"),
            ("EMP201/EMP501 Submission", "Monthly EMP201 and annual EMP501 submission", 1200.0, 15.0, "SARS"),
            ("Customs Registration", "SARS customs registration for import/export", 2500.0, 15.0, "SARS"),
            ("PBO Application", "Public Benefit Organization application to SARS", 5000.0, 15.0, "SARS"),
            ("SARS Correspondence", "Handling all SARS correspondence and queries", 1500.0, 15.0, "SARS"),
            # B-BBEE
            ("B-BBEE Certificate", "B-BBEE certificate verification and certificate procurement", 3000.0, 15.0, "B-BBEE"),
            # Advisory
            ("Business Advisory", "Strategic business advisory and planning sessions", 2500.0, 15.0, "Advisory"),
            ("Tax Consultation", "Professional tax planning and consultation", 2000.0, 15.0, "Advisory"),
            ("Cash Flow Forecasting", "12-month cash flow projection and analysis", 3500.0, 15.0, "Advisory"),
            ("Business Valuation", "Small business valuation report", 15000.0, 15.0, "Advisory"),
            ("Audit Support", "Support during external audit process", 7500.0, 15.0, "Advisory"),
            # General
            ("Consultation", "General business consultation meeting", 1000.0, 15.0, "General"),
            ("Administrative Services", "General administrative and secretarial services", 500.0, 15.0, "General"),
            ("Document Preparation", "Professional document preparation and review", 800.0, 15.0, "General"),
            ("Compliance Review", "Regulatory compliance review and recommendations", 3000.0, 15.0, "General"),
        ]
        services = []
        for i, (name, desc, price, vat, cat) in enumerate(services_data, 1):
            s = ServiceItem(id=f"svc_{i:03d}", name=name, description=desc, unit_price=price, vat_rate=vat, category=cat)
            services.append(s)
        db.add_all(services)

        # Documents
        docs = [
            ("Q-2026-000001", "quote", "sent", "client_001", date(2026, 1, 15), date(2026, 2, 15), date(2026, 2, 15), 14970.00, 15.0, 2245.50, 0, 17215.50, "exclusive"),
            ("Q-2026-000002", "quote", "draft", "client_002", date(2026, 1, 20), date(2026, 2, 20), date(2026, 2, 20), 7350.00, 15.0, 1102.50, 0, 8452.50, "exclusive"),
            ("Q-2026-000003", "quote", "sent", "client_003", date(2026, 2, 1), date(2026, 3, 1), date(2026, 3, 1), 25500.00, 15.0, 3825.00, 0, 29325.00, "exclusive"),
            ("Q-2026-000004", "quote", "sent", "client_004", date(2026, 2, 5), date(2026, 3, 5), date(2026, 3, 5), 4800.00, 15.0, 720.00, 0, 5520.00, "exclusive"),
            ("INV-2026-000001", "invoice", "paid", "client_001", date(2026, 1, 1), date(2026, 1, 31), None, 4500.00, 15.0, 675.00, 0, 5175.00, "exclusive"),
            ("INV-2026-000002", "invoice", "overdue", "client_003", date(2026, 2, 15), date(2026, 3, 15), None, 11376.00, 15.0, 1706.40, 0, 13082.40, "exclusive"),
        ]
        documents = []
        for i, (num, dtype, status, cid, issue, due, valid, sub, vr, va, disc, total, vmode) in enumerate(docs, 1):
            d = Document(
                id=f"doc_{i:03d}", document_number=num, type=dtype, status=status,
                client_id=cid, issue_date=issue, due_date=due, valid_until=valid,
                subtotal=sub, vat_rate=vr, vat_amount=va, discount_amount=disc,
                grand_total=total, vat_mode=vmode,
                payment_terms="30_days",
                paid_date=date(2026, 1, 28) if status == "paid" else None,
            )
            documents.append(d)
        db.add_all(documents)

        # Line Items
        line_items = [
            ("li_001", "doc_005", 1, "Monthly Bookkeeping", "November 2024 bookkeeping", 1, 4500.0, 0, 15.0, "exclusive", 4500.0),
            ("li_002", "doc_006", 1, "Annual Financial Statements", "FY2024 AFS compilation", 1, 8500.0, 0, 15.0, "exclusive", 8500.0),
            ("li_003", "doc_006", 2, "Company Tax Return", "ITR14 FY2024", 1, 5500.0, 5.0, 15.0, "exclusive", 5225.0),
            ("li_004", "doc_001", 1, "Private Company Registration (Pty Ltd)", "New company registration for TechCorp subsidiary", 1, 3500.0, 0, 15.0, "exclusive", 3500.0),
            ("li_005", "doc_001", 2, "VAT Registration", "VAT registration for new entity", 1, 2000.0, 0, 15.0, "exclusive", 2000.0),
            ("li_006", "doc_001", 3, "B-BBEE Certificate", "B-BBEE certificate for new entity", 1, 3000.0, 0, 15.0, "exclusive", 3000.0),
            ("li_007", "doc_002", 1, "Monthly Bookkeeping", "Jan 2026 bookkeeping", 1, 4500.0, 0, 15.0, "exclusive", 4500.0),
            ("li_008", "doc_002", 2, "Payroll Administration", "Jan 2026 payroll - 8 employees", 8, 350.0, 0, 15.0, "exclusive", 2800.0),
            ("li_009", "doc_003", 1, "Annual Financial Statements", "FY2025 AFS for Metro Construction", 1, 8500.0, 0, 15.0, "exclusive", 8500.0),
            ("li_010", "doc_003", 2, "Company Tax Return", "ITR14 FY2025", 1, 5500.0, 0, 15.0, "exclusive", 5500.0),
            ("li_011", "doc_003", 3, "Audit Support", "External audit support - 3 days", 3, 2500.0, 0, 15.0, "exclusive", 7500.0),
            ("li_012", "doc_004", 1, "VAT201 Submission", "Q1 2026 VAT return", 1, 1800.0, 0, 15.0, "exclusive", 1800.0),
            ("li_013", "doc_004", 2, "EMP201/EMP501 Submission", "Feb 2026 EMP201", 1, 1200.0, 0, 15.0, "exclusive", 1200.0),
            ("li_014", "doc_004", 3, "SARS Correspondence", "Responding to SARS notice", 1, 1500.0, 0, 15.0, "exclusive", 1500.0),
        ]
        for lid, docid, sort, svc, desc, qty, price, disc, vr, vm, total in line_items:
            db.add(DocumentLineItem(
                id=lid, document_id=docid, sort_order=sort, service=svc, description=desc,
                quantity=qty, unit_price=price, discount=disc, vat_rate=vr, vat_mode=vm, line_total=total
            ))

        # Activity Log
        activities = [
            ("user_admin", "created", "document", "doc_001", "Created quote Q-2026-000001 for TechCorp Solutions"),
            ("user_admin", "sent", "document", "doc_001", "Sent quote Q-2026-000001 to TechCorp Solutions"),
            ("user_staff", "created", "client", "client_005", "Added new client Ocean Logistics"),
            ("user_admin", "created", "document", "doc_005", "Created invoice INV-2026-000001 for TechCorp Solutions"),
            ("user_admin", "paid", "document", "doc_005", "Invoice INV-2026-000001 marked as paid"),
            ("user_admin", "created", "document", "doc_002", "Created quote Q-2026-000002 for Green Valley Farms"),
            ("user_admin", "created", "document", "doc_003", "Created quote Q-2026-000003 for Metro Construction"),
            ("user_admin", "sent", "document", "doc_003", "Sent quote Q-2026-000003 to Metro Construction"),
            ("user_admin", "created", "document", "doc_006", "Created invoice INV-2026-000002 for Metro Construction"),
        ]
        for uid, action, etype, eid, desc in activities:
            db.add(ActivityLog(user_id=uid, action=action, entity_type=etype, entity_id=eid, description=desc))

        await db.commit()
        print("Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
