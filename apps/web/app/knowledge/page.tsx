import { KnowledgeView } from "@/components/knowledge-view";
import { getSouSurface } from "@/lib/reality-adapter-data";

export default async function KnowledgePage() {
  const surface = await getSouSurface();
  return <KnowledgeView surface={surface} />;
}
