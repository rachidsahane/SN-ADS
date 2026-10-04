"use client";

import { useId } from "react";

import { Button } from "@/components/ui/button";
import { FieldError, FieldWarning } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { fieldLabel } from "@/lib/field-labels";
import { FORM_GROUPS, type FormState, SELECT_OPTIONS } from "@/lib/predict-form";
import { labels } from "@/lib/labels";
import { OPTIONAL_FIELDS } from "@/lib/schemas/prediction";

type Props = {
  form: FormState;
  errors: Record<string, string>;
  outOfRange: Set<string>;
  disabled: boolean;
  /** Champs facultatifs que le modèle actif utilise (affichés dans « Target audience profile »). */
  optionalUsed: readonly string[];
  onChange: (name: string, value: string) => void;
  onReset: () => void;
};

const BLOCK_TITLES = [
  labels.predict.blocks.plan,
  labels.predict.blocks.audience,
  labels.predict.blocks.engagement,
];

/** Les trois blocs du formulaire de campagne (prototype : numéro, titre, indication, champs en grille). */
export function PredictForm({
  form,
  errors,
  outOfRange,
  disabled,
  optionalUsed,
  onChange,
  onReset,
}: Props) {
  const ids = useId();

  function field(name: string) {
    const id = `${ids}-${name}`;
    const error = errors[name];
    const warning = !error && outOfRange.has(name);
    const describedBy = error || warning ? `${id}-note` : undefined;
    const options = SELECT_OPTIONS[name];
    return (
      <div key={name} className="field min-w-0">
        <Label htmlFor={id}>{fieldLabel(name)}</Label>
        {options ? (
          <Select
            id={id}
            value={form[name] ?? ""}
            onChange={(event) => onChange(name, event.target.value)}
          >
            {options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        ) : (
          <Input
            id={id}
            inputMode="decimal"
            autoComplete="off"
            value={form[name] ?? ""}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            onChange={(event) => onChange(name, event.target.value)}
          />
        )}
        {error ? <FieldError id={`${id}-note`}>{error}</FieldError> : null}
        {warning ? (
          <FieldWarning id={`${id}-note`}>{labels.predict.outOfRange}</FieldWarning>
        ) : null}
      </div>
    );
  }

  return (
    <section
      aria-label={labels.predict.formLabel}
      className="flex max-w-[480px] flex-[1_1_340px] flex-col gap-[22px]"
    >
      {FORM_GROUPS.map((group, index) => {
        const names: string[] = [...group.fields];
        if (group.key === "audience") {
          names.push(...OPTIONAL_FIELDS.filter((name) => optionalUsed.includes(name)));
        }
        const meta = labels.predict.groups[index];
        return (
          <fieldset
            key={group.key}
            disabled={disabled}
            className="blueprint m-0 flex min-w-0 flex-col gap-[14px] p-4"
          >
            <div className="flex items-baseline justify-between gap-2">
              <div>
                <div className="kicker">{meta?.num}</div>
                <h4 className="m-0">{BLOCK_TITLES[index]}</h4>
              </div>
              <div className="text-right text-xs text-neutral-700">{meta?.hint}</div>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-3">
              {names.map(field)}
            </div>
            {group.key === "engagement" ? (
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-divider pt-2.5 text-xs text-neutral-700">
                <span>
                  {labels.predict.engagementBasis(
                    form.campaign_channel ?? "",
                    form.campaign_type ?? "",
                  )}
                </span>
                <Button
                  variant="ghost"
                  className="!text-[13px]"
                  onClick={onReset}
                  disabled={disabled}
                >
                  {labels.predict.resetToAverages}
                </Button>
              </div>
            ) : null}
          </fieldset>
        );
      })}
    </section>
  );
}
