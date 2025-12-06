import type { Feature, FeatureCollection, Geometry, GeoJsonProperties } from 'geojson';

// Zone types matching backend
export type ZoneType = 'wetland' | 'easement' | 'stream_buffer' | 'setback' | 'custom';
export type ZoneSource = 'imported' | 'drawn';

// Zone colors for display
export const ZONE_COLORS: Record<ZoneType, { fill: [number, number, number, number]; stroke: [number, number, number, number] }> = {
  wetland: { fill: [59, 130, 246, 120], stroke: [37, 99, 235, 255] },        // Blue
  easement: { fill: [249, 115, 22, 120], stroke: [234, 88, 12, 255] },       // Orange
  stream_buffer: { fill: [34, 211, 238, 120], stroke: [6, 182, 212, 255] },  // Cyan
  setback: { fill: [156, 163, 175, 120], stroke: [107, 114, 128, 255] },     // Gray
  custom: { fill: [168, 85, 247, 120], stroke: [147, 51, 234, 255] },        // Purple
};

export const ZONE_LABELS: Record<ZoneType, string> = {
  wetland: 'Wetland',
  easement: 'Easement',
  stream_buffer: 'Stream Buffer',
  setback: 'Setback',
  custom: 'Custom Zone',
};

// Exclusion zone from API
export interface ExclusionZone {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  zone_type: ZoneType;
  source: ZoneSource;
  geometry: Geometry;
  geometry_type: string;
  buffer_distance?: number;
  buffer_applied: boolean;
  buffered_geometry?: Geometry;
  fill_color?: string;
  stroke_color?: string;
  fill_opacity?: number;
  area_sqm?: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

// Create/update zone request
export interface ExclusionZoneCreate {
  name: string;
  description?: string;
  zone_type: ZoneType;
  geometry: Geometry;
  buffer_distance?: number;
  fill_color?: string;
  stroke_color?: string;
  fill_opacity?: number;
}

export interface ExclusionZoneUpdate {
  name?: string;
  description?: string;
  zone_type?: ZoneType;
  buffer_distance?: number;
  is_active?: boolean;
  fill_color?: string;
  stroke_color?: string;
  fill_opacity?: number;
}

// Map view state
export interface MapViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

// Layer visibility state
export interface LayerVisibility {
  siteBoundary: boolean;
  exclusionZones: boolean;
  terrain: boolean;
  satellite: boolean;
}

// Project boundary from uploaded file
export interface ProjectBoundary {
  id: string;
  name: string;
  geometry: Geometry;
  geometry_type: string;
}

// Convert exclusion zone to GeoJSON feature
export function zoneToFeature(zone: ExclusionZone): Feature<Geometry, GeoJsonProperties> {
  return {
    type: 'Feature',
    id: zone.id,
    properties: {
      id: zone.id,
      name: zone.name,
      zone_type: zone.zone_type,
      source: zone.source,
      buffer_distance: zone.buffer_distance,
      buffer_applied: zone.buffer_applied,
      area_sqm: zone.area_sqm,
      is_active: zone.is_active,
    },
    geometry: zone.buffer_applied && zone.buffered_geometry
      ? zone.buffered_geometry
      : zone.geometry,
  };
}

// Convert zones array to FeatureCollection
export function zonesToFeatureCollection(zones: ExclusionZone[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: zones.filter(z => z.is_active).map(zoneToFeature),
  };
}

// Get color for zone type
export function getZoneColor(zoneType: ZoneType) {
  return ZONE_COLORS[zoneType] || ZONE_COLORS.custom;
}
