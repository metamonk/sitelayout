# Site Layout Tool - Pacifico Energy

Automated site layout generation for Battery Energy Storage Systems (BESS) projects. This tool streamlines the planning process by automating terrain analysis, asset placement, road network generation, and earthwork volume estimation.

## Project Structure

```
sitelayout/
├── frontend/          # Next.js frontend application
├── backend/           # FastAPI backend application
├── .github/           # GitHub Actions CI/CD workflows
└── .taskmaster/       # Task management and project planning
```

## Tech Stack

### Frontend
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Map Rendering**: Deck.gl + Mapbox GL
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL 14+ with PostGIS extension
- **ORM**: SQLAlchemy + GeoAlchemy2
- **Geospatial**: GeoPandas, Shapely, Rasterio
- **Authentication**: JWT + Google OAuth
- **Migrations**: Alembic

### Infrastructure
- **Frontend Hosting**: Vercel
- **Backend Hosting**: AWS App Runner (with ECR)
- **Database**: AWS RDS PostgreSQL with PostGIS
- **CI/CD**: GitHub Actions
- **Version Control**: Git

## Features

### ✅ Core Features
- [x] User authentication (JWT + Google OAuth)
- [x] Project management (create, list, update, delete)
- [x] File upload interface (KMZ/KML) with validation
- [x] Interactive map visualization (Deck.gl + Mapbox)
- [x] Terrain analysis engine (elevation, slope, aspect)
- [x] Exclusion zone management (wetlands, easements, setbacks)
- [x] Asset auto-placement algorithm
- [x] Road network generation
- [x] Cut/fill volume estimation
- [x] Export and reporting (PDF, GeoJSON, KMZ, DXF, CSV, Shapefile)

### ✅ Infrastructure
- [x] CI/CD pipelines (GitHub Actions)
- [x] Frontend deployment (Vercel)
- [x] Backend deployment (AWS App Runner + ECR)
- [x] Database hosting (AWS RDS PostgreSQL + PostGIS)
- [x] Database migrations (Alembic)
- [x] Performance optimization (indexes, caching)

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL 14+ with PostGIS
- pnpm (for frontend)

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd sitelayout
```

2. **Set up the frontend**
```bash
cd frontend
pnpm install
cp .env.example .env.local
# Edit .env.local with your configuration
pnpm dev
```

3. **Set up the backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration

# Set up database
createdb sitelayout
psql sitelayout -c "CREATE EXTENSION IF NOT EXISTS postgis;"
alembic upgrade head

# Run server
uvicorn app.main:app --reload
```

4. **Access the applications**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Deployment

### Frontend (Vercel)

The frontend deploys automatically to Vercel on push to the `main` branch.

**Required Secrets:**
- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_MAPBOX_TOKEN`

### Backend (AWS App Runner)

The backend deploys automatically to AWS App Runner on push to the `master` branch.

**Required GitHub Secrets:**
- `AWS_ACCESS_KEY_ID` - AWS credentials
- `AWS_SECRET_ACCESS_KEY` - AWS credentials

**AWS Resources:**
- ECR Repository: `site-layout-optimizer-backend`
- App Runner Service: `sitelayout-backend`
- RDS PostgreSQL with PostGIS extension

**Environment Variables (App Runner):**
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Generate with `openssl rand -hex 32`
- `ALGORITHM` - JWT algorithm (HS256)
- `ALLOWED_ORIGINS` - Frontend URLs (JSON array)
- `GOOGLE_CLIENT_ID` - For OAuth
- `GOOGLE_CLIENT_SECRET` - For OAuth

**Live API Endpoints:**
- API URL: `https://zwt2iazqjv.us-east-1.awsapprunner.com`
- Health: `https://zwt2iazqjv.us-east-1.awsapprunner.com/health`
- API Docs: `https://zwt2iazqjv.us-east-1.awsapprunner.com/docs`

## Development Workflow

1. **Create a feature branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make changes and commit**
```bash
git add .
git commit -m "feat: your feature description"
```

3. **Push and create PR**
```bash
git push origin feature/your-feature-name
```

4. **CI/CD will automatically:**
- Run linters (ESLint, Black, Flake8)
- Run type checks (TypeScript, mypy)
- Run tests (pytest)
- Build the application
- Deploy to preview environment (Vercel)

5. **On merge to main:**
- Deploy frontend to Vercel production
- Deploy backend to Railway production

## Testing

### Frontend
```bash
cd frontend
pnpm lint
pnpm type-check
pnpm build
```

### Backend
```bash
cd backend
pytest
pytest --cov=app tests/
black --check .
flake8 .
mypy app
```

## Documentation

- [API Documentation](./docs/API.md) - Complete API reference
- [User Guide](./docs/USER_GUIDE.md) - Step-by-step usage instructions
- [Deployment Guide](./docs/DEPLOYMENT.md) - Production deployment guide
- [Interactive API Docs](https://zwt2iazqjv.us-east-1.awsapprunner.com/docs) - Swagger UI
- [Product Requirements](/.taskmaster/docs/prd.md)
- [Architecture](/.taskmaster/docs/architecture.md)

## Task Management

This project uses Task Master AI for task tracking and management. View tasks:

```bash
# View all tasks
taskmaster get-tasks

# View next task
taskmaster next-task

# View specific task
taskmaster get-task 1
```

## Contributing

1. Follow the existing code style
2. Write tests for new features
3. Update documentation as needed
4. Ensure CI/CD passes before requesting review

## License

Proprietary - Pacifico Energy Group

## Support

For issues or questions, please contact the development team or create an issue in the repository.
