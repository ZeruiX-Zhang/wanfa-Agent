import { LibraryDetail } from "@/components/pages/library-detail";

export default async function LibraryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LibraryDetail id={id} />;
}
