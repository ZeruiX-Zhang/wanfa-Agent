import { InputView } from "@/components/input-view";
import { getCaptureSummary } from "@/lib/reality-adapter-data";

export default async function InputPage() {
  const summary = await getCaptureSummary();
  return <InputView summary={summary} />;
}
