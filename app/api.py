import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_postgres import PGVectorStore
from langchain_postgres.v2.engine import Column
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.engine import get_session, pg_engine
from app.models.convmodels import QueryVectConversationRequest, SaveConversationRequest
from app.models.query import QueryRagRequest
from app.models.uploaded_document import UploadedDocument
from app.tools.conversations import ingest_conversation
from app.tools.middleware import run_validation_logic
from app.tools.run import run_ingestion_job
from app.tools.storage import delete_blob, upload_blob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

RAG_JOB = os.getenv("JOB_RAG")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "poc-suroeste")
# Initialize the a specific Embeddings Model version
embeddings_model = VertexAIEmbeddings(
    model_name="gemini-embedding-001",
    dimensions=768,
    project=PROJECT_ID,  # Aquí usamos poc-suroeste
    location="us-central1",
)
# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {
    # Documents
    ".docx",
    ".pptx",
    ".pdf",
    ".html",
    ".htm",
    ".md",
    # Adoc
    ".asciidoc",
    ".adoc",
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
    ".webp",
    # Data / Tables
    ".csv",  # CSV
    ".xlsx",  # Excel
    # XML formats
    ".xml",  # XML_USPTO, XML_JATS, METS_GBS
    # Subtitles / transcripts
    ".vtt",  # WebVTT
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pg_engine.ainit_vectorstore_table(
        table_name="rag_vectorstore",
        vector_size=768,
        metadata_columns=[
            Column("uploaded_document_id", "UUID"),
            Column("product_id", "UUID"),
        ],
        overwrite_existing=False,
    )
    app.state.vector_store = await PGVectorStore.create(
        table_name="rag_vectorstore",
        engine=pg_engine,
        embedding_service=embeddings_model,
        metadata_columns=["uploaded_document_id", "product_id"],
    )
    yield


def vector_store() -> PGVectorStore:
    return app.state.vector_store


app = FastAPI(lifespan=lifespan)


async def validation_limits(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    is_valid, message = await run_validation_logic(product_id, session)
    if not is_valid:
        raise HTTPException(
            status_code=403,
            detail=message,
        )


@app.post("/upload", dependencies=[Depends(validation_limits)])
async def upload_file(
    file: UploadFile,
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> UploadedDocument:
    """
    Upload a file to GCS and triggers Ingestion process.

    Supported file types:
    - PDF
    - DOCX, XLSX, PPTX (MS Office Open XML)
    - Markdown (.md, .markdown)
    - AsciiDoc (.adoc, .asciidoc)
    - HTML, XHTML
    - CSV
    - Images: PNG, JPEG, TIFF, BMP, WEBP
    - WebVTT (.vtt)
    """
    # Validate file type by extension
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_ext}' is not supported. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    id = uuid.uuid4()

    # Read file content to get size
    file_content = await file.read()
    file_size = len(file_content)
    await file.seek(0)  # Reset file pointer for upload

    document = UploadedDocument(
        id=id,
        product_id=product_id,
        filename=file.filename,
        content_type=file.content_type,
        uri=f"uploads/{id}_{file.filename}",
        size=file_size,
    )

    upload_blob(file.file, document.uri)
    session.add(document)
    await session.commit()
    await session.refresh(document)

    run_ingestion_job(document.id, RAG_JOB)

    print("Ingrestion job triggered for document ID:", document.id)
    return document


@app.get("/documents", dependencies=[Depends(validation_limits)])
async def list_documents(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    """
    List uploaded documents
    """
    stmt = select(UploadedDocument).where(UploadedDocument.product_id == product_id)
    results = await session.exec(stmt)
    documents = results.all()
    return documents


@app.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> UploadedDocument:
    """
    Get uploaded document by ID
    """
    document = await session.get(UploadedDocument, document_id)
    return document


@app.post("/query")
async def query_rag(
    request: QueryRagRequest, vector_store: PGVectorStore = Depends(vector_store)
):
    """
    Query RAG system
    """
    results = []
    for query in request.queries:
        docs = await vector_store.asimilarity_search(
            query, k=3, filter={"product_id": {"$eq": str(request.product_id)}}
        )
        results.extend(docs)
    return {"results": results}


@app.post("/dialog/save_conversation", tags=["Dialog"])
async def save_conversation(request: SaveConversationRequest):
    try:
        await ingest_conversation(
            question=request.question,
            answer=request.answer,
            product_id=request.product_id,
            channel_product_id=request.channel_product_id,
            id_usuario=request.id_usuario,
            id_session=request.id_session,
            pg_engine=pg_engine,
            embeddings_model=embeddings_model,
        )
        return {"status": "success", "message": "Conversation saved to vector store"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error saving conversation: {str(e)}"
        )


@app.post("/dialog/query_conversation", tags=["Dialog"])
async def query_conversation(request: QueryVectConversationRequest):
    try:
        conv_store = await PGVectorStore.create(
            table_name="rag_conversationsstore",
            engine=pg_engine,
            embedding_service=embeddings_model,
            metadata_columns=[
                "user_query",
                "bot_response",
                "id_usuario",
                "id_session",
                "product_id",
                "created_at",
            ],
        )

        search_filter = {"product_id": str(request.product_id)}

        docs = await conv_store.asimilarity_search(
            query=request.query,
            k=3,
            filter=search_filter,
        )

        return {"results": docs}
    except Exception as e:
        print(f"Error detallado: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error querying conversation vectors: {str(e)}"
        )


@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a document by ID:
    - Removes all embeddings with metadata document_id equal to the given ID
    - Removes the document from cloud storage
    - Removes the document row from the database
    """
    # Get the document first to get the URI
    document = await session.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove embeddings from vector store
    stmt = text("DELETE FROM rag_vectorstore WHERE uploaded_document_id = :doc_id")
    await session.execute(stmt, {"doc_id": str(document_id)})

    # Remove file from cloud storage
    delete_blob(document.uri)

    # Remove document from database
    await session.delete(document)
    await session.commit()

    return {"message": f"Document {document_id} deleted successfully"}
