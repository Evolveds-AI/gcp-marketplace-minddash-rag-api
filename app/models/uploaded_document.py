import uuid
from datetime import datetime
from typing import Literal

from sqlmodel import BigInteger, Field, SQLModel, String


class UploadedDocument(SQLModel, table=True):
    __tablename__ = "rag_uploaded_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_id: uuid.UUID
    filename: str
    content_type: str
    uri: str
    size: int = Field(default=0, sa_type=BigInteger())  # Size in bytes
    status: Literal["PENDING", "RUNNING", "ERROR", "DONE"] = Field(
        default="PENDING", sa_type=String
    )

    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
