import { ReflectionView } from "@/components/reflection-view";
import { getReflectionSurface } from "@/lib/reality-adapter-data";

export default async function ReflectionPage() {
  const surface = await getReflectionSurface();
  return <ReflectionView surface={surface} />;
}
