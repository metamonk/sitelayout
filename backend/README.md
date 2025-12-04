# Site Layout Backend

FastAPI backend for automated site layout generation.

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL + PostGIS
- **ORM**: SQLAlchemy + GeoAlchemy2
- **Migrations**: Alembic
- **Geospatial**: GeoPandas, Shapely, Rasterio
- **Authentication**: JWT + Google OAuth
- **Testing**: pytest

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with PostGIS extension

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

```bash
# Create database
createdb sitelayout

# Enable PostGIS extension
psql sitelayout -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Run migrations
alembic upgrade head
```

### Development

```bash
# Run development server
uvicorn app.main:app --reload

# Or use the main.py
python -m app.main
```

API will be available at http://localhost:8000

Interactive docs at http://localhost:8000/docs

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT secret key (generate with `openssl rand -hex 32`)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: OAuth credentials

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Testing

```bash
pytest
pytest --cov=app tests/
```

## Deployment

Deployed automatically to Railway on push to main branch.
