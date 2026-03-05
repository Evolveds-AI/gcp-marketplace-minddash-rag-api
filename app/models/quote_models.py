from sqlalchemy import Column, String, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid

Base = declarative_base()


class MetricConfigurationQuota(Base):
    __tablename__ = "metric_configurations_quota"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metrics_name = Column(String(200), nullable=False)
    level = Column(String(50), nullable=False)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    dimension = Column(
        String(100), nullable=False
    )  # ej: "tokens", "requests", "storage"
    quota = Column(Numeric(18, 2), nullable=False)
