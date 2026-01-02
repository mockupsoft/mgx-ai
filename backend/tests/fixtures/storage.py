# -*- coding: utf-8 -*-
"""
Storage Fixtures

Provides fixtures for MinIO/S3 storage testing including:
- Mock S3 client
- Test bucket setup
- File upload/download fixtures
"""

import pytest
import io
from unittest.mock import Mock, MagicMock
from typing import Dict, Any


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    mock_client = MagicMock()
    mock_client._buckets: Dict[str, Dict[str, bytes]] = {}
    
    def create_bucket(Bucket: str, **kwargs):
        if Bucket not in mock_client._buckets:
            mock_client._buckets[Bucket] = {}
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}
    
    def head_bucket(Bucket: str):
        if Bucket not in mock_client._buckets:
            from botocore.exceptions import ClientError
            error = ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadBucket"
            )
            raise error
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}
    
    def put_object(Bucket: str, Key: str, Body: bytes, **kwargs):
        if Bucket not in mock_client._buckets:
            mock_client._buckets[Bucket] = {}
        mock_client._buckets[Bucket][Key] = Body if isinstance(Body, bytes) else Body.read()
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "ETag": "test-etag",
        }
    
    def get_object(Bucket: str, Key: str, **kwargs):
        if Bucket not in mock_client._buckets or Key not in mock_client._buckets[Bucket]:
            from botocore.exceptions import ClientError
            error = ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}},
                "GetObject"
            )
            raise error
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "Body": io.BytesIO(mock_client._buckets[Bucket][Key]),
        }
    
    def delete_object(Bucket: str, Key: str, **kwargs):
        if Bucket in mock_client._buckets and Key in mock_client._buckets[Bucket]:
            del mock_client._buckets[Bucket][Key]
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}
    
    def list_objects_v2(Bucket: str, Prefix: str = "", **kwargs):
        objects = []
        if Bucket in mock_client._buckets:
            for key in mock_client._buckets[Bucket].keys():
                if key.startswith(Prefix):
                    objects.append({"Key": key})
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "Contents": objects,
            "IsTruncated": False,
        }
    
    def generate_presigned_url(ClientMethod: str, Params: Dict[str, Any], ExpiresIn: int = 3600, **kwargs):
        Bucket = Params.get("Bucket", "")
        Key = Params.get("Key", "")
        return f"https://s3.example.com/{Bucket}/{Key}?signature=test"
    
    mock_client.create_bucket = create_bucket
    mock_client.head_bucket = head_bucket
    mock_client.put_object = put_object
    mock_client.get_object = get_object
    mock_client.delete_object = delete_object
    mock_client.list_objects_v2 = list_objects_v2
    mock_client.generate_presigned_url = generate_presigned_url
    
    return mock_client


@pytest.fixture
def test_bucket(mock_s3_client):
    """Create a test bucket."""
    bucket_name = "test-bucket"
    mock_s3_client.create_bucket(Bucket=bucket_name)
    return bucket_name




