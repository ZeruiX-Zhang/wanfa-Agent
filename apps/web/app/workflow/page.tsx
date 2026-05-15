import { WorkflowView } from "@/components/workflow-view";
import { getSupervisorSurface } from "@/lib/reality-adapter-data";

export default async function WorkflowPage() {
  const surface = await getSupervisorSurface();
  return <WorkflowView surface={surface} />;
}
