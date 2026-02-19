from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from ..database import Base


class IntegrationProvider(str, Enum):
    OPEN_DENTAL = "OPEN_DENTAL"


class IntegrationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"


class SyncRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id = Column(Integer, primary_key=True, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, default=IntegrationProvider.OPEN_DENTAL.value)
    status = Column(String(50), nullable=False, default=IntegrationStatus.INACTIVE.value)
    config_json = Column(Text, nullable=True)
    secrets_ref = Column(String(255), nullable=True)
    last_cursor = Column(String(255), nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    practice = relationship("Practice", back_populates="integration_connections")
    sync_runs = relationship("IntegrationSyncRun", back_populates="connection", order_by="IntegrationSyncRun.started_at.desc()")


class IntegrationSyncRun(Base):
    __tablename__ = "integration_sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("integration_connections.id"), nullable=False, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default=SyncRunStatus.RUNNING.value)
    pulled_count = Column(Integer, nullable=False, default=0)
    upserted_count = Column(Integer, nullable=False, default=0)
    error_json = Column(Text, nullable=True)
    sync_type = Column(String(50), nullable=False, default="API")

    connection = relationship("IntegrationConnection", back_populates="sync_runs")
    practice = relationship("Practice")
