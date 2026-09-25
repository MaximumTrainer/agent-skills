const BASE = '/provider';

export interface WellnessRow {
  date: string;
  hrv: number | null;
  restingHr: number | null;
}

export class ProviderClient {
  constructor(private readonly key: string) {}

  async wellness(athleteId: string): Promise<WellnessRow[]> {
    const res = await fetch(`${BASE}/athlete/${athleteId}/wellness`, {
      headers: { Authorization: `Bearer ${this.key}` },
    });
    return res.json();
  }

  async activities(athleteId: string): Promise<unknown[]> {
    const res = await fetch(`${BASE}/athlete/${athleteId}/activities`, {
      headers: { Authorization: `Bearer ${this.key}` },
    });
    return res.json();
  }
}
