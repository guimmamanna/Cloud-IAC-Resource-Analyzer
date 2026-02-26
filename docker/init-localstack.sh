#!/bin/bash
# Creates the S3 bucket used for storing analysis reports.
# Runs automatically inside LocalStack on startup via /docker-entrypoint-initaws.d/

AWS_CMD="aws --endpoint-url=http://localhost:4566 --region us-east-1"
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

echo "Creating S3 bucket: analyzer-reports"
$AWS_CMD s3 mb s3://analyzer-reports

echo "Enabling versioning on analyzer-reports"
$AWS_CMD s3api put-bucket-versioning \
    --bucket analyzer-reports \
    --versioning-configuration Status=Enabled

echo "LocalStack initialization completed!"
