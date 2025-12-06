# Site Layout Tool - User Guide

## Introduction

The Site Layout Tool automates the planning and design of Battery Energy Storage System (BESS) sites. This guide walks you through the complete workflow from uploading site boundaries to exporting final layouts.

## Getting Started

### 1. Access the Application

- **Production URL:** Your deployed Vercel URL
- **API Documentation:** https://zwt2iazqjv.us-east-1.awsapprunner.com/docs

### 2. Create an Account

1. Navigate to the application
2. Click "Sign Up" or use "Continue with Google"
3. Complete registration with your email and password
4. Verify your email (if required)

### 3. Log In

1. Enter your email and password
2. Or click "Continue with Google" for OAuth login
3. You'll be redirected to the dashboard

## Workflow Overview

```
Upload File → Analyze Terrain → Define Exclusions → Place Assets → Generate Roads → Export
```

## Step-by-Step Guide

### Step 1: Create a Project

1. From the dashboard, click **"New Project"**
2. Enter a project name (e.g., "BESS Site Alpha")
3. Add an optional description
4. Click **"Create"**

### Step 2: Upload Site Boundary

**Supported Formats:**
- KMZ (Google Earth format)
- KML (Keyhole Markup Language)

**How to Upload:**

1. Navigate to your project
2. Click **"Upload File"** or drag and drop
3. Select your KMZ/KML file
4. Wait for validation (the system checks for valid geometry)
5. The boundary will appear on the map

**Tips:**
- Ensure your file contains a valid polygon boundary
- The coordinate system should be WGS84 (EPSG:4326)
- File size limit: 50MB

### Step 3: Analyze Terrain

Terrain analysis extracts elevation, slope, and aspect data for your site.

1. With a valid boundary, click **"Analyze Terrain"**
2. Select the source file if multiple uploads exist
3. Click **"Start Analysis"**
4. Monitor progress (typically 1-5 minutes)

**Analysis Results:**
- **Elevation:** Min, max, mean elevation in meters
- **Slope:** Slope statistics in degrees
- **Aspect:** Cardinal direction distribution
- **Slope Classification:**
  - Flat: 0-2%
  - Gentle: 2-5%
  - Moderate: 5-10%
  - Steep: 10-15%
  - Very Steep: >15%

### Step 4: Define Exclusion Zones

Exclusion zones prevent asset placement in sensitive areas.

**Zone Types:**

| Type | Description | Typical Buffer |
|------|-------------|----------------|
| Wetland | Wetland areas | 50-100m |
| Easement | Property easements | 10-25m |
| Stream Buffer | Water features | 30-100m |
| Setback | Building setbacks | 10-50m |
| Custom | User-defined areas | Variable |

**How to Create:**

1. Click **"Add Exclusion Zone"**
2. Choose the zone type
3. Draw the polygon on the map OR import from file
4. Set buffer distance (optional)
5. Click **"Save"**

**Drawing Tools:**
- Click to add vertices
- Double-click to complete polygon
- Right-click to cancel

### Step 5: Auto-Place Assets

The asset placement algorithm finds optimal locations for BESS containers.

**Configuration:**

1. Click **"Place Assets"**
2. Configure parameters:
   - **Asset Width:** Container width in meters
   - **Asset Length:** Container length in meters
   - **Asset Count:** Number of assets to place
   - **Min Spacing:** Minimum distance between assets
   - **Max Slope:** Maximum allowable slope (degrees)

3. Select optimization criteria:
   - **Minimize Cut/Fill:** Reduce earthwork volume
   - **Maximize Flat Areas:** Prefer level terrain
   - **Minimize Distance:** Cluster assets together
   - **Balanced:** Equal weight to all criteria

4. Click **"Start Placement"**

**Results:**
- Placed asset locations on map
- Success rate percentage
- Average slope at placement locations
- Estimated cut/fill volumes

### Step 6: Generate Road Network

The road network algorithm connects assets and defines access routes.

**Configuration:**

1. Click **"Generate Roads"**
2. Set parameters:
   - **Road Width:** Typical road width (6m default)
   - **Max Grade:** Maximum road slope (12% default)
   - **Min Curve Radius:** Minimum turning radius (15m default)

3. Select entry point on map
4. Choose optimization criteria
5. Click **"Generate"**

**Results:**
- Road centerlines on map
- Total road length
- Grade compliance status
- Estimated earthwork volumes

### Step 7: Export Data

Export your completed layout in various formats.

**Available Formats:**

| Format | Use Case | Contains |
|--------|----------|----------|
| PDF | Client presentations | Full report with maps |
| GeoJSON | Web mapping | All geometries |
| KMZ | Google Earth | 3D visualization |
| DXF | AutoCAD | CAD-compatible |
| CSV | Spreadsheets | Asset coordinates |
| Shapefile | GIS software | All layers |

**How to Export:**

1. Click **"Export"**
2. Select desired format
3. Choose what to include:
   - Terrain analysis
   - Exclusion zones
   - Asset placements
   - Road network
4. Click **"Download"**

## Map Controls

### Navigation
- **Pan:** Click and drag
- **Zoom:** Mouse wheel or +/- buttons
- **Rotate:** Right-click and drag

### Layer Controls
- Toggle visibility of each layer
- Adjust opacity
- Change layer order

### Map Styles
- **Satellite:** Aerial imagery
- **Streets:** Road map
- **Outdoors:** Terrain focused
- **Light/Dark:** Minimal styles

## Best Practices

### File Preparation
1. Clean up geometry in Google Earth or QGIS before upload
2. Ensure boundaries are closed polygons
3. Remove unnecessary features or layers

### Terrain Analysis
1. Allow analysis to complete before starting placement
2. Review slope classification to understand site constraints
3. Consider re-running with different DEM sources if available

### Exclusion Zones
1. Define all exclusions BEFORE asset placement
2. Add appropriate buffers for regulatory compliance
3. Verify zone boundaries match actual site conditions

### Asset Placement
1. Start with fewer assets and increase if needed
2. Adjust max slope based on grading budget
3. Run multiple scenarios with different optimization criteria

### Road Network
1. Place entry point at site access location
2. Consider emergency vehicle access requirements
3. Review grade compliance for equipment transport

## Troubleshooting

### Upload Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid geometry" | Malformed polygon | Repair geometry in GIS software |
| "Unsupported format" | Wrong file type | Convert to KMZ or KML |
| "File too large" | Exceeds 50MB limit | Simplify or split file |

### Analysis Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "No elevation data" | Area not covered | Use different DEM source |
| "Timeout" | Large area | Reduce boundary size |
| "Processing failed" | Server error | Retry or contact support |

### Placement Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "No valid locations" | All area excluded | Reduce exclusion zones or max slope |
| "Low success rate" | Insufficient space | Reduce asset count or spacing |
| "Timeout" | Complex geometry | Simplify exclusion zones |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Cancel current operation |
| `Delete` | Remove selected feature |
| `Ctrl+Z` | Undo last action |
| `Ctrl+S` | Save project |
| `+` / `-` | Zoom in/out |

## Getting Help

- **Documentation:** Check the API docs for technical details
- **Support:** Contact support@pacificoenergy.com
- **Issues:** Report bugs via GitHub Issues
