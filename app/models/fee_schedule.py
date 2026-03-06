"""FeeScheduleItem model - reimbursement rates per procedure per payer contract."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..database import Base


class FeeScheduleItem(Base):
    __tablename__ = "fee_schedule_items"

    id = Column(Integer, primary_key=True, index=True)
    payer_contract_id = Column(Integer, ForeignKey("payer_contracts.id"), nullable=False, index=True)
    procedure_code_id = Column(Integer, ForeignKey("procedure_codes.id"), nullable=True, index=True)

    cdt_code = Column(String(10), nullable=False)  # denormalized
    allowed_amount_cents = Column(BigInteger, nullable=False)
    effective_date = Column(DateTime, nullable=True)
    notes = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    payer_contract = relationship("PayerContract", back_populates="fee_schedule_items")
    procedure_code = relationship("ProcedureCode")

    __table_args__ = (
        Index("idx_fee_schedule_contract_code", "payer_contract_id", "cdt_code"),
    )
