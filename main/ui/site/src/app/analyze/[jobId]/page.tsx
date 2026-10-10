import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AnalysisWorkspace } from "@/components/analyze/analysis-workspace";
export const metadata: Metadata = { title: "Demo analysis", robots: { index: false, follow: false } };
export default async function AnalysisPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  if (!/^TEST_\d{14}_[a-f0-9]{32}$/.test(jobId)) notFound();
  return <AnalysisWorkspace key={jobId} jobId={jobId} />;
}
