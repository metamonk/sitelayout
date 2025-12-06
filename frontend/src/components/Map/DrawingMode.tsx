'use client';

import { useState, useCallback, useEffect } from 'react';
import type { Feature, Polygon, Position } from 'geojson';

export type DrawingModeType = 'none' | 'polygon' | 'rectangle';

interface DrawingModeProps {
  mode: DrawingModeType;
  onComplete: (geometry: Polygon) => void;
  onCancel: () => void;
}

interface DrawingState {
  points: Position[];
  isDrawing: boolean;
}

export function useDrawingMode({ mode, onComplete, onCancel }: DrawingModeProps) {
  const [drawingState, setDrawingState] = useState<DrawingState>({
    points: [],
    isDrawing: false,
  });
  const [cursorPosition, setCursorPosition] = useState<Position | null>(null);

  // Reset drawing state when mode changes
  useEffect(() => {
    setDrawingState({ points: [], isDrawing: false });
    setCursorPosition(null);
  }, [mode]);

  const handleMapClick = useCallback(
    (coordinate: Position) => {
      if (mode === 'none') return;

      setDrawingState((prev) => {
        const newPoints = [...prev.points, coordinate];

        if (mode === 'rectangle' && newPoints.length === 2) {
          // Complete rectangle with 2 points
          const [p1, p2] = newPoints;
          const polygon: Polygon = {
            type: 'Polygon',
            coordinates: [
              [
                p1,
                [p2[0], p1[1]],
                p2,
                [p1[0], p2[1]],
                p1, // Close the polygon
              ],
            ],
          };
          onComplete(polygon);
          return { points: [], isDrawing: false };
        }

        return { points: newPoints, isDrawing: true };
      });
    },
    [mode, onComplete]
  );

  const handleDoubleClick = useCallback(() => {
    if (mode !== 'polygon' || drawingState.points.length < 3) return;

    // Close the polygon
    const points = drawingState.points;
    const polygon: Polygon = {
      type: 'Polygon',
      coordinates: [[...points, points[0]]],
    };
    onComplete(polygon);
    setDrawingState({ points: [], isDrawing: false });
  }, [mode, drawingState.points, onComplete]);

  const handleMouseMove = useCallback(
    (coordinate: Position) => {
      if (mode !== 'none') {
        setCursorPosition(coordinate);
      }
    },
    [mode]
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setDrawingState({ points: [], isDrawing: false });
        onCancel();
      } else if (event.key === 'Enter' && mode === 'polygon' && drawingState.points.length >= 3) {
        handleDoubleClick();
      } else if (event.key === 'Backspace' && drawingState.points.length > 0) {
        // Remove last point
        setDrawingState((prev) => ({
          ...prev,
          points: prev.points.slice(0, -1),
        }));
      }
    },
    [mode, drawingState.points.length, onCancel, handleDoubleClick]
  );

  // Set up keyboard listeners
  useEffect(() => {
    if (mode !== 'none') {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [mode, handleKeyDown]);

  // Get preview geometry for rendering
  const previewGeometry = useCallback((): Feature<Polygon> | null => {
    if (mode === 'none' || drawingState.points.length === 0) return null;

    const points = [...drawingState.points];
    if (cursorPosition) {
      points.push(cursorPosition);
    }

    if (mode === 'rectangle' && points.length === 2) {
      const [p1, p2] = points;
      return {
        type: 'Feature',
        properties: { preview: true },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              p1,
              [p2[0], p1[1]],
              p2,
              [p1[0], p2[1]],
              p1,
            ],
          ],
        },
      };
    }

    if (mode === 'polygon' && points.length >= 2) {
      // Show preview polygon
      return {
        type: 'Feature',
        properties: { preview: true },
        geometry: {
          type: 'Polygon',
          coordinates: [[...points, points[0]]],
        },
      };
    }

    return null;
  }, [mode, drawingState.points, cursorPosition]);

  return {
    drawingState,
    cursorPosition,
    handleMapClick,
    handleDoubleClick,
    handleMouseMove,
    previewGeometry,
    isDrawing: mode !== 'none',
  };
}

// Drawing toolbar component
interface DrawingToolbarProps {
  activeMode: DrawingModeType;
  onModeChange: (mode: DrawingModeType) => void;
  onCancel: () => void;
  disabled?: boolean;
}

export function DrawingToolbar({
  activeMode,
  onModeChange,
  onCancel,
  disabled = false,
}: DrawingToolbarProps) {
  return (
    <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
      <div className="bg-white rounded-lg shadow-lg p-2 flex items-center space-x-2">
        <button
          onClick={() => onModeChange('polygon')}
          disabled={disabled}
          className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
            activeMode === 'polygon'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          title="Draw polygon (click to add points, double-click to finish)"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
        </button>

        <button
          onClick={() => onModeChange('rectangle')}
          disabled={disabled}
          className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
            activeMode === 'rectangle'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          title="Draw rectangle (click two corners)"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 6v12m16-12v12M4 18h16"
            />
          </svg>
        </button>

        {activeMode !== 'none' && (
          <button
            onClick={onCancel}
            className="px-3 py-2 rounded text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
            title="Cancel drawing (Escape)"
          >
            Cancel
          </button>
        )}
      </div>

      {activeMode !== 'none' && (
        <div className="mt-2 bg-black/70 text-white text-xs px-3 py-1.5 rounded text-center">
          {activeMode === 'polygon' ? (
            <>Click to add points. Double-click or press Enter to finish.</>
          ) : (
            <>Click two corners to create a rectangle.</>
          )}
          <br />
          <span className="text-gray-300">Press Escape to cancel, Backspace to undo</span>
        </div>
      )}
    </div>
  );
}
