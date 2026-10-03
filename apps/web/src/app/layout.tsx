import "@/lib/env"; // échoue au démarrage si une variable est manquante ou invalide

import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";

import { labels } from "@/lib/labels";
import { QueryProvider } from "@/providers/query-provider";

import "./globals.css";

const barlow = localFont({
  src: [
    { path: "./fonts/barlow-latin-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/barlow-latin-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/barlow-latin-700.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-barlow",
  display: "swap",
});

const barlowCondensed = localFont({
  src: [
    { path: "./fonts/barlow-condensed-latin-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/barlow-condensed-latin-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-barlow-condensed",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: labels.app.name, template: `%s · ${labels.app.name}` },
  description: labels.app.tagline,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${barlow.variable} ${barlowCondensed.variable}`}>
      <body className="min-h-screen">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
