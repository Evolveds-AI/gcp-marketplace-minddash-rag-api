import logging
import os
from uuid import UUID

from dotenv import load_dotenv
from google.cloud import storage
from sqlalchemy import select, text

from app.models.quote_models import MetricConfigurationQuota

load_dotenv()

logger = logging.getLogger(__name__)

# Configuración de GCS
storage_client = storage.Client()
BUCKET_NAME = os.getenv("BUCKET_RAG")


async def get_db_vector_usage(session, product_id: str) -> int:
    """
    Calcula el tamaño aproximado de los embeddings en PostgreSQL.
    Cada vector de 768 dimensiones (float32) ocupa ~3072 bytes + metadata.
    """
    stmt = text("SELECT count(*) FROM rag_vectorstore WHERE product_id = :p_id")
    result = await session.execute(stmt, {"p_id": product_id})
    count = result.scalar() or 0

    # Estimación: 768 dims * 4 bytes + ~200 bytes de metadata/overhead por fila
    bytes_per_row = (768 * 4) + 200
    return count * bytes_per_row


async def run_validation_logic(product_id: UUID, session) -> tuple[bool, str]:
    ## Get QUOTA
    logger.info(f"Buscando cuota 'rag_storage_producto' para ID: {product_id}")
    quota_stmt = select(MetricConfigurationQuota).where(
        MetricConfigurationQuota.metrics_name == "rag_storage_producto"
    )
    res = await session.execute(quota_stmt)
    quota_config = res.scalars().first()

    if not quota_config:
        logger.warning(
            f"No se encontró configuración de cuota en DB para el producto {product_id}. Permitiendo acceso por defecto."
        )
        return (True, "OK")

    quota_limit_bytes = int(quota_config.quota)
    quota_limit_mb = int(quota_limit_bytes) >> 20
    logger.info(f"Cuota encontrada: {quota_limit_mb} MB")

    ## SPACE ON GCS
    logger.info("Calculando uso en GCS desde DB...")
    size_stmt = text(
        "SELECT COALESCE(SUM(size), 0) FROM rag_uploaded_documents WHERE product_id = :p_id"
    )
    size_res = await session.execute(size_stmt, {"p_id": product_id})
    current_gcs_bytes = size_res.scalar()

    used_gcs_mb = int(current_gcs_bytes) >> 20
    logger.info(f"Uso GCS: {used_gcs_mb} MB")

    ## SPACE ON DB
    logger.info("Calculando uso de vectores en DB...")
    current_db_bytes = await get_db_vector_usage(session, product_id)
    used_db_mb = int(current_db_bytes) >> 20
    logger.info(f"Uso DB: {used_db_mb} MB")

    total_bytes = current_gcs_bytes + current_db_bytes

    used_mb = int(total_bytes) >> 20
    limit_mb = int(quota_limit_bytes) >> 20

    if total_bytes > quota_limit_bytes:
        logger.error("CUOTA EXCEDIDA")
        return (
            False,
            f"Limite de almacenamiento excedido. {used_mb} MB / {limit_mb} MB",
        )

    return (True, "OK")
