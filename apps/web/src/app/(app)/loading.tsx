import { PageShell } from "@/components/layout/page-shell";
import { Skeleton } from "@/components/ui/skeleton";

/** Affichée tout de suite pendant un changement de page : la place du contenu, sans texte. */
export default function AppLoading() {
  return (
    <PageShell>
      <div aria-busy="true" className="flex flex-col gap-[22px]">
        <Skeleton className="h-[58px] w-64" />
        <Skeleton className="h-[72px]" />
        <Skeleton className="h-[260px]" />
      </div>
    </PageShell>
  );
}
