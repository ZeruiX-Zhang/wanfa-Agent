import { SearchView } from "@/components/search-view";
import { getSearchSurface } from "@/lib/reality-adapter-data";

export default async function SearchPage() {
  const surface = await getSearchSurface("");
  return <SearchView surface={surface} />;
}
