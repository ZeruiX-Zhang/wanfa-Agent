import { VerificationView } from "@/components/verification-view";
import { getVerificationSurface } from "@/lib/reality-adapter-data";

export default async function VerificationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const surface = await getVerificationSurface(id);
  return <VerificationView id={id} surface={surface} />;
}
