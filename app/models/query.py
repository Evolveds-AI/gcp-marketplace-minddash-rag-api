import uuid

from pydantic import BaseModel


class QueryRagRequest(BaseModel):
    product_id: uuid.UUID
    queries: list[str]
