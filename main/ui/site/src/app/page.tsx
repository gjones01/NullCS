import { CapabilitiesGrid } from "@/components/home/capabilities-grid";
import { Hero } from "@/components/home/hero";
import { ProofGrid } from "@/components/home/proof-grid";
import { ProjectIntro } from "@/components/home/project-intro";
import { ResearchCta } from "@/components/home/research-cta";
import { WhyExists } from "@/components/home/why-exists";
import { WorkflowStrip } from "@/components/home/workflow-strip";

export default function HomePage() {
  return (
    <>
      <Hero />
      <ProjectIntro />
      <WhyExists />
      <CapabilitiesGrid />
      <ProofGrid />
      <WorkflowStrip />
      <ResearchCta />
    </>
  );
}
