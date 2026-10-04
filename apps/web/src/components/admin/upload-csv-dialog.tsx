"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { UploadIcon } from "@/components/ui/icons";
import { useUploadDataset } from "@/hooks/use-dataset-upload";
import { ApiError } from "@/lib/api/client";
import { apiMessage, isUnexpectedError } from "@/lib/api/messages";
import { type CsvProblem, MAX_CSV_BYTES, checkCsv } from "@/lib/csv-check";
import { labels } from "@/lib/labels";
import { reportError } from "@/lib/observability";
import { useToast } from "@/providers/toast-provider";

type Props = { open: boolean; onClose: () => void };

/** Problèmes à lister : ceux du navigateur ou ceux renvoyés par l'API (row, column, message). */
type Problems = { list: CsvProblem[] };

/** Texte du fichier choisi (FileReader : disponible partout, y compris dans les tests). */
function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

/**
 * Fenêtre « Upload agency data » (prototype). Le fichier est d'abord contrôlé dans le navigateur (colonnes, bornes,
 * valeurs, numéros uniques, aucune formule), puis envoyé à l'API, qui refait tous les contrôles et ajoute les lignes
 * (source « agency »). Les problèmes, ceux du navigateur comme ceux de l'API, sont listés dans le même tableau.
 */
export function UploadCsvDialog({ open, onClose }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={labels.data.dialog.title}
      className="!w-[min(560px,100%)]"
    >
      <UploadForm onClose={onClose} />
    </Dialog>
  );
}

function UploadForm({ onClose }: { onClose: () => void }) {
  const d = labels.data.dialog;
  const upload = useUploadDataset();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [anonymized, setAnonymized] = useState(false);
  const [stage, setStage] = useState<"idle" | "checking" | "importing">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [problems, setProblems] = useState<Problems | null>(null);

  async function send(chosen: File) {
    setStage("importing");
    try {
      const result = await upload.mutateAsync(chosen);
      toast(d.imported(result.rows_imported));
      onClose();
    } catch (error) {
      if (error instanceof ApiError && error.code === "CSV_INVALID") {
        setProblems({
          list: error.details.map((detail) => ({
            row: detail.row ?? 0,
            column: detail.column ?? "—",
            message: detail.message ?? "",
          })),
        });
      }
      setMessage(apiMessage(error));
      if (isUnexpectedError(error)) {
        reportError(error, {
          route: "upload-csv-dialog",
          requestId: error instanceof ApiError ? error.requestId : null,
        });
      }
    }
  }

  async function submit() {
    setProblems(null);
    if (!file) {
      setMessage(d.noFile);
      return;
    }
    if (!/\.csv$/i.test(file.name)) {
      setMessage(d.notCsv);
      return;
    }
    if (file.size > MAX_CSV_BYTES) {
      setMessage(d.tooBig);
      return;
    }
    if (!anonymized) {
      setMessage(d.confirmAnonymized);
      return;
    }
    setStage("checking");
    setMessage(null);
    try {
      const checked = checkCsv(await readText(file));
      if (checked.total > 0) {
        setProblems({ list: checked.problems });
        setMessage(d.errors(checked.total));
        return;
      }
      await send(file);
    } finally {
      setStage("idle");
    }
  }

  const busy = stage !== "idle";
  return (
    <>
      <div className="border border-divider px-3 py-2.5 text-[13px]">{d.note}</div>
      <label className="flex cursor-pointer flex-col items-center gap-1.5 border border-dashed border-brand p-5 text-sm text-brand-800 hover:bg-brand-100">
        <input
          type="file"
          accept=".csv,text/csv"
          className="absolute h-px w-px opacity-0"
          data-testid="csv-file"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setMessage(null);
            setProblems(null);
          }}
        />
        <UploadIcon size={22} />
        <span>{file ? file.name : d.choose}</span>
        <span className="text-[11px] text-neutral-700">{d.hint}</span>
      </label>
      <label className="flex cursor-pointer items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-[3px]"
          checked={anonymized}
          onChange={(event) => setAnonymized(event.target.checked)}
        />
        {d.anonymized}
      </label>
      {message ? (
        <div role="alert" className="notice !px-3 !py-2.5 !text-[13px]">
          {message}
        </div>
      ) : null}
      {problems && problems.list.length > 0 ? (
        <>
          <div className="max-h-[200px] overflow-auto border border-divider">
            <table className="table !text-xs">
              <thead>
                <tr>
                  <th>{d.columns.row}</th>
                  <th>{d.columns.column}</th>
                  <th>{d.columns.problem}</th>
                </tr>
              </thead>
              <tbody>
                {problems.list.map((problem, index) => (
                  <tr key={`${problem.row}-${problem.column}-${index}`}>
                    <td className="num">{problem.row}</td>
                    <td>
                      <code>{problem.column}</code>
                    </td>
                    <td>{problem.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-xs text-neutral-700">{d.nothingImported}</div>
        </>
      ) : null}
      <div className="dialog-actions">
        <Button variant="outline" onClick={onClose}>
          {d.cancel}
        </Button>
        <Button disabled={busy} onClick={() => void submit()}>
          {stage === "checking" ? d.checking : stage === "importing" ? d.importing : d.submit}
        </Button>
      </div>
    </>
  );
}
