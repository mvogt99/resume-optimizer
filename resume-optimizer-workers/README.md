# resume-optimizer-workers

Fargate-based worker pool for long-running analysis jobs.

## Purpose

Consumes resume analysis tasks from SQS, invokes Bedrock models, stores results in S3.

## Architecture

- Deployed to ECS Fargate cluster (shared)
- Scales horizontally based on SQS queue depth (CloudWatch autoscaling)
- Uses IAM service role for S3 + Bedrock + SQS access

## Local Development
```bash
CLOUDLIFT_ENV=local python -m workers.analysis_worker
```

## Production
Built as OCI image, pushed to ECR, deployed to ECS Fargate task definition via CloudFormation.
