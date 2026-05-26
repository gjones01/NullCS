import { Hero } from "@/components/home/hero";
import { ProofGrid } from "@/components/home/proof-grid";
import { ResearchCta } from "@/components/home/research-cta";
import { ReviewPipeline } from "@/components/home/review-pipeline";

export default function HomePage() {
  return (
    <>
      <Hero />
      <ReviewPipeline />
      <ProofGrid />
      <ResearchCta />
    </>
  );
}
