# resume-optimizer-web — S3 + CloudFront Deployment

Build: `cd ../frontend && npm run build`
Deploy: `aws s3 sync dist/ s3://ro-{env}-web/ --delete`
Invalidate: `aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"`
