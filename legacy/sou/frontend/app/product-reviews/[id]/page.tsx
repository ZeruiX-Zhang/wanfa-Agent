import { redirect } from "next/navigation";

export default async function ProductReviewDetailRedirectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/ai-product-reviews/${id}`);
}
