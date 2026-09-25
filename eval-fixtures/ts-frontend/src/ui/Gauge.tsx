import { useStore } from '../state/store';
import { strokeRateBand } from '../domain/bands';

export function Gauge() {
  const state = useStore();
  const band = strokeRateBand(state.strokeRate);
  return (
    <div title="Low: under 18 spm. Steady: 18-26 spm. High: above 26 spm.">
      <span>{state.strokeRate.toFixed(1)} spm</span>
      <span>{band}</span>
    </div>
  );
}
