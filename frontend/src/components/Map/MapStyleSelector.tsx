'use client';

import { useState } from 'react';
import type { MapStyle } from './MapView';

interface MapStyleSelectorProps {
  currentStyle: MapStyle;
  onStyleChange: (style: MapStyle) => void;
}

const STYLE_OPTIONS: { value: MapStyle; label: string; icon: string }[] = [
  { value: 'satellite', label: 'Satellite', icon: '🛰️' },
  { value: 'streets', label: 'Streets', icon: '🗺️' },
  { value: 'outdoors', label: 'Outdoors', icon: '🏔️' },
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'dark', label: 'Dark', icon: '🌙' },
];

export default function MapStyleSelector({
  currentStyle,
  onStyleChange,
}: MapStyleSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const currentOption = STYLE_OPTIONS.find((opt) => opt.value === currentStyle);

  return (
    <div className="absolute bottom-8 right-4 z-10">
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="bg-white rounded-lg shadow-lg px-3 py-2 flex items-center space-x-2 hover:bg-gray-50 transition-colors"
        >
          <span className="text-lg">{currentOption?.icon}</span>
          <span className="text-sm font-medium text-gray-700">{currentOption?.label}</span>
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
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

        {isOpen && (
          <div className="absolute bottom-full right-0 mb-2 bg-white rounded-lg shadow-lg overflow-hidden min-w-[140px]">
            {STYLE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  onStyleChange(option.value);
                  setIsOpen(false);
                }}
                className={`w-full px-3 py-2 flex items-center space-x-2 hover:bg-gray-50 transition-colors ${
                  option.value === currentStyle ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700'
                }`}
              >
                <span className="text-lg">{option.icon}</span>
                <span className="text-sm font-medium">{option.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
