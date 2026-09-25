export function strokeRateBand(spm: number): string {
  if (spm < 18) return 'Low';
  if (spm < 24) return 'Steady';
  return 'High';
}
