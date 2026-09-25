import { describe, it, expect } from 'vitest';
import { strokeRateBand } from '../src/domain/bands';

describe('strokeRateBand', () => {
  it('returns a band', () => {
    expect(strokeRateBand(20)).toBeDefined();
  });
});
