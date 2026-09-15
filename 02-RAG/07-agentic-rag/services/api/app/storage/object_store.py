import asyncio
from io import BytesIO

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.config import settings


# 对象存储封装：通过 S3 兼容协议对接 MinIO，存原始上传文件。
# 同步 boto3 调用都丢到线程池执行，避免阻塞事件循环。
class ObjectStore:
    def __init__(self) -> None:
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
        )

    # 确保桶存在，不存在则创建
    async def ensure_bucket(self) -> None:
        def ensure() -> None:
            try:
                self.client.head_bucket(Bucket=settings.s3_bucket)
            except ClientError:
                self.client.create_bucket(Bucket=settings.s3_bucket)

        await asyncio.to_thread(ensure)

    # 上传：字节流写入指定 key
    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        await self.ensure_bucket()
        await asyncio.to_thread(
            self.client.upload_fileobj,
            BytesIO(content),
            settings.s3_bucket,
            key,
            ExtraArgs={"ContentType": mime_type},
        )

    # 下载：读取指定 key 的字节内容
    async def get(self, key: str) -> bytes:
        response = await asyncio.to_thread(
            self.client.get_object, Bucket=settings.s3_bucket, Key=key
        )
        return await asyncio.to_thread(response["Body"].read)

    # 删除：删除指定 key
    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=settings.s3_bucket, Key=key
        )
