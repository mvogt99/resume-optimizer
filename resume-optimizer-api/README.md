# resume-optimizer-api

Flask-to-Lambda bridge for resume-optimizer service.

## Purpose

Provides HTTP endpoints for:
- Resume upload + S3 storage
- Analysis job submission to SQS
- Status polling for long-running jobs

## Deployment

### Local Development
```bash
cd resume-optimizer-api
python -m flask run
```

### Production (AWS Lambda)
Built as OCI image, pushed to ECR, deployed to Lambda via CloudFormation.

### Environment Variables
- CLOUDLIFT_ENV: "aws" or "local" (default: local)
- AWS_REGION: us-east-1 (default)
- SQS_QUEUE_URL: ARN of analysis request queue
- S3_BUCKET: resume uploads bucket
