# Deployment Guide

This document covers deploying the Site Layout Tool to production.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          INTERNET                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │                                   │
         ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐
│     Vercel      │                 │  AWS App Runner │
│   (Frontend)    │      API        │    (Backend)    │
│   Next.js 15    │ ◄────────────► │    FastAPI      │
└─────────────────┘                 └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │    AWS RDS      │
                                    │  PostgreSQL     │
                                    │   + PostGIS     │
                                    └─────────────────┘
```

## Prerequisites

### Required Accounts
- GitHub account with repository access
- Vercel account
- AWS account with appropriate IAM permissions

### Required Tools
- AWS CLI v2
- Docker Desktop
- Node.js 18+
- Python 3.11+

## Frontend Deployment (Vercel)

### Initial Setup

1. **Connect Repository to Vercel**
   ```bash
   # Install Vercel CLI
   npm i -g vercel

   # Login
   vercel login

   # Link project
   cd frontend
   vercel link
   ```

2. **Configure Environment Variables in Vercel Dashboard**
   - `NEXT_PUBLIC_API_URL`: Backend API URL
   - `NEXT_PUBLIC_MAPBOX_TOKEN`: Mapbox access token

3. **Add GitHub Secrets**
   ```
   VERCEL_TOKEN: Your Vercel token
   VERCEL_ORG_ID: From .vercel/project.json
   VERCEL_PROJECT_ID: From .vercel/project.json
   ```

### Automatic Deployment

Pushes to `master` branch trigger automatic deployment via GitHub Actions:
- Runs linting and type checking
- Builds the application
- Deploys to Vercel production

### Manual Deployment

```bash
cd frontend
vercel --prod
```

## Backend Deployment (AWS)

### AWS Resources Required

1. **ECR Repository**
   ```bash
   aws ecr create-repository \
     --repository-name site-layout-optimizer-backend \
     --region us-east-1
   ```

2. **RDS PostgreSQL with PostGIS**
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier sitelayout-db \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --engine-version 14.9 \
     --master-username postgres \
     --master-user-password <password> \
     --allocated-storage 20 \
     --region us-east-1
   ```

   Enable PostGIS:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

3. **VPC Connector (for RDS access)**
   ```bash
   aws apprunner create-vpc-connector \
     --vpc-connector-name sitelayout-vpc-connector \
     --subnets subnet-xxx subnet-yyy \
     --security-groups sg-xxx
   ```

4. **App Runner Service**
   - Create via AWS Console or CLI
   - Connect to ECR repository
   - Enable auto-deployments on ECR push
   - Attach VPC connector

### Environment Variables (App Runner)

Configure these in the App Runner service:

```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
SECRET_KEY=<generate with openssl rand -hex 32>
ALGORITHM=HS256
ALLOWED_ORIGINS=["https://your-frontend.vercel.app"]
GOOGLE_CLIENT_ID=<optional>
GOOGLE_CLIENT_SECRET=<optional>
```

### GitHub Secrets

```
AWS_ACCESS_KEY_ID: IAM user access key
AWS_SECRET_ACCESS_KEY: IAM user secret key
```

### Deployment Flow

1. Push to `master` branch
2. GitHub Actions:
   - Runs tests and linting
   - Builds Docker image
   - Pushes to ECR
3. App Runner detects new image
4. Deploys automatically

### Manual Deployment

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
cd backend
docker build --platform linux/amd64 -t site-layout-optimizer-backend .
docker tag site-layout-optimizer-backend:latest \
  <account>.dkr.ecr.us-east-1.amazonaws.com/site-layout-optimizer-backend:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/site-layout-optimizer-backend:latest
```

## Database Migrations

### Running Migrations

Migrations run automatically on container startup via `start.sh`:

```bash
#!/bin/bash
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Manual Migration

```bash
# SSH into a running container or use bastion host
cd /app
alembic upgrade head
```

### Creating New Migrations

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
```

## Monitoring

### Health Checks

- **Basic:** `GET /health` - Returns `{"status": "healthy"}`
- **Database:** `GET /health/db` - Checks database connectivity

### AWS CloudWatch

App Runner automatically logs to CloudWatch:
- Application logs
- Request metrics
- Resource utilization

### Vercel Analytics

Enable in Vercel dashboard for:
- Web vitals
- Request analytics
- Error tracking

## Rollback Procedures

### Frontend (Vercel)

1. Go to Vercel Dashboard → Deployments
2. Find previous working deployment
3. Click "Promote to Production"

### Backend (App Runner)

1. Push a fix to `master` (auto-deploys)
2. Or manually push previous image to ECR

### Database

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

## Security Checklist

- [ ] All secrets stored in environment variables
- [ ] HTTPS enabled (automatic on Vercel and App Runner)
- [ ] CORS properly configured
- [ ] Database password meets complexity requirements
- [ ] IAM permissions follow least privilege
- [ ] Security groups restrict database access
- [ ] Rate limiting enabled
- [ ] JWT tokens have appropriate expiry

## Troubleshooting

### App Runner Deployment Fails

1. Check CloudWatch logs
2. Verify Docker build works locally
3. Check ECR image was pushed successfully
4. Verify environment variables are set

### Database Connection Issues

1. Check VPC connector is attached
2. Verify security group allows traffic from App Runner
3. Test connection from bastion host
4. Check DATABASE_URL format

### Frontend Build Fails

1. Check Vercel build logs
2. Verify all dependencies are in package.json
3. Check environment variables are set
4. Test build locally: `pnpm build`

## Cost Optimization

### App Runner
- Use minimum instance size (0.25 vCPU, 0.5 GB)
- Enable auto-pause for non-production
- Monitor and right-size based on usage

### RDS
- Use smallest instance for dev/staging
- Enable auto-pause for development
- Use reserved instances for production

### ECR
- Set lifecycle policies to clean old images
- Limit image retention to last 10 versions

## Useful Commands

```bash
# Check App Runner service status
aws apprunner describe-service \
  --service-arn arn:aws:apprunner:us-east-1:xxx:service/sitelayout-backend/xxx

# View recent logs
aws logs tail /aws/apprunner/sitelayout-backend --since 1h

# Check ECR images
aws ecr describe-images \
  --repository-name site-layout-optimizer-backend \
  --query 'imageDetails[*].[imagePushedAt,imageTags]'

# Test database connectivity
curl https://zwt2iazqjv.us-east-1.awsapprunner.com/health/db
```
