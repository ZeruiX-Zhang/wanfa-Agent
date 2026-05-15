import { DashboardView } from "@/components/dashboard-view";
import { getDashboardSurface } from "@/lib/reality-adapter-data";

export default async function DashboardPage() {
  const surface = await getDashboardSurface();
  return <DashboardView surface={surface} />;
}
