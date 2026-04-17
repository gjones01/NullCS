import { redirect } from "next/navigation";

type PageProps = {
  params: Promise<{ demoId: string }>;
};

export default async function BetaReviewPage({ params: _params }: PageProps) {
  void _params;
  redirect("/beta");
}
