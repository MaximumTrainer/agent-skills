import { describe, it, expect, vi } from 'vitest';
import { buildDashboardState } from '../src/application/dashboard';
import rows from './fixtures/wellness-oldest-first.json';

describe('buildDashboardState', () => {
  it('builds state', async () => {
    const client = { wellness: vi.fn().mockResolvedValue(rows) } as any;
    const state = await buildDashboardState(client, 'a1');
    expect(state).toBeTruthy();
  });
});
