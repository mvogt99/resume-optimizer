# resume-optimizer-web

Static frontend distribution via S3 + CloudFront.

## Purpose

Serves React web application (built from ../frontend).

## Deployment

No container. Built static files distributed to S3, cached via CloudFront CDN.

## Build
```bash
cd ../frontend
npm run build
# Output: dist/
```

## Deploy
```bash
aws s3 sync dist/ s3://ro-prod-web/ --delete
aws cloudfront create-invalidation --distribution-id E123ABC --paths "/*"
```
