'use client';

import dynamic from 'next/dynamic';
import { Skeleton } from '@/components/ui/skeleton';
import type { MapViewState, MapStyle, LayerConfig } from './MapView';
import type { Feature } from 'geojson';

// Lazy load the heavy MapView component
const MapView = dynamic(() => import('./MapView'), {
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-muted/50">
      <div className="space-y-4 w-full max-w-md px-8">
        <Skeleton className="h-8 w-3/4 mx-auto" />
        <Skeleton className="h-4 w-1/2 mx-auto" />
        <div className="flex justify-center gap-2 mt-4">
          <Skeleton className="h-10 w-10 rounded-full" />
          <Skeleton className="h-10 w-10 rounded-full" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>
        <p className="text-center text-sm text-muted-foreground mt-4">Loading map...</p>
      </div>
    </div>
  ),
  ssr: false, // Disable SSR for mapbox components
});

interface LazyMapViewProps {
  layers?: LayerConfig[];
  mapStyle?: MapStyle;
  initialViewState?: Partial<MapViewState>;
  onFeatureClick?: (feature: Feature | null, layerId: string) => void;
  onFeatureHover?: (feature: Feature | null, layerId: string) => void;
  onViewStateChange?: (viewState: MapViewState) => void;
  children?: React.ReactNode;
}

export default function LazyMapView(props: LazyMapViewProps) {
  return <MapView {...props} />;
}

// Re-export types for convenience
export type { MapViewState, MapStyle, LayerConfig };
