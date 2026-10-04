"use client";

import { useState } from "react";

import { UploadCsvDialog } from "@/components/admin/upload-csv-dialog";
import { PageTitle } from "@/components/layout/page-title";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { UploadIcon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/tag";
import { type DatasetSummary, useDatasetSummary } from "@/hooks/use-dataset-summary";
import { apiMessage } from "@/lib/api/messages";
import { formatDateTime, formatNumber } from "@/lib/format";
import { labels } from "@/lib/labels";

function Tiles({ summary }: { summary: DatasetSummary | undefined }) {
  const t = labels.data.tiles;
  const enough = (summary?.agency_rows ?? 0) >= labels.data.agencyMinimum;
  const tiles = [
    { key: t.seed.key, value: summary?.seed_rows, sub: t.seed.sub },
    {
      key: t.agency.key,
      value: summary?.agency_rows,
      sub: enough ? t.agency.enough : t.agency.needed(labels.data.agencyMinimum),
    },
    { key: t.holdout.key, value: summary?.holdout_rows, sub: t.holdout.sub },
  ];
  return (
    <div
      data-testid="data-tiles"
      className="stat-grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))]"
    >
      {tiles.map((tile) => (
        <div key={tile.key} className="p-4">
          <div className="kicker">{tile.key}</div>
          {tile.value === undefined ? (
            <Skeleton className="my-1.5 h-9 w-24" />
          ) : (
            <div className="num font-heading text-[40px] font-normal leading-[1.1]">
              {formatNumber(tile.value)}
            </div>
          )}
          <div className="text-xs text-neutral-700">{summary ? tile.sub : ""}</div>
        </div>
      ))}
    </div>
  );
}

/** Page « Data » : trois totaux, historique des imports (jeu de départ) et fenêtre « Upload CSV ». */
export function DataSummary() {
  const summary = useDatasetSummary();
  const [uploadOpen, setUploadOpen] = useState(false);
  const i = labels.data.imports;
  const data = summary.data;

  return (
    <>
      <PageTitle
        subtitle={labels.data.subtitle}
        actions={
          <Button blueprint onClick={() => setUploadOpen(true)}>
            <UploadIcon />
            {labels.data.upload}
          </Button>
        }
      >
        {labels.data.title}
      </PageTitle>
      {summary.isError ? (
        <Alert variant="destructive" role="alert">
          {apiMessage(summary.error)}
        </Alert>
      ) : (
        <Tiles summary={data} />
      )}
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>{i.date}</th>
              <th>{i.file}</th>
              <th>{i.origin}</th>
              <th className="!text-right">{i.rows}</th>
              <th>{i.by}</th>
              <th>{i.status}</th>
            </tr>
          </thead>
          <tbody>
            <tr data-testid="import-row">
              <td className="num whitespace-nowrap">
                {data?.seed_loaded_at
                  ? formatDateTime(data.seed_loaded_at)
                  : labels.admin.audit.none}
              </td>
              <td>{i.seedFile}</td>
              <td>{i.seedOrigin}</td>
              <td className="num text-right">
                {data ? formatNumber(data.seed_rows) : <Skeleton className="ml-auto h-4 w-12" />}
              </td>
              <td>{i.system}</td>
              <td>
                <Tag tone="accent">{i.ready}</Tag>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <UploadCsvDialog open={uploadOpen} onClose={() => setUploadOpen(false)} />
    </>
  );
}
