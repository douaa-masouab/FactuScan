from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database configuration
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '3306')
DB_USER = os.environ.get('DB_USER', 'factuscan_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'secure_password')
DB_NAME = os.environ.get('DB_NAME', 'factuscan')

DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URI)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Database Models
class Invoice(Base):
    __tablename__ = 'invoices'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    invoice_number = Column(String(100))
    invoice_date = Column(String(50))
    supplier = Column(String(255))
    ice = Column(String(50))
    vat_amount = Column(Float)
    total_amount = Column(Float)
    extracted_text = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date,
            'supplier': self.supplier,
            'ice': self.ice,
            'vat_amount': self.vat_amount,
            'total_amount': self.total_amount,
            'extracted_text': self.extracted_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class DatabaseManager:
    def __init__(self):
        self.session = Session()
    
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(engine)
    
    def get_session(self):
        """Get a new database session"""
        return Session()
    
    def save_invoice(self, invoice_data):
        """Save a new invoice to the database"""
        try:
            invoice = Invoice(**invoice_data)
            self.session.add(invoice)
            self.session.commit()
            return invoice.id
        except Exception as e:
            self.session.rollback()
            raise e
    
    def get_invoice(self, invoice_id):
        """Get an invoice by ID"""
        return self.session.query(Invoice).filter_by(id=invoice_id).first()
    
    def get_all_invoices(self):
        """Get all invoices"""
        return self.session.query(Invoice).all()
    
    def update_invoice(self, invoice_id, data):
        """Update an invoice"""
        try:
            invoice = self.session.query(Invoice).filter_by(id=invoice_id).first()
            if not invoice:
                return None
            
            for key, value in data.items():
                if hasattr(invoice, key):
                    setattr(invoice, key, value)
            
            invoice.updated_at = datetime.now()
            self.session.commit()
            return invoice
        except Exception as e:
            self.session.rollback()
            raise e
    
    def delete_invoice(self, invoice_id):
        """Delete an invoice"""
        try:
            invoice = self.session.query(Invoice).filter_by(id=invoice_id).first()
            if not invoice:
                return False
            
            self.session.delete(invoice)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            raise e
    
    def get_statistics(self):
        """Get invoice statistics"""
        try:
            total_invoices = self.session.query(func.count(Invoice.id)).scalar()
            total_amount = self.session.query(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar()
            
            # Current month
            current_month = datetime.now().month
            current_year = datetime.now().year
            month_amount = self.session.query(func.coalesce(func.sum(Invoice.total_amount), 0)).filter(
                func.month(Invoice.created_at) == current_month,
                func.year(Invoice.created_at) == current_year
            ).scalar()
            
            return {
                'total_invoices': total_invoices,
                'total_amount': float(total_amount),
                'month_amount': float(month_amount),
                'average_amount': float(total_amount) / total_invoices if total_invoices > 0 else 0
            }
        except Exception as e:
            raise e