'use client';

import { useCallback, useState, useMemo } from 'react';
import Map, { NavigationControl, ScaleControl, FullscreenControl } from 'react-map-gl';
import { DeckGL, GeoJsonLayer } from 'deck.gl';
import type { Feature, FeatureCollection } from 'geojson';
import 'mapbox-gl/dist/mapbox-gl.css';

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

// Map view state interface
export interface MapViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

// Default view centered on US
const INITIAL_VIEW_STATE: MapViewState = {
  longitude: -98.5795,
  latitude: 39.8283,
  zoom: 4,
  pitch: 0,
  bearing: 0,
};

// Map style options
export type MapStyle = 'satellite' | 'streets' | 'outdoors' | 'light' | 'dark';

const MAP_STYLES: Record<MapStyle, string> = {
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  streets: 'mapbox://styles/mapbox/streets-v12',
  outdoors: 'mapbox://styles/mapbox/outdoors-v12',
  light: 'mapbox://styles/mapbox/light-v11',
  dark: 'mapbox://styles/mapbox/dark-v11',
};

// Layer configuration for different feature types
export interface LayerConfig {
  id: string;
  name: string;
  visible: boolean;
  data: FeatureCollection | null;
  color: [number, number, number, number];
  strokeColor?: [number, number, number, number];
  lineWidth?: number;
}

interface MapViewProps {
  layers?: LayerConfig[];
  mapStyle?: MapStyle;
  initialViewState?: Partial<MapViewState>;
  onFeatureClick?: (feature: Feature | null, layerId: string) => void;
  onFeatureHover?: (feature: Feature | null, layerId: string) => void;
  onViewStateChange?: (viewState: MapViewState) => void;
  children?: React.ReactNode;
}

export default function MapView({
  layers = [],
  mapStyle = 'satellite',
  initialViewState,
  onFeatureClick,
  onFeatureHover,
  onViewStateChange,
  children,
}: MapViewProps) {
  const [viewState, setViewState] = useState<MapViewState>({
    ...INITIAL_VIEW_STATE,
    ...initialViewState,
  });
  const [hoveredFeatureId, setHoveredFeatureId] = useState<string | number | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleViewStateChange = useCallback((params: any) => {
    const newViewState = params.viewState as MapViewState;
    setViewState(newViewState);
    onViewStateChange?.(newViewState);
  }, [onViewStateChange]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleClick = useCallback((info: any) => {
    if (info.object && onFeatureClick) {
      const layerId = info.layer?.id || '';
      onFeatureClick(info.object as Feature, layerId);
    }
  }, [onFeatureClick]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleHover = useCallback((info: any) => {
    const feature = info.object as Feature | null;
    setHoveredFeatureId(feature?.id ?? null);
    if (onFeatureHover) {
      const layerId = info.layer?.id || '';
      onFeatureHover(feature, layerId);
    }
  }, [onFeatureHover]);

  // Convert layer configs to Deck.gl layers
  const deckLayers = useMemo(() => {
    return layers
      .filter((layer) => layer.visible && layer.data)
      .map((layer) => {
        return new GeoJsonLayer({
          id: layer.id,
          data: layer.data as FeatureCollection,
          pickable: true,
          stroked: true,
          filled: true,
          extruded: false,
          getFillColor: (d: Feature) => {
            // Highlight on hover
            if (hoveredFeatureId !== null && d.id === hoveredFeatureId) {
              return [layer.color[0], layer.color[1], layer.color[2], 200] as [number, number, number, number];
            }
            return layer.color;
          },
          getLineColor: layer.strokeColor || [255, 255, 255, 200],
          getLineWidth: layer.lineWidth || 2,
          lineWidthMinPixels: 1,
          lineWidthScale: 1,
          updateTriggers: {
            getFillColor: [hoveredFeatureId],
          },
        });
      });
  }, [layers, hoveredFeatureId]);

  if (!MAPBOX_TOKEN) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100">
        <div className="text-center p-8">
          <p className="text-red-600 font-semibold">Mapbox token not configured</p>
          <p className="text-gray-600 text-sm mt-2">
            Please set NEXT_PUBLIC_MAPBOX_TOKEN in your environment variables
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={true}
        layers={deckLayers}
        onClick={handleClick}
        onHover={handleHover}
        getCursor={({ isHovering, isDragging }: { isHovering: boolean; isDragging: boolean }) =>
          isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab'
        }
      >
        <Map
          mapboxAccessToken={MAPBOX_TOKEN}
          mapStyle={MAP_STYLES[mapStyle]}
          reuseMaps
          attributionControl={false}
        >
          <NavigationControl position="top-right" />
          <ScaleControl position="bottom-left" />
          <FullscreenControl position="top-right" />
        </Map>
      </DeckGL>
      {children}
    </div>
  );
}
