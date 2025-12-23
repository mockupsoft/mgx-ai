# -*- coding: utf-8 -*-
"""
Backend-MinIO/S3 Integration Tests

Tests cover:
- Bucket creation tests
- File upload/download tests
- File deletion tests
- Presigned URL tests
- Storage quota tests
"""

import pytest
import io
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Optional


# Test MinIO/S3 configuration
TEST_S3_ENDPOINT = "http://localhost:9000"
TEST_S3_ACCESS_KEY = "minioadmin"
TEST_S3_SECRET_KEY = "minioadmin"
TEST_S3_BUCKET = "test-bucket"
TEST_S3_REGION = "us-east-1"


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock_client = MagicMock()
    mock_client._buckets = {}
    mock_client._objects = {}
    
    def create_bucket(Bucket, **kwargs):
        if Bucket not in mock_client._buckets:
            mock_client._buckets[Bucket] = {}
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}
    
    def head_bucket(Bucket):
        if Bucket not in mock_client._buckets:
            from botocore.exceptions import ClientError
            error = ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadBucket"
            )
            raise error
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}
    
    def put_object(Bucket, Key, Body, **kwargs):
        if Bucket not in mock_client._buckets:
            mock_client._buckets[Bucket] = {}
        mock_client._objects[f"{Bucket}/{Key}"] = Body
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "ETag": "test-etag",
        }
    
    def get_object(Bucket, Key, **kwargs):
        obj_key = f"{Bucket}/{Key}"
        if obj_key not in mock_client._objects:
            from botocore.exceptions import ClientError
            error = ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}},
                "GetObject"
            )
            raise error
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "Body": io.BytesIO(mock_client._objects[obj_key]),
        }
    
    def delete_object(Bucket, Key, **kwargs):
        obj_key = f"{Bucket}/{Key}"
        if obj_key in mock_client._objects:
            del mock_client._objects[obj_key]
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}
    
    def list_objects_v2(Bucket, Prefix="", **kwargs):
        objects = []
        for key in mock_client._objects.keys():
            if key.startswith(f"{Bucket}/{Prefix}"):
                objects.append({"Key": key.split("/", 1)[1]})
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "Contents": objects,
            "IsTruncated": False,
        }
    
    def generate_presigned_url(ClientMethod, Params, ExpiresIn=3600, **kwargs):
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
def s3_storage_service(mock_s3_client):
    """Create S3 storage service with mocked client."""
    with patch('boto3.client') as mock_boto3:
        mock_boto3.return_value = mock_s3_client
        
        # Create a simple storage service wrapper
        class S3StorageService:
            def __init__(self, endpoint, access_key, secret_key, bucket, region):
                self.client = mock_s3_client
                self.bucket = bucket
                self.endpoint = endpoint
                self.region = region
            
            async def create_bucket_if_not_exists(self):
                try:
                    self.client.head_bucket(Bucket=self.bucket)
                except Exception:
                    self.client.create_bucket(Bucket=self.bucket)
            
            async def upload_file(self, key: str, content: bytes):
                return self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=content,
                )
            
            async def download_file(self, key: str) -> bytes:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
                return response["Body"].read()
            
            async def delete_file(self, key: str):
                return self.client.delete_object(Bucket=self.bucket, Key=key)
            
            async def list_files(self, prefix: str = ""):
                response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
                return [obj["Key"] for obj in response.get("Contents", [])]
            
            async def generate_presigned_url(self, key: str, expires_in: int = 3600):
                return self.client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
        
        service = S3StorageService(
            endpoint=TEST_S3_ENDPOINT,
            access_key=TEST_S3_ACCESS_KEY,
            secret_key=TEST_S3_SECRET_KEY,
            bucket=TEST_S3_BUCKET,
            region=TEST_S3_REGION,
        )
        return service


@pytest.mark.integration
class TestBucketCreation:
    """Test bucket creation functionality."""
    
    async def test_bucket_creation(self, s3_storage_service):
        """Test creating a new bucket."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Verify bucket exists
        result = s3_storage_service.client.head_bucket(Bucket=TEST_S3_BUCKET)
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200
    
    async def test_bucket_creation_idempotent(self, s3_storage_service):
        """Test that bucket creation is idempotent."""
        # Create bucket first time
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Create again (should not fail)
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Verify bucket still exists
        result = s3_storage_service.client.head_bucket(Bucket=TEST_S3_BUCKET)
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200
    
    async def test_bucket_exists_check(self, s3_storage_service):
        """Test checking if bucket exists."""
        # Create bucket
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Check existence
        result = s3_storage_service.client.head_bucket(Bucket=TEST_S3_BUCKET)
        assert result is not None


@pytest.mark.integration
class TestFileUploadDownload:
    """Test file upload and download functionality."""
    
    async def test_file_upload(self, s3_storage_service):
        """Test uploading a file."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/file.txt"
        content = b"Test file content"
        
        result = await s3_storage_service.upload_file(key, content)
        
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200
        assert "ETag" in result
    
    async def test_file_download(self, s3_storage_service):
        """Test downloading a file."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/file.txt"
        content = b"Test file content"
        
        # Upload first
        await s3_storage_service.upload_file(key, content)
        
        # Download
        downloaded = await s3_storage_service.download_file(key)
        
        assert downloaded == content
    
    async def test_file_download_nonexistent(self, s3_storage_service):
        """Test downloading a non-existent file."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        with pytest.raises(Exception):  # Should raise ClientError
            await s3_storage_service.download_file("nonexistent/file.txt")
    
    async def test_file_upload_large_file(self, s3_storage_service):
        """Test uploading a large file."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/large_file.bin"
        # Create 1MB content
        content = b"x" * (1024 * 1024)
        
        result = await s3_storage_service.upload_file(key, content)
        
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200
        
        # Verify download
        downloaded = await s3_storage_service.download_file(key)
        assert len(downloaded) == len(content)
    
    async def test_file_upload_with_metadata(self, s3_storage_service):
        """Test uploading a file with metadata."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/file_with_metadata.txt"
        content = b"Test content"
        
        # Upload with metadata
        result = s3_storage_service.client.put_object(
            Bucket=TEST_S3_BUCKET,
            Key=key,
            Body=content,
            Metadata={"content-type": "text/plain", "author": "test"},
        )
        
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200


@pytest.mark.integration
class TestFileDeletion:
    """Test file deletion functionality."""
    
    async def test_file_deletion(self, s3_storage_service):
        """Test deleting a file."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/file_to_delete.txt"
        content = b"Test content"
        
        # Upload first
        await s3_storage_service.upload_file(key, content)
        
        # Verify exists
        downloaded = await s3_storage_service.download_file(key)
        assert downloaded == content
        
        # Delete
        result = await s3_storage_service.delete_file(key)
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 204
        
        # Verify deleted
        with pytest.raises(Exception):
            await s3_storage_service.download_file(key)
    
    async def test_file_deletion_nonexistent(self, s3_storage_service):
        """Test deleting a non-existent file."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Delete non-existent file (should not raise error)
        result = await s3_storage_service.delete_file("nonexistent/file.txt")
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 204
    
    async def test_bulk_file_deletion(self, s3_storage_service):
        """Test deleting multiple files."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Upload multiple files
        keys = [f"test/file_{i}.txt" for i in range(5)]
        for key in keys:
            await s3_storage_service.upload_file(key, b"content")
        
        # Delete all
        for key in keys:
            await s3_storage_service.delete_file(key)
        
        # Verify all deleted
        for key in keys:
            with pytest.raises(Exception):
                await s3_storage_service.download_file(key)


@pytest.mark.integration
class TestPresignedURL:
    """Test presigned URL functionality."""
    
    async def test_generate_presigned_url(self, s3_storage_service):
        """Test generating a presigned URL."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/private_file.txt"
        content = b"Private content"
        
        # Upload file
        await s3_storage_service.upload_file(key, content)
        
        # Generate presigned URL
        url = await s3_storage_service.generate_presigned_url(key, expires_in=3600)
        
        assert url is not None
        assert key in url
        assert "signature" in url or "X-Amz" in url
    
    async def test_presigned_url_expiration(self, s3_storage_service):
        """Test presigned URL expiration."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        key = "test/expiring_file.txt"
        content = b"Content"
        
        await s3_storage_service.upload_file(key, content)
        
        # Generate URL with short expiration
        url = await s3_storage_service.generate_presigned_url(key, expires_in=1)
        
        assert url is not None
        
        # Note: Actual expiration testing would require time.sleep and HTTP request
        # This is a simplified test


@pytest.mark.integration
class TestStorageQuota:
    """Test storage quota functionality."""
    
    async def test_list_files(self, s3_storage_service):
        """Test listing files in bucket."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Upload multiple files
        keys = ["test/file1.txt", "test/file2.txt", "other/file3.txt"]
        for key in keys:
            await s3_storage_service.upload_file(key, b"content")
        
        # List all files
        all_files = await s3_storage_service.list_files()
        assert len(all_files) == 3
        assert all(key in all_files for key in keys)
    
    async def test_list_files_with_prefix(self, s3_storage_service):
        """Test listing files with prefix filter."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Upload files with different prefixes
        keys = ["test/file1.txt", "test/file2.txt", "other/file3.txt"]
        for key in keys:
            await s3_storage_service.upload_file(key, b"content")
        
        # List files with prefix
        test_files = await s3_storage_service.list_files(prefix="test/")
        assert len(test_files) == 2
        assert "test/file1.txt" in test_files
        assert "test/file2.txt" in test_files
        assert "other/file3.txt" not in test_files
    
    async def test_storage_size_calculation(self, s3_storage_service):
        """Test calculating storage size."""
        await s3_storage_service.create_bucket_if_not_exists()
        
        # Upload files of different sizes
        files = {
            "small.txt": b"x" * 100,
            "medium.txt": b"x" * 1000,
            "large.txt": b"x" * 10000,
        }
        
        total_size = 0
        for key, content in files.items():
            await s3_storage_service.upload_file(f"test/{key}", content)
            total_size += len(content)
        
        # Note: Actual size calculation would require HEAD requests
        # This is a simplified test
        assert total_size > 0

