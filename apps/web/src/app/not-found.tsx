import Link from "next/link";

import { labels } from "@/lib/labels";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col justify-center gap-3 px-6">
      <h1>{labels.errors.notFoundTitle}</h1>
      <p className="text-neutral-700">{labels.errors.notFoundHint}</p>
      <Link href="/">{labels.errors.backHome}</Link>
    </main>
  );
}
