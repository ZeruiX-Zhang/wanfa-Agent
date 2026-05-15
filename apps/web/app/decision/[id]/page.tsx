import { DecisionView } from "@/components/decision-view";
import { getDecisionCase } from "@/lib/reality-adapter-data";

export default async function DecisionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const decision = await getDecisionCase(id);
  return <DecisionView id={id} decision={decision} />;
}
