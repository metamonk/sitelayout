# AWS Migration Status - SiteLayout

## DEPLOYMENT COMPLETE

**Backend API**: https://zwt2iazqjv.us-east-1.awsapprunner.com
**Status**: RUNNING
**Last Updated**: 2025-12-05

## Infrastructure

### 1. App Runner Service (US-EAST-1)
- **Service Name**: `sitelayout-backend`
- **Service ARN**: `arn:aws:apprunner:us-east-1:971422717446:service/sitelayout-backend/c39b2ac6475147a6b6352c2b28b43b1e`
- **Service URL**: `https://zwt2iazqjv.us-east-1.awsapprunner.com`
- **Status**: RUNNING
- **Auto-deployments**: Enabled (triggers on ECR image push)
- **Instance Config**: 1024 CPU, 2048 MB RAM

### 2. ECR Repository (US-EAST-1)
- **Repository Name**: `site-layout-optimizer-backend`
- **URI**: `971422717446.dkr.ecr.us-east-1.amazonaws.com/site-layout-optimizer-backend`
- **Image Architecture**: `linux/amd64`

### 3. RDS PostgreSQL Database (US-EAST-2)
- **Instance ID**: `sitelayout-db`
- **Endpoint**: `sitelayout-db.c1uuigcm4bd1.us-east-2.rds.amazonaws.com:5432`
- **Database Name**: `sitelayout`
- **Engine**: PostgreSQL 16.8
- **PostGIS Version**: 3.4
- **Status**: Available
- **Publicly Accessible**: Yes (for cross-region App Runner access)

### 4. AWS Secrets Manager (US-EAST-2)
- **Database Credentials**: `arn:aws:secretsmanager:us-east-2:971422717446:secret:sitelayout/database-ltJJXv`
- **App Secrets**: `arn:aws:secretsmanager:us-east-2:971422717446:secret:sitelayout/app-secrets-Axff3E`

### 5. GitHub Actions CI/CD
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
| `DATABASE_URL` | PostgreSQL connection string (us-east-2) |
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
- **Password**: `u0th2i*9LRjR[G4g-m^4[5,A2iqSw2GA`
- **Connection String**:
  ```
  postgresql://sitelayout_admin:u0th2i*9LRjR[G4g-m^4[5,A2iqSw2GA@sitelayout-db.c1uuigcm4bd1.us-east-2.rds.amazonaws.com:5432/sitelayout
  ```

**Application**
- **Secret Key**: `VwIROk7i7vEQgHfsEApunaB3AuEnDunyru0LupCbJXtWVPFHj8avMOOH5560x7Wb`

## Resources
- **App Runner Region**: `us-east-1`
- **Database Region**: `us-east-2`
- **AWS Account**: `971422717446`
