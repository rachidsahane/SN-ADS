import Link from "next/link";

import { labels } from "@/lib/labels";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="flex w-full max-w-[400px] flex-col gap-5">
        <div className="font-heading text-[28px] font-semibold tracking-[0.06em]">
          {labels.app.wordmark}
        </div>
        <section className="blueprint flex flex-col gap-[14px] p-6">
          <h1 className="m-0 text-[32px]">{labels.errors.notFoundTitle}</h1>
          <p className="text-sm text-neutral-700">{labels.errors.notFoundHint}</p>
          <Link href="/" className="btn btn-primary self-start">
            {labels.errors.backHome}
          </Link>
        </section>
      </div>
    </main>
  );
}
