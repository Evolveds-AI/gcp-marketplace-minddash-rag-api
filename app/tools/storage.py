import os
from typing import IO

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_RAG")

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


def upload_blob(source: IO, destination: str):
    """
    Uploads a file to the bucket
    """

    blob = bucket.blob(destination)
    blob.upload_from_file(source)

    print(f"File uploaded to {destination}.")


def delete_blob(destination: str):
    """
    Deletes a file from the bucket
    """

    blob = bucket.blob(destination)
    blob.delete()

    print(f"File {destination} deleted.")
