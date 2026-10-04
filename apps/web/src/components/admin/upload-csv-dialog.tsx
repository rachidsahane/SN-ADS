"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { UploadIcon } from "@/components/ui/icons";
import { type CsvCheck, MAX_CSV_BYTES, checkCsv } from "@/lib/csv-check";
import { labels } from "@/lib/labels";

type Props = { open: boolean; onClose: () => void };

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
 * Fenêtre « Upload agency data » (prototype). Le fichier est contrôlé dans le navigateur (colonnes, bornes, valeurs,
 * numéros uniques, aucune formule) et les problèmes sont listés ; l'import lui-même est coupé dans cette démonstration
 * (D-910) : un fichier valide est annoncé comme tel, rien n'est ajouté.
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
  const [file, setFile] = useState<File | null>(null);
  const [anonymized, setAnonymized] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<CsvCheck | null>(null);

  async function submit() {
    setResult(null);
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
    setBusy(true);
    setMessage(null);
    try {
      const checked = checkCsv(await readText(file));
      setResult(checked);
      setMessage(checked.total > 0 ? d.errors(checked.total) : d.checked(checked.rows));
    } finally {
      setBusy(false);
    }
  }

  const valid = result !== null && result.total === 0;
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
            setResult(null);
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
        <div role={valid ? "status" : "alert"} className="notice !px-3 !py-2.5 !text-[13px]">
          {message}
        </div>
      ) : null}
      {result && result.problems.length > 0 ? (
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
                {result.problems.map((problem, index) => (
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
          {valid ? d.close : d.cancel}
        </Button>
        {valid ? null : (
          <Button disabled={busy} onClick={() => void submit()}>
            {busy ? d.checking : d.submit}
          </Button>
        )}
      </div>
    </>
  );
}
