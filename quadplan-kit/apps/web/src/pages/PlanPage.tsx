import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useCatalogYears } from "@/api/hooks";
import { LoadingState, PageContainer, PageHeader } from "@/components/layout/page";
import { activePlan, newLocalId, today, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { emptyPlan } from "@/features/planner/planModel";
import { Planner } from "@/features/planner/Planner";
import { catalogYearFor } from "@/features/planner/terms";

/** The newest catalog year the API lists, or the current academic year if it lists none. */
export function defaultCatalogYear(ids: string[] | undefined): string {
  const sorted = [...(ids ?? [])].sort().reverse();
  return sorted[0] ?? catalogYearFor(new Date());
}

export default function PlanPage() {
  const [params] = useSearchParams();
  const years = useCatalogYears();
  const [local, setLocal] = useState<LocalPlan | null>(() => activePlan());

  useEffect(() => {
    if (local || years.isLoading) return;
    const plan: LocalPlan = {
      localId: newLocalId(),
      name: "My plan",
      isPrimary: true,
      state: emptyPlan(defaultCatalogYear(years.data?.map((y) => y.id))),
      updatedDay: today(),
    };
    upsertPlan(plan);
    setLocal(plan);
  }, [local, years.isLoading, years.data]);

  if (!local) {
    return (
      <PageContainer width="tool" as="section">
        <PageHeader title="Planner" size="md" />
        <LoadingState label="Preparing your plan" />
      </PageContainer>
    );
  }
  return <Planner key={local.localId} initial={local} autoGenerate={params.get("generate") === "1"} />;
}
