import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useCatalogYears } from "@/api/hooks";
import { LoadingState, PageContainer, PageHeader } from "@/components/layout/page";
import { activePlan, newLocalId, today, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { emptyPlan } from "@/features/planner/planModel";
import { Planner } from "@/features/planner/Planner";
import { defaultCatalogYear } from "@/features/planner/terms";

export default function PlanPage() {
  const [params, setParams] = useSearchParams();
  // ?generate=1 (the onboarding wizard's last step) starts one generation: read it once, then
  // drop it from the address, so a reload does not start another paid run.
  const [generateFromUrl] = useState(() => params.get("generate") === "1");
  useEffect(() => {
    if (!params.has("generate")) return;
    setParams(
      (p) => {
        const next = new URLSearchParams(p);
        next.delete("generate");
        return next;
      },
      { replace: true },
    );
  }, [params, setParams]);
  const years = useCatalogYears();
  const [local, setLocal] = useState<LocalPlan | null>(() => activePlan());
  // A plan set up from the student record reopens the planner (a new key), with the generator
  // when the student kept "Generate a starting plan" (the onboarding wizard's last step).
  const [setUp, setSetUp] = useState<{ version: number; generate: boolean }>({ version: 0, generate: false });

  useEffect(() => {
    if (local || years.isLoading) return;
    const plan: LocalPlan = {
      localId: newLocalId(),
      name: "My Plan",
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
  return (
    <Planner
      key={`${local.localId}:${setUp.version}`}
      initial={local}
      autoGenerate={setUp.version > 0 ? setUp.generate : generateFromUrl}
      onSetUp={(plan, generate) => {
        const next = { ...plan, updatedDay: today() };
        upsertPlan(next);
        setLocal(next);
        setSetUp((s) => ({ version: s.version + 1, generate }));
      }}
    />
  );
}
