export type ReportPlayer = { rank: number; steamid: string; name: string; review_score: number; model_score: number; calibrated_probability: number | null; confidence: number | null };
export type SignalBand = 'low' | 'elevated' | 'strong' | 'unavailable';
export const bandLabels: Record<SignalBand, string> = { low: 'Low signal', elevated: 'Elevated signal', strong: 'Strong signal', unavailable: 'No reference band' };
export function signalBand(score: number | null, matchingModel: boolean): SignalBand {
  if (!matchingModel || score === null || !Number.isFinite(score) || score < 0 || score > 1) return 'unavailable';
  return score >= 0.5 ? 'strong' : score >= 0.2 ? 'elevated' : 'low';
}
export function scoreBin(value: number): number | null {
  return Number.isFinite(value) && value >= 0 && value <= 1 ? Math.min(19, Math.floor(value * 20)) : null;
}
