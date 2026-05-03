import { buildSampleReviewBundle, loadReviewBundleFromFile, type ReviewBundle } from "./reviewBundle";

export async function openBundledSampleReview(): Promise<ReviewBundle> {
  return buildSampleReviewBundle();
}

export async function openImportedReviewBundle(file: File): Promise<ReviewBundle> {
  return loadReviewBundleFromFile(file);
}
