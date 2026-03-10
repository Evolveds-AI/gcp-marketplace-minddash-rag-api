from datetime import datetime
from langchain_postgres import PGVectorStore
from langchain_postgres.v2.engine import Column
from sqlalchemy.exc import ProgrammingError


async def ingest_conversation(
    question: str,
    answer: str,
    product_id: str,
    channel_product_id: str,
    id_usuario: str,
    id_session: str,
    pg_engine,
    embeddings_model,
):
    custom_columns = [
        "user_query",
        "bot_response",
        "id_usuario",
        "id_session",
        "product_id",
        "channel_product_id",
        "created_at",
    ]

    try:
        await pg_engine.ainit_vectorstore_table(
            table_name="rag_conversationsstore",
            vector_size=768,
            metadata_columns=[
                Column("user_query", "TEXT"),
                Column("bot_response", "TEXT"),
                Column("id_usuario", "TEXT"),
                Column("id_session", "TEXT"),
                Column("product_id", "TEXT"),
                Column("channel_product_id", "TEXT"),
                Column("created_at", "TIMESTAMP WITH TIME ZONE"),
            ],
            overwrite_existing=False,
        )
    except ProgrammingError:
        pass  # table already exists with the correct schema

    vector_store = await PGVectorStore.create(
        table_name="rag_conversationsstore",
        engine=pg_engine,
        embedding_service=embeddings_model,
        metadata_columns=custom_columns,
    )

    combined_text = f"Pregunta: {question} \n Respuesta: {answer}"

    metadata_for_columns = {
        "user_query": question,
        "bot_response": answer,
        "id_usuario": id_usuario,
        "id_session": id_session,
        "product_id": product_id,
        "channel_product_id": channel_product_id,
        "created_at": datetime.now(),
    }

    await vector_store.aadd_texts(
        texts=[combined_text],
        metadatas=[metadata_for_columns],
    )

    return True
