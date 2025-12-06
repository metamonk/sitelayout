'use client';

import { useState } from 'react';
import type { ZoneType } from '@/types/map';
import { ZONE_COLORS, ZONE_LABELS } from '@/types/map';

interface ZoneTypeSelectorProps {
  selectedType: ZoneType;
  onTypeChange: (type: ZoneType) => void;
  disabled?: boolean;
}

const ZONE_TYPES: ZoneType[] = ['wetland', 'easement', 'stream_buffer', 'setback', 'custom'];

export function ZoneTypeSelector({
  selectedType,
  onTypeChange,
  disabled = false,
}: ZoneTypeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const selectedColors = ZONE_COLORS[selectedType];

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className="w-full px-4 py-2 bg-white border border-gray-300 rounded-lg shadow-sm flex items-center justify-between hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <div className="flex items-center space-x-3">
          <div
            className="w-5 h-5 rounded border-2"
            style={{
              backgroundColor: `rgba(${selectedColors.fill.slice(0, 3).join(',')}, 0.5)`,
              borderColor: `rgb(${selectedColors.stroke.slice(0, 3).join(',')})`,
            }}
          />
          <span className="text-gray-900">{ZONE_LABELS[selectedType]}</span>
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {ZONE_TYPES.map((type) => {
            const colors = ZONE_COLORS[type];
            return (
              <button
                key={type}
                type="button"
                onClick={() => {
                  onTypeChange(type);
                  setIsOpen(false);
                }}
                className={`w-full px-4 py-2 flex items-center space-x-3 hover:bg-gray-50 transition-colors ${
                  type === selectedType ? 'bg-indigo-50' : ''
                }`}
              >
                <div
                  className="w-5 h-5 rounded border-2"
                  style={{
                    backgroundColor: `rgba(${colors.fill.slice(0, 3).join(',')}, 0.5)`,
                    borderColor: `rgb(${colors.stroke.slice(0, 3).join(',')})`,
                  }}
                />
                <span className={type === selectedType ? 'text-indigo-700 font-medium' : 'text-gray-700'}>
                  {ZONE_LABELS[type]}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Zone creation panel
interface ZoneCreationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  selectedType: ZoneType;
  onTypeChange: (type: ZoneType) => void;
  zoneName: string;
  onNameChange: (name: string) => void;
  bufferDistance: number | null;
  onBufferChange: (distance: number | null) => void;
  onSave: () => void;
  isSaving?: boolean;
}

export function ZoneCreationPanel({
  isOpen,
  onClose,
  selectedType,
  onTypeChange,
  zoneName,
  onNameChange,
  bufferDistance,
  onBufferChange,
  onSave,
  isSaving = false,
}: ZoneCreationPanelProps) {
  if (!isOpen) return null;

  return (
    <div className="absolute top-20 right-4 z-20 w-80 bg-white rounded-lg shadow-xl border border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">New Exclusion Zone</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Zone Name</label>
          <input
            type="text"
            value={zoneName}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Enter zone name..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Zone Type</label>
          <ZoneTypeSelector
            selectedType={selectedType}
            onTypeChange={onTypeChange}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Buffer Distance (optional)
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="number"
              value={bufferDistance ?? ''}
              onChange={(e) => {
                const val = e.target.value;
                onBufferChange(val ? parseFloat(val) : null);
              }}
              placeholder="0"
              min="0"
              max="10000"
              step="1"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
            <span className="text-gray-500 text-sm">meters</span>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Add a buffer around the zone boundary (0-10,000m)
          </p>
        </div>
      </div>

      <div className="p-4 border-t border-gray-200 flex justify-end space-x-3">
        <button
          onClick={onClose}
          className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={onSave}
          disabled={!zoneName.trim() || isSaving}
          className="px-4 py-2 text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? 'Saving...' : 'Save Zone'}
        </button>
      </div>
    </div>
  );
}
