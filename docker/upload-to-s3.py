#!/usr/bin/env python3
"""
S3 Uploader for Analysis Reports

This script uploads generated analysis reports to an S3 bucket (LocalStack).
It's designed to run after the analyzer completes, ensuring reports are
persisted in S3 for archival and compliance purposes.

Usage:
    python upload-to-s3.py
    
Environment Variables:
    AWS_ENDPOINT_URL: LocalStack S3 endpoint (default: http://localhost:4566)
    AWS_ACCESS_KEY_ID: AWS credentials
    AWS_SECRET_ACCESS_KEY: AWS credentials
    REPORT_FILE: Path to report file (default: /app/output/report.json)
    S3_BUCKET: Target S3 bucket (default: analyzer-reports)
    S3_PREFIX: S3 path prefix (default: reports/)
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


def upload_report_to_s3(
    report_file: str,
    bucket_name: str = "analyzer-reports",
    s3_prefix: str = "reports/"
) -> bool:
    """
    Upload an analysis report to S3 bucket.
    
    Creates a timestamped S3 key based on the report generation time
    to prevent overwrites and maintain a full audit trail.
    
    Args:
        report_file: Path to the report JSON file
        bucket_name: Name of the S3 bucket
        s3_prefix: S3 path prefix for organization
        
    Returns:
        True if upload was successful, False otherwise
    """
    # Validate input file
    report_path = Path(report_file)
    if not report_path.exists():
        print(f"[ERROR] Report file not found: {report_file}")
        return False
    
    if not report_path.is_file():
        print(f"[ERROR] Not a file: {report_file}")
        return False
    
    try:
        # Get LocalStack endpoint from environment or use default
        endpoint_url = os.getenv('AWS_ENDPOINT_URL', 'http://localhost:4566')
        
        # Initialize S3 client pointing to LocalStack
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'test'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'test'),
            region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # Create bucket if it doesn't exist (init scripts can be unreliable)
        try:
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"[INFO] Created bucket: {bucket_name}")
        except ClientError as e:
            if e.response['Error']['Code'] not in ('BucketAlreadyExists', 'BucketAlreadyOwnedByYou'):
                raise

        # Create timestamped S3 key
        timestamp = datetime.now().strftime('%Y/%m/%d/%H-%M-%S')
        s3_key = f"{s3_prefix}analysis_{timestamp}.json"

        print(f"[INFO] Uploading report to S3...")
        print(f"[INFO] Bucket: {bucket_name}")
        print(f"[INFO] Key: {s3_key}")

        # Read report content
        with open(report_path, encoding='utf-8') as f:
            report_content = f.read()
        
        # Upload to S3
        response = s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=report_content,
            ContentType='application/json',
            # Metadata for tracking
            Metadata={
                'uploaded_at': datetime.now().isoformat(),
                'source': 'cloud-iac-analyzer'
            }
        )
        
        # Check if upload was successful
        status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
        if status_code == 200:
            print(f"[SUCCESS] Report uploaded successfully!")
            print(f"[INFO] S3 Location: s3://{bucket_name}/{s3_key}")
            return True
        else:
            print(f"[ERROR] Upload failed with status code: {status_code}")
            return False
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"[ERROR] AWS Client error ({error_code}): {error_message}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Unexpected error during upload: {str(e)}")
        return False


def main():
    """
    Main entry point for the S3 uploader.
    
    Reads configuration from environment variables and uploads
    the generated report to S3.
    """
    # Get configuration from environment variables with defaults
    report_file = os.getenv('REPORT_FILE', '/app/output/report.json')
    bucket_name = os.getenv('S3_BUCKET', 'analyzer-reports')
    s3_prefix = os.getenv('S3_PREFIX', 'reports/')
    
    print("\n" + "="*60)
    print("Cloud-to-IaC Analyzer - S3 Report Uploader")
    print("="*60 + "\n")
    
    # Attempt to upload the report
    success = upload_report_to_s3(report_file, bucket_name, s3_prefix)
    
    if success:
        print("\n" + "="*60)
        print("[SUCCESS] Report upload completed!")
        print("="*60 + "\n")
        return 0
    else:
        print("\n" + "="*60)
        print("[FAILED] Report upload failed!")
        print("="*60 + "\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
