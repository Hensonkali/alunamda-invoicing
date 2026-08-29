import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import String, Float, Integer, Boolean, Text, DateTime, Date, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum


def gen_id():
    return uuid.uuid4().hex[:20]


def utcnow():
    return datetime.now(timezone.utc)


class DocType(str, enum.Enum):
    quote = "quote"
    invoice = "invoice"
    paid_invoice = "paid_invoice"
    receipt = "receipt"


class DocStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class VATMode(str, enum.Enum):
    inclusive = "inclusive"
    exclusive = "exclusive"
    none = "none"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    company_name: Mapped[str] = mapped_column(String(255))
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(100), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    postal_code: Mapped[str] = mapped_column(String(20), default="")
    country: Mapped[str] = mapped_column(String(100), default="South Africa")
    vat_number: Mapped[str] = mapped_column(String(50), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    documents: Mapped[list["Document"]] = relationship(back_populates="client")


class ServiceItem(Base):
    __tablename__ = "service_items"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=15.0)
    category: Mapped[str] = mapped_column(String(100), default="General")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    document_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    client_id: Mapped[str] = mapped_column(String(20), ForeignKey("clients.id"))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=15.0)
    vat_amount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    grand_total: Mapped[float] = mapped_column(Float, default=0.0)
    vat_mode: Mapped[str] = mapped_column(String(20), default="exclusive")
    payment_terms: Mapped[str] = mapped_column(String(255), default="Due within 30 days")
    payment_method: Mapped[str] = mapped_column(String(100), default="")
    client_notes: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    terms_and_conditions: Mapped[str] = mapped_column(Text, default="")
    parent_document_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    client: Mapped["Client"] = relationship(back_populates="documents")
    line_items: Mapped[list["DocumentLineItem"]] = relationship(back_populates="document", order_by="DocumentLineItem.sort_order")
    payments: Mapped[list["Payment"]] = relationship(back_populates="document", order_by="Payment.payment_date")


class DocumentLineItem(Base):
    __tablename__ = "document_line_items"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    document_id: Mapped[str] = mapped_column(String(20), ForeignKey("documents.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    service: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    vat_rate: Mapped[float] = mapped_column(Float, default=15.0)
    vat_mode: Mapped[str] = mapped_column(String(20), default="exclusive")
    line_total: Mapped[float] = mapped_column(Float, default=0.0)
    document: Mapped["Document"] = relationship(back_populates="line_items")


class CompanySettings(Base):
    __tablename__ = "company_settings"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    company_name: Mapped[str] = mapped_column(String(255), default="ALUNAMDA Accounting Services (Pty) Ltd")
    trading_as: Mapped[str] = mapped_column(String(255), default="")
    registration_number: Mapped[str] = mapped_column(String(100), default="")
    vat_number: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(255), default="info@alunamda.co.za")
    phone: Mapped[str] = mapped_column(String(100), default="")
    whatsapp: Mapped[str] = mapped_column(String(100), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    postal_code: Mapped[str] = mapped_column(String(20), default="")
    country: Mapped[str] = mapped_column(String(100), default="South Africa")
    postal_address: Mapped[str] = mapped_column(Text, default="")
    bank_name: Mapped[str] = mapped_column(String(255), default="")
    bank_account_name: Mapped[str] = mapped_column(String(255), default="")
    bank_account: Mapped[str] = mapped_column(String(100), default="")
    bank_branch: Mapped[str] = mapped_column(String(100), default="")
    bank_swift: Mapped[str] = mapped_column(String(100), default="")
    primary_color: Mapped[str] = mapped_column(String(20), default="#002060")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#C9A227")
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    footer_text: Mapped[str] = mapped_column(Text, default="Thank you for your business.")
    signature: Mapped[str] = mapped_column(Text, default="")
    default_vat_rate: Mapped[float] = mapped_column(Float, default=15.0)
    default_payment_terms: Mapped[str] = mapped_column(String(255), default="30_days")
    default_quote_validity: Mapped[str] = mapped_column(String(50), default="30_days")
    default_notes: Mapped[str] = mapped_column(Text, default="")
    default_terms: Mapped[str] = mapped_column(Text, default="Payment is due within 30 days of invoice date.\nLate payments may be subject to interest at the prescribed rate.\nAll prices are exclusive of VAT unless stated otherwise.")
    quote_prefix: Mapped[str] = mapped_column(String(10), default="Q")
    invoice_prefix: Mapped[str] = mapped_column(String(10), default="INV")
    paid_invoice_prefix: Mapped[str] = mapped_column(String(10), default="PINV")
    receipt_prefix: Mapped[str] = mapped_column(String(10), default="REC")
    next_quote_number: Mapped[int] = mapped_column(Integer, default=1)
    next_invoice_number: Mapped[int] = mapped_column(Integer, default=1)
    next_paid_invoice_number: Mapped[int] = mapped_column(Integer, default=1)
    next_receipt_number: Mapped[int] = mapped_column(Integer, default=1)
    counter_year: Mapped[int] = mapped_column(Integer, default=2026)


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(20), default="system")
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(20), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    document_id: Mapped[str] = mapped_column(String(20), ForeignKey("documents.id"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    payment_date: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str] = mapped_column(String(100), default="")
    reference: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    document: Mapped["Document"] = relationship(back_populates="payments")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    document_id: Mapped[str] = mapped_column(String(20), ForeignKey("documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[str] = mapped_column(Text, default="")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(20), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    document_id: Mapped[str] = mapped_column(String(20), ForeignKey("documents.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RecurringInvoice(Base):
    __tablename__ = "recurring_invoices"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default=gen_id)
    client_id: Mapped[str] = mapped_column(String(20), ForeignKey("clients.id"), index=True)
    template_name: Mapped[str] = mapped_column(String(255))
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    day_of_month: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    line_items_snapshot: Mapped[str] = mapped_column(Text, default="[]")
    vat_mode: Mapped[str] = mapped_column(String(20), default="exclusive")
    payment_terms: Mapped[str] = mapped_column(String(255), default="Due within 30 days")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_generated_doc_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
