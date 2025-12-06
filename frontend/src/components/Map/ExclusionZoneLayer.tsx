'use client';

import { useMemo } from 'react';
import { GeoJsonLayer } from 'deck.gl';
import type { Feature } from 'geojson';
import type { ExclusionZone, ZoneType } from '@/types/map';
import { ZONE_COLORS, zonesToFeatureCollection } from '@/types/map';

interface ExclusionZoneLayerProps {
  zones: ExclusionZone[];
  visible?: boolean;
  selectedZoneId?: string | null;
  onZoneClick?: (zone: ExclusionZone) => void;
  onZoneHover?: (zone: ExclusionZone | null) => void;
}

export function useExclusionZoneLayers({
  zones,
  visible = true,
  selectedZoneId,
  onZoneClick,
  onZoneHover,
}: ExclusionZoneLayerProps) {
  // Group zones by type for separate styling
  const layersByType = useMemo(() => {
    if (!visible || zones.length === 0) return [];

    const zonesByType = zones.reduce((acc, zone) => {
      if (!zone.is_active) return acc;
      if (!acc[zone.zone_type]) {
        acc[zone.zone_type] = [];
      }
      acc[zone.zone_type].push(zone);
      return acc;
    }, {} as Record<ZoneType, ExclusionZone[]>);

    return Object.entries(zonesByType).map(([zoneType, typeZones]) => {
      const colors = ZONE_COLORS[zoneType as ZoneType];
      const data = zonesToFeatureCollection(typeZones);

      return new GeoJsonLayer({
        id: `exclusion-zones-${zoneType}`,
        data,
        pickable: true,
        stroked: true,
        filled: true,
        extruded: false,
        getFillColor: (d: Feature) => {
          const isSelected = d.properties?.id === selectedZoneId;
          if (isSelected) {
            // Brighter fill for selected zone
            return [colors.fill[0], colors.fill[1], colors.fill[2], 180] as [number, number, number, number];
          }
          return colors.fill;
        },
        getLineColor: (d: Feature) => {
          const isSelected = d.properties?.id === selectedZoneId;
          if (isSelected) {
            return [255, 255, 255, 255] as [number, number, number, number];
          }
          return colors.stroke;
        },
        getLineWidth: (d: Feature) => {
          const isSelected = d.properties?.id === selectedZoneId;
          return isSelected ? 4 : 2;
        },
        lineWidthMinPixels: 1,
        lineWidthScale: 1,
        updateTriggers: {
          getFillColor: [selectedZoneId],
          getLineColor: [selectedZoneId],
          getLineWidth: [selectedZoneId],
        },
        onClick: (info: { object?: Feature }) => {
          if (info.object && onZoneClick) {
            const zoneId = info.object.properties?.id;
            const zone = zones.find((z) => z.id === zoneId);
            if (zone) {
              onZoneClick(zone);
            }
          }
        },
        onHover: (info: { object?: Feature }) => {
          if (onZoneHover) {
            if (info.object) {
              const zoneId = info.object.properties?.id;
              const zone = zones.find((z) => z.id === zoneId);
              onZoneHover(zone || null);
            } else {
              onZoneHover(null);
            }
          }
        },
      });
    });
  }, [zones, visible, selectedZoneId, onZoneClick, onZoneHover]);

  return layersByType;
}

// Component to display zone legend
export function ExclusionZoneLegend({ visible = true }: { visible?: boolean }) {
  if (!visible) return null;

  return (
    <div className="absolute bottom-20 left-4 z-10 bg-white rounded-lg shadow-lg p-3">
      <h4 className="text-xs font-semibold text-gray-700 mb-2">Exclusion Zones</h4>
      <div className="space-y-1">
        {(Object.entries(ZONE_COLORS) as [ZoneType, typeof ZONE_COLORS[ZoneType]][]).map(
          ([type, colors]) => (
            <div key={type} className="flex items-center space-x-2">
              <div
                className="w-4 h-3 rounded border"
                style={{
                  backgroundColor: `rgba(${colors.fill.join(',')})`,
                  borderColor: `rgba(${colors.stroke.join(',')})`,
                }}
              />
              <span className="text-xs text-gray-600 capitalize">
                {type.replace('_', ' ')}
              </span>
            </div>
          )
        )}
      </div>
    </div>
  );
}
