import { DashboardView } from "@/components/dashboard-view";
import { LearningDashboard } from "@/components/learning-dashboard";
import { getDashboardSurface } from "@/lib/reality-adapter-data";

export default async function DashboardPage() {
  const surface = await getDashboardSurface();
  return (
    <div className="space-y-5">
      <DashboardView surface={surface} />
      <LearningDashboard />
    </div>
  );
}
