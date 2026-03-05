from google.api_core import operation
from google.cloud import run_v2

client = run_v2.JobsClient()


def run_ingestion_job(
    document_id: str,
    job: str,
    location: str = "us-central1",
    project: str = "poc-suroeste",
) -> operation.Operation:
    job_name = f"projects/{project}/locations/{location}/jobs/{job}"

    container_override = run_v2.RunJobRequest.Overrides.ContainerOverride(
        args=[str(document_id)]
    )

    job_overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[container_override]
    )

    request = run_v2.RunJobRequest(
        name=job_name,
        overrides=job_overrides,
    )

    # Make the request
    operation = client.run_job(request=request)

    # Handle the response
    # print(operation)
    # print(operation.operation)
    # print(operation.operation.name) -> str

    return operation
