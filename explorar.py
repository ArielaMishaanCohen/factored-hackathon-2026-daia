import os
import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)

bucket = os.getenv("BUCKET")
paginator = s3.get_paginator("list_objects_v2")

total = 0
carpetas = {}
for page in paginator.paginate(Bucket=bucket):
    for obj in page.get("Contents", []):
        total += 1
        key = obj["Key"]
        top = "/".join(key.split("/")[:2])
        carpetas.setdefault(top, [0, 0])
        carpetas[top][0] += 1
        carpetas[top][1] += obj["Size"]
        if total <= 30:
            print(key, f"{obj['Size']/1e6:.1f} MB")

print(f"\nTotal archivos: {total}\n")
for c, (n, size) in sorted(carpetas.items()):
    print(f"{c:60s} {n:6d} archivos  {size/1e9:.2f} GB")