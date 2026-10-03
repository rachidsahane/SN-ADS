"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useMe } from "@/hooks/use-me";
import { labels } from "@/lib/labels";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string };

const MARKETER_ITEMS: NavItem[] = [{ href: "/predict", label: labels.nav.predict }];
const ADMIN_ITEMS: NavItem[] = [
  ...MARKETER_ITEMS,
  { href: "/admin/users", label: labels.nav.users },
  { href: "/admin/audit", label: labels.nav.audit },
];

/**
 * Menu principal selon le rôle. Tant que le profil charge (ou en cas d'erreur), seul « Predict »
 * apparaît : jamais de lien d'administration affiché par erreur (D-087).
 */
export function AppNav() {
  const pathname = usePathname();
  const { data: me } = useMe();
  const items = me?.role === "admin" ? ADMIN_ITEMS : MARKETER_ITEMS;

  return (
    <nav
      aria-label={labels.nav.label}
      className="order-last flex w-full items-center gap-4 text-sm sm:order-none sm:w-auto"
    >
      {items.map((item) => {
        const current = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className={cn(
              "whitespace-nowrap no-underline hover:underline",
              current ? "font-semibold text-foreground" : "text-muted-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
