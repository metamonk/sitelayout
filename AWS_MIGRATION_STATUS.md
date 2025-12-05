# AWS Migration Status - SiteLayout

## DEPLOYMENT COMPLETE

**Backend API**: https://zwt2iazqjv.us-east-1.awsapprunner.com
**Status**: RUNNING
**Region**: US-EAST-1 (consolidated)
**Last Updated**: 2025-12-05

## Infrastructure (All US-EAST-1)

### 1. App Runner Service
- **Service Name**: `sitelayout-backend`
- **Service ARN**: `arn:aws:apprunner:us-east-1:971422717446:service/sitelayout-backend/c39b2ac6475147a6b6352c2b28b43b1e`
- **Service URL**: `https://zwt2iazqjv.us-east-1.awsapprunner.com`
- **Status**: RUNNING
- **Auto-deployments**: Enabled (triggers on ECR image push)
- **Instance Config**: 1024 CPU, 2048 MB RAM

### 2. ECR Repository
- **Repository Name**: `site-layout-optimizer-backend`
- **URI**: `971422717446.dkr.ecr.us-east-1.amazonaws.com/site-layout-optimizer-backend`
- **Image Architecture**: `linux/amd64`

### 3. RDS PostgreSQL Database
- **Instance ID**: `sitelayout-db`
- **Endpoint**: `sitelayout-db.crws0amqe1e3.us-east-1.rds.amazonaws.com:5432`
- **Database Name**: `sitelayout`
- **Engine**: PostgreSQL 16.10
- **PostGIS Version**: 3.4
- **Instance Class**: db.t3.micro
- **Storage**: 20 GB gp3
- **Status**: Available

### 4. GitHub Actions CI/CD
- Configured in `.github/workflows/backend-ci.yml`
- Auto-deploys on push to `master` branch
- Builds Docker image and pushes to ECR
- App Runner auto-deploys from ECR

## API Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/` | GET | API info | Working |
| `/health` | GET | Health check | Working |

## Environment Variables

Configured in App Runner:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key |
| `ALGORITHM` | JWT algorithm (HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration (10080 = 7 days) |
| `ENVIRONMENT` | production |
| `DEBUG` | False |
| `ALLOWED_ORIGINS` | `["http://localhost:3000","https://*.vercel.app","https://sitelayout.vercel.app"]` |
| `MAX_UPLOAD_SIZE` | 52428800 (50MB) |
| `UPLOAD_DIR` | /tmp/uploads |

## Frontend (Vercel)

- **Project**: https://vercel.com/ratlabs/sitelayout
- **Environment Variables**:
  - `NEXT_PUBLIC_API_URL`: `https://zwt2iazqjv.us-east-1.awsapprunner.com`
  - `NEXT_PUBLIC_MAPBOX_TOKEN`: (set in Vercel dashboard)

## Important Credentials

**Database**
- **Username**: `sitelayout_admin`
- **Password**: `V6NcaBXMu13PvPPkfgHIgwd5iUq34F`
- **Connection String**:
  ```
  postgresql://sitelayout_admin:V6NcaBXMu13PvPPkfgHIgwd5iUq34F@sitelayout-db.crws0amqe1e3.us-east-1.rds.amazonaws.com:5432/sitelayout
  ```

**Application**
- **Secret Key**: `VwIROk7i7vEQgHfsEApunaB3AuEnDunyru0LupCbJXtWVPFHj8avMOOH5560x7Wb`

## Resources
- **Region**: `us-east-1` (all resources consolidated)
- **AWS Account**: `971422717446`
