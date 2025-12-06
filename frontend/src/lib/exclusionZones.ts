import { api } from './api';
import type {
  ExclusionZone,
  ExclusionZoneCreate,
  ExclusionZoneUpdate,
} from '@/types/map';

export interface ExclusionZoneListResponse {
  zones: ExclusionZone[];
  total: number;
}

export interface ExclusionZoneImportRequest {
  source_file_id: string;
  zone_type: string;
  name_prefix?: string;
  buffer_distance?: number;
}

export interface ExclusionZoneImportResponse {
  zones_created: number;
  zones: ExclusionZone[];
  message: string;
}

export interface BufferApplyRequest {
  buffer_distance: number;
}

export interface SpatialQueryRequest {
  geometry: GeoJSON.Geometry;
}

export interface SpatialQueryResponse {
  intersects: boolean;
  intersecting_zones: ExclusionZone[];
  total_intersecting: number;
}

// Get all exclusion zones for a project
export async function getExclusionZones(
  projectId: string,
  activeOnly = true,
  zoneType?: string
): Promise<ExclusionZoneListResponse> {
  const params = new URLSearchParams();
  params.append('active_only', String(activeOnly));
  if (zoneType) {
    params.append('zone_type', zoneType);
  }

  const response = await api.get<ExclusionZoneListResponse>(
    `/api/v1/projects/${projectId}/zones?${params.toString()}`
  );
  return response.data;
}

// Get a single exclusion zone
export async function getExclusionZone(
  projectId: string,
  zoneId: string
): Promise<ExclusionZone> {
  const response = await api.get<ExclusionZone>(
    `/api/v1/projects/${projectId}/zones/${zoneId}`
  );
  return response.data;
}

// Create a new exclusion zone (drawn on map)
export async function createExclusionZone(
  projectId: string,
  data: ExclusionZoneCreate
): Promise<ExclusionZone> {
  const response = await api.post<ExclusionZone>(
    `/api/v1/projects/${projectId}/zones`,
    data
  );
  return response.data;
}

// Import exclusion zones from an uploaded file
export async function importExclusionZones(
  projectId: string,
  data: ExclusionZoneImportRequest
): Promise<ExclusionZoneImportResponse> {
  const response = await api.post<ExclusionZoneImportResponse>(
    `/api/v1/projects/${projectId}/zones/import`,
    data
  );
  return response.data;
}

// Update an exclusion zone
export async function updateExclusionZone(
  projectId: string,
  zoneId: string,
  data: ExclusionZoneUpdate
): Promise<ExclusionZone> {
  const response = await api.patch<ExclusionZone>(
    `/api/v1/projects/${projectId}/zones/${zoneId}`,
    data
  );
  return response.data;
}

// Apply buffer to a zone
export async function applyBuffer(
  projectId: string,
  zoneId: string,
  bufferDistance: number
): Promise<ExclusionZone> {
  const response = await api.post<ExclusionZone>(
    `/api/v1/projects/${projectId}/zones/${zoneId}/buffer`,
    { buffer_distance: bufferDistance } as BufferApplyRequest
  );
  return response.data;
}

// Remove buffer from a zone
export async function removeBuffer(
  projectId: string,
  zoneId: string
): Promise<ExclusionZone> {
  const response = await api.delete<ExclusionZone>(
    `/api/v1/projects/${projectId}/zones/${zoneId}/buffer`
  );
  return response.data;
}

// Delete an exclusion zone
export async function deleteExclusionZone(
  projectId: string,
  zoneId: string
): Promise<void> {
  await api.delete(`/api/v1/projects/${projectId}/zones/${zoneId}`);
}

// Check if geometry intersects with any exclusion zones
export async function checkZoneIntersection(
  projectId: string,
  geometry: GeoJSON.Geometry
): Promise<SpatialQueryResponse> {
  const response = await api.post<SpatialQueryResponse>(
    `/api/v1/projects/${projectId}/zones/check-intersection`,
    { geometry } as SpatialQueryRequest
  );
  return response.data;
}
