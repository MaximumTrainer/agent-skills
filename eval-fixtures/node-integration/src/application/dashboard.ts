import type { ProviderClient, WellnessRow } from '../adapter/ProviderClient';

export interface DashboardState {
  latestHrv: number | null;
  freshness: string;
}

export async function buildDashboardState(client: ProviderClient, athleteId: string): Promise<DashboardState> {
  const rows: WellnessRow[] = await client.wellness(athleteId);
  const latest = rows[0];
  const ageDays = (Date.now() - new Date(latest.date).getTime()) / 86400000;
  return {
    latestHrv: latest.hrv,
    freshness: ageDays < 2 ? 'current' : 'stale',
  };
}
