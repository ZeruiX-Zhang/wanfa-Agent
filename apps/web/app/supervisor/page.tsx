import { SupervisorDigest } from "@/components/supervisor-digest";
import { SupervisorHeader } from "@/components/supervisor-header";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { getSupervisorSurface } from "@/lib/reality-adapter-data";

export default async function SupervisorPage() {
  const surface = await getSupervisorSurface();
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="supervisor" />
      <SupervisorHeader surface={surface} />
      <SupervisorDigest initialSnapshot={surface} />
    </div>
  );
}
