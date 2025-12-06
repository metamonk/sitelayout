# Site Layout API Documentation

## Overview

The Site Layout API provides RESTful endpoints for managing BESS (Battery Energy Storage System) site layout projects. The API includes terrain analysis, asset placement, road network generation, and data export capabilities.

**Base URL:** `https://zwt2iazqjv.us-east-1.awsapprunner.com`
**Interactive Docs:** [Swagger UI](https://zwt2iazqjv.us-east-1.awsapprunner.com/docs) | [ReDoc](https://zwt2iazqjv.us-east-1.awsapprunner.com/redoc)

## Authentication

The API uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_token>
```

### Endpoints

#### Register a new user
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepassword
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Get current user
```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

## Projects

### Create Project
```http
POST /api/v1/projects
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "BESS Site Alpha",
  "description": "100MW battery storage project"
}
```

### List Projects
```http
GET /api/v1/projects?page=1&page_size=20
Authorization: Bearer <token>
```

### Get Project
```http
GET /api/v1/projects/{project_id}
Authorization: Bearer <token>
```

### Update Project
```http
PATCH /api/v1/projects/{project_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Name",
  "status": "analyzed"
}
```

### Delete Project
```http
DELETE /api/v1/projects/{project_id}
Authorization: Bearer <token>
```

## File Upload

### Upload KMZ/KML File
```http
POST /api/v1/files/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <your_kmz_or_kml_file>
```

**Response:**
```json
{
  "id": "uuid",
  "filename": "site_boundary.kmz",
  "status": "valid",
  "geometry_type": "Polygon",
  "feature_count": 1,
  "boundary": {
    "type": "Feature",
    "geometry": {...}
  }
}
```

### List Files
```http
GET /api/v1/files
Authorization: Bearer <token>
```

### Delete File
```http
DELETE /api/v1/files/{filename}
Authorization: Bearer <token>
```

## Terrain Analysis

### Start Terrain Analysis
```http
POST /api/v1/projects/{project_id}/terrain/analyze
Authorization: Bearer <token>
Content-Type: application/json

{
  "source_file_id": "uuid-of-uploaded-file"
}
```

### Get Terrain Analysis Status
```http
GET /api/v1/projects/{project_id}/terrain/{analysis_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "uuid",
  "status": "completed",
  "progress_percent": 100,
  "elevation_min": 100.5,
  "elevation_max": 150.2,
  "elevation_mean": 125.3,
  "slope_min": 0.0,
  "slope_max": 15.5,
  "slope_mean": 3.2,
  "slope_classification": {
    "flat": 25.0,
    "gentle": 45.0,
    "moderate": 20.0,
    "steep": 8.0,
    "very_steep": 2.0
  }
}
```

### Get Terrain Tiles
```http
GET /api/v1/projects/{project_id}/terrain/{analysis_id}/tiles/{z}/{x}/{y}
Authorization: Bearer <token>
```

## Exclusion Zones

### Create Exclusion Zone
```http
POST /api/v1/projects/{project_id}/exclusion-zones
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Wetland Area",
  "zone_type": "wetland",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lon, lat], ...]]
  },
  "buffer_distance": 50
}
```

**Zone Types:**
- `wetland` - Wetland areas
- `easement` - Property easements
- `stream_buffer` - Stream/river buffers
- `setback` - Building setbacks
- `custom` - Custom exclusion zones

### List Exclusion Zones
```http
GET /api/v1/projects/{project_id}/exclusion-zones
Authorization: Bearer <token>
```

### Update Exclusion Zone
```http
PUT /api/v1/projects/{project_id}/exclusion-zones/{zone_id}
Authorization: Bearer <token>
```

### Delete Exclusion Zone
```http
DELETE /api/v1/projects/{project_id}/exclusion-zones/{zone_id}
Authorization: Bearer <token>
```

## Asset Placement

### Start Asset Placement
```http
POST /api/v1/projects/{project_id}/asset-placement
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Battery Container Layout",
  "terrain_analysis_id": "uuid",
  "asset_width": 12.0,
  "asset_length": 2.5,
  "asset_count": 50,
  "min_spacing": 10.0,
  "max_slope": 5.0,
  "optimization_criteria": "balanced"
}
```

**Optimization Criteria:**
- `minimize_cut_fill` - Minimize earthwork
- `maximize_flat_areas` - Prefer flatter areas
- `minimize_inter_asset_distance` - Cluster assets together
- `balanced` - Balance all criteria

### Get Placement Status
```http
GET /api/v1/projects/{project_id}/asset-placement/{placement_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "uuid",
  "status": "completed",
  "assets_placed": 48,
  "assets_requested": 50,
  "placement_success_rate": 96.0,
  "avg_slope": 2.1,
  "total_cut_fill_volume": 1500.5,
  "placement_details": [
    {"id": 1, "position": [-98.5, 35.2], "elevation": 120.5, "slope": 1.8},
    ...
  ]
}
```

## Road Network

### Generate Road Network
```http
POST /api/v1/projects/{project_id}/road-network
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Access Roads",
  "terrain_analysis_id": "uuid",
  "asset_placement_id": "uuid",
  "road_width": 6.0,
  "max_grade": 12.0,
  "min_curve_radius": 15.0,
  "optimization_criteria": "balanced"
}
```

### Get Road Network Status
```http
GET /api/v1/projects/{project_id}/road-network/{network_id}
Authorization: Bearer <token>
```

## Exports

### Export PDF Report
```http
POST /api/v1/projects/{project_id}/export/pdf
Authorization: Bearer <token>
Content-Type: application/json

{
  "include_terrain": true,
  "include_assets": true,
  "include_roads": true,
  "include_exclusions": true
}
```

### Export GeoJSON
```http
GET /api/v1/projects/{project_id}/export/geojson
Authorization: Bearer <token>
```

### Export KMZ
```http
POST /api/v1/projects/{project_id}/export/kmz
Authorization: Bearer <token>
```

### Export DXF (AutoCAD)
```http
POST /api/v1/projects/{project_id}/export/dxf
Authorization: Bearer <token>
```

### Export CSV
```http
GET /api/v1/projects/{project_id}/export/csv?type=assets
Authorization: Bearer <token>
```

### Export Shapefile
```http
GET /api/v1/projects/{project_id}/export/shapefile
Authorization: Bearer <token>
```

## Health Checks

### Basic Health
```http
GET /health
```

**Response:**
```json
{"status": "healthy"}
```

### Database Health
```http
GET /health/db
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "postgis_version": "3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1"
}
```

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message",
  "code": "ERROR_CODE"
}
```

### Common Error Codes

| Status Code | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Access denied |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid data format |
| 500 | Internal Server Error |

## Rate Limiting

The API implements rate limiting of 100 requests per minute per user. Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699123456
```

## WebSocket Support

Real-time progress updates are available via WebSocket for long-running operations:

```javascript
const ws = new WebSocket('wss://api-url/ws/progress/{operation_id}');
ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Progress: ${progress.percent}%`);
};
```
