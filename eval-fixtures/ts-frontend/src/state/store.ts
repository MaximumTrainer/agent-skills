import { create } from 'zustand';

interface TelemetryState {
  strokeRate: number;
  power: number;
  distance: number;
  selectedBoatId: string | null;
  showCoxView: boolean;
  setTelemetry: (t: { strokeRate: number; power: number; distance: number }) => void;
  setSelected: (id: string | null) => void;
}

export const useStore = create<TelemetryState>((set) => ({
  strokeRate: 0,
  power: 0,
  distance: 0,
  selectedBoatId: null,
  showCoxView: false,
  setTelemetry: (t) => set(t),
  setSelected: (id) => set({ selectedBoatId: id }),
}));
