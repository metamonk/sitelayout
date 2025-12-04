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
- **Backend Hosting**: Railway
- **CI/CD**: GitHub Actions
- **Version Control**: Git

## Features (Phase 1)

### ✅ Completed
- [x] Project repository structure
- [x] Frontend setup with Next.js and TypeScript
- [x] Backend setup with FastAPI and geospatial dependencies
- [x] PostgreSQL database schema with PostGIS
- [x] CI/CD pipelines (GitHub Actions)
- [x] Deployment configurations (Vercel + Railway)
- [x] Database migrations with Alembic

### 🚧 In Progress
- [ ] User authentication system (email/password + Google OAuth)
- [ ] File upload interface (KMZ/KML)
- [ ] Backend file validation and storage
- [ ] Terrain analysis engine
- [ ] Asset auto-placement
- [ ] Road network generation
- [ ] Cut/fill volume estimation
- [ ] Map visualization
- [ ] Export and reporting

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

### Backend (Railway)

The backend deploys automatically to Railway on push to the `main` branch.

**Required Secrets:**
- `RAILWAY_TOKEN`

**Environment Variables (Railway):**
- `DATABASE_URL` - Provided by Railway's PostgreSQL service
- `SECRET_KEY` - Generate with `openssl rand -hex 32`
- `ALLOWED_ORIGINS` - Your frontend URL
- `GOOGLE_CLIENT_ID` - For OAuth
- `GOOGLE_CLIENT_SECRET` - For OAuth

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

- [Frontend README](./frontend/README.md)
- [Backend README](./backend/README.md)
- [API Documentation](http://localhost:8000/docs) (when running locally)
- [Product Requirements](/.taskmaster/docs/prd.md)
- [Architecture](/.taskmaster/docs/architecture.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Phase 1 Summary](./PHASE1_SUMMARY.md)

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
