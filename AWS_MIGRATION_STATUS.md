# AWS Migration Status - SiteLayout

## Completed Tasks ✅

### 1. RDS PostgreSQL Database
- **Instance ID**: `sitelayout-db`
- **Endpoint**: `sitelayout-db.c1uuigcm4bd1.us-east-2.rds.amazonaws.com:5432`
- **Database Name**: `sitelayout`
- **Engine**: PostgreSQL 16.8
- **PostGIS Version**: 3.4
- **Status**: Available and fully configured
- **Security Group**: `sg-0e34638c2e6dab8ed` (PostgreSQL port 5432 open)

### 2. AWS Secrets Manager
- **Database Credentials**: `arn:aws:secretsmanager:us-east-2:971422717446:secret:sitelayout/database-ltJJXv`
- **App Secrets**: `arn:aws:secretsmanager:us-east-2:971422717446:secret:sitelayout/app-secrets-Axff3E`

### 3. ECR Repository
- **Repository Name**: `sitelayout-backend`
- **URI**: `971422717446.dkr.ecr.us-east-2.amazonaws.com/sitelayout-backend`
- **Images Pushed**: `latest`, `v1.0.0`
- **Image Size**: 1.74GB

### 4. VPC Connector
- **Name**: `sitelayout-vpc-connector`
- **ARN**: `arn:aws:apprunner:us-east-2:971422717446:vpcconnector/sitelayout-vpc-connector/1/2f83366a30fa42999b585880c9b1bcd5`
- **Status**: ACTIVE

### 5. App Runner Service (In Progress)
- **Service Name**: `sitelayout-backend`
- **Service ARN**: `arn:aws:apprunner:us-east-2:971422717446:service/sitelayout-backend/5c325119796f4de0900cf54d310bfeaf`
- **Service URL**: `https://psuxmxth9f.us-east-2.awsapprunner.com`
- **Status**: Deploying...
- **Note**: Needs VPC connector association and health check update

### 6. GitHub Actions
- ✅ Updated `.github/workflows/backend-ci.yml` for AWS deployment
- ✅ Configured ECR build and push
- ✅ Added App Runner deployment automation
- ✅ Dockerfile fixed with build tools for geospatial libraries

## Next Steps 🚀

### Option 1: Build and Push Docker Image Locally
1. **Start Docker Desktop** on your machine
2. **Build and push the image**:
   ```bash
   cd /Users/zeno/Projects/sitelayout/backend
   docker build -t 971422717446.dkr.ecr.us-east-2.amazonaws.com/sitelayout-backend:latest .
   docker push 971422717446.dkr.ecr.us-east-2.amazonaws.com/sitelayout-backend:latest
   ```

### Option 2: Use GitHub Actions (Recommended)
1. **Add AWS credentials to GitHub Secrets**:
   - Go to your repository settings
   - Navigate to Secrets and variables → Actions
   - Add these secrets:
     - `AWS_ACCESS_KEY_ID`: [From your AWS credentials]
     - `AWS_SECRET_ACCESS_KEY`: [From your AWS credentials]

2. **Commit and push changes**:
   ```bash
   git add .github/workflows/backend-ci.yml
   git commit -m "Update CI/CD for AWS deployment"
   git push origin main
   ```

3. **GitHub Actions will automatically**:
   - Build the Docker image
   - Push to ECR
   - Deploy to App Runner (once service is created)

## Remaining Tasks

### 8. Create AWS App Runner Service
Once you have a Docker image in ECR, run:
```bash
aws apprunner create-service \
  --service-name sitelayout-backend \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "971422717446.dkr.ecr.us-east-2.amazonaws.com/sitelayout-backend:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "DATABASE_URL": "postgresql://sitelayout_admin:u0th2i*9LRjR[G4g-m^4[5,A2iqSw2GA@sitelayout-db.c1uuigcm4bd1.us-east-2.rds.amazonaws.com:5432/sitelayout",
          "SECRET_KEY": "VwIROk7i7vEQgHfsEApunaB3AuEnDunyru0LupCbJXtWVPFHj8avMOOH5560x7Wb",
          "ALGORITHM": "HS256",
          "ACCESS_TOKEN_EXPIRE_MINUTES": "10080",
          "ENVIRONMENT": "production",
          "DEBUG": "False"
        }
      }
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{
    "Cpu": "1024",
    "Memory": "2048"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }' \
  --tags "Key=Project,Value=sitelayout"
```

### 9. Configure VPC Connector
After creating App Runner service, connect it to the VPC for RDS access.

### 10. Run Alembic Migrations
Once App Runner is deployed, run migrations:
```bash
# From your local machine or via App Runner console
alembic upgrade head
```

### 11. Update Vercel Frontend
Update the API URL environment variable in Vercel to point to your App Runner service URL.

## Important Credentials 🔐

**⚠️ SAVE THESE SECURELY - They are also stored in AWS Secrets Manager**

### Database
- **Username**: `sitelayout_admin`
- **Password**: `u0th2i*9LRjR[G4g-m^4[5,A2iqSw2GA`
- **Connection String**:
  ```
  postgresql://sitelayout_admin:u0th2i*9LRjR[G4g-m^4[5,A2iqSw2GA@sitelayout-db.c1uuigcm4bd1.us-east-2.rds.amazonaws.com:5432/sitelayout
  ```

### Application
- **Secret Key**: `VwIROk7i7vEQgHfsEApunaB3AuEnDunyru0LupCbJXtWVPFHj8avMOOH5560x7Wb`

## Resources
- **AWS Region**: `us-east-2`
- **AWS Account**: `971422717446`
