import uuid
from datetime import datetime, date
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Date, Numeric, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..database import Base


class OntologyObjectType(str, Enum):
    PRACTICE = "Practice"
    PAYER = "Payer"
    CLAIM = "Claim"
    PROCEDURE = "Procedure"
    DENIAL = "Denial"
    REMITTANCE = "Remittance"
    PAYMENT_INTENT = "PaymentIntent"
    LEDGER_ENTRY = "LedgerEntry"
    KPI_OBSERVATION = "KPIObservation"
    PATIENT = "Patient"


class OntologyLinkType(str, Enum):
    CLAIM_BILLED_TO_PAYER = "CLAIM_BILLED_TO_PAYER"
    CLAIM_HAS_PROCEDURE = "CLAIM_HAS_PROCEDURE"
    CLAIM_FUNDED_BY_PAYMENT_INTENT = "CLAIM_FUNDED_BY_PAYMENT_INTENT"
    CLAIM_RESULTED_IN_DENIAL = "CLAIM_RESULTED_IN_DENIAL"
    CLAIM_RESULTED_IN_REMITTANCE = "CLAIM_RESULTED_IN_REMITTANCE"
    CLAIM_BELONGS_TO_PATIENT = "CLAIM_BELONGS_TO_PATIENT"


class OntologyObject(Base):
    __tablename__ = "ontology_objects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    object_type = Column(String(50), nullable=False)
    object_key = Column(String(255), nullable=True)
    properties_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ontology_objects_practice_type", "practice_id", "object_type"),
        Index("idx_ontology_objects_practice_key", "practice_id", "object_key"),
    )


class OntologyLink(Base):
    __tablename__ = "ontology_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    link_type = Column(String(50), nullable=False)
    from_object_id = Column(UUID(as_uuid=True), ForeignKey("ontology_objects.id"), nullable=False)
    to_object_id = Column(UUID(as_uuid=True), ForeignKey("ontology_objects.id"), nullable=False)
    properties_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ontology_links_practice_type", "practice_id", "link_type"),
        Index("idx_ontology_links_from", "from_object_id"),
        Index("idx_ontology_links_to", "to_object_id"),
    )


class KPIObservation(Base):
    __tablename__ = "kpi_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric, nullable=True)
    as_of_date = Column(Date, nullable=False, default=date.today)
    provenance_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_kpi_observations_practice_metric", "practice_id", "metric_name"),
        Index("idx_kpi_observations_date", "as_of_date"),
    )


class MetricTimeseries(Base):
    __tablename__ = "metric_timeseries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    value = Column(Numeric, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_metric_ts_practice_metric_date", "practice_id", "metric_name", "date"),
        Index("idx_metric_ts_practice_date", "practice_id", "date"),
    )
