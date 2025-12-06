'use client';

import { useState } from 'react';
import type { LayerConfig } from './MapView';

interface LayerControlProps {
  layers: LayerConfig[];
  onLayerToggle: (layerId: string, visible: boolean) => void;
  onOpacityChange?: (layerId: string, opacity: number) => void;
}

export default function LayerControl({
  layers,
  onLayerToggle,
  onOpacityChange,
}: LayerControlProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="absolute top-4 left-4 z-10">
      <div className="bg-white rounded-lg shadow-lg overflow-hidden min-w-[200px]">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <span className="font-semibold text-gray-900 text-sm">Layers</span>
          <svg
            className={`w-4 h-4 text-gray-600 transition-transform ${
              isExpanded ? 'rotate-180' : ''
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>

        {isExpanded && (
          <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
            {layers.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-2">No layers available</p>
            ) : (
              layers.map((layer) => (
                <div
                  key={layer.id}
                  className="flex items-center space-x-3 p-2 rounded hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    id={`layer-${layer.id}`}
                    checked={layer.visible}
                    onChange={(e) => onLayerToggle(layer.id, e.target.checked)}
                    className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                  />
                  <div className="flex items-center space-x-2 flex-1 min-w-0">
                    <div
                      className="w-4 h-4 rounded border border-gray-300 flex-shrink-0"
                      style={{
                        backgroundColor: `rgba(${layer.color[0]}, ${layer.color[1]}, ${layer.color[2]}, ${layer.color[3] / 255})`,
                      }}
                    />
                    <label
                      htmlFor={`layer-${layer.id}`}
                      className="text-sm text-gray-700 cursor-pointer truncate"
                    >
                      {layer.name}
                    </label>
                  </div>
                  {layer.data && (
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {layer.data.features.length}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
