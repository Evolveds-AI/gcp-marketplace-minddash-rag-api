from pydantic import BaseModel


class SaveConversationRequest(BaseModel):
    question: str
    answer: str
    product_id: str
    id_usuario: str
    id_session: str
    channel_product_id: str


class QueryVectConversationRequest(BaseModel):
    product_id: str
    query: str
