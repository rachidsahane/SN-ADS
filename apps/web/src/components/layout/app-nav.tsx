"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useMe } from "@/hooks/use-me";
import { labels } from "@/lib/labels";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string };

const MARKETER_ITEMS: NavItem[] = [
  { href: "/predict", label: labels.nav.predict },
  { href: "/history", label: labels.nav.history },
  { href: "/model", label: labels.nav.model },
];
const ADMIN_ITEMS: NavItem[] = [
  { href: "/admin/data", label: labels.nav.data },
  { href: "/admin/models", label: labels.nav.models },
  { href: "/admin/users", label: labels.nav.users },
  { href: "/admin/audit", label: labels.nav.audit },
];

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const current = pathname === item.href || pathname.startsWith(`${item.href}/`);
  return (
    <Link
      href={item.href}
      aria-current={current ? "page" : undefined}
      className={cn(
        "flex items-center whitespace-nowrap border-b-2 px-3 font-heading text-[15px] font-semibold tracking-[0.02em] no-underline hover:text-brand-700",
        current ? "border-brand text-brand-700" : "border-transparent text-foreground",
      )}
    >
      {item.label}
    </Link>
  );
}

/**
 * Menu principal selon le rôle (prototype : Predict, History, Model, puis le groupe « Admin »).
 * Tant que le profil charge (ou en cas d'erreur), aucun lien d'administration n'apparaît (D-087).
 */
export function AppNav() {
  const pathname = usePathname();
  const { data: me } = useMe();
  const isAdmin = me?.role === "admin";

  return (
    <nav
      aria-label={labels.nav.label}
      className="order-last flex w-full flex-wrap items-stretch gap-0.5 self-stretch md:order-none md:w-auto md:flex-1"
    >
      {MARKETER_ITEMS.map((item) => (
        <NavLink key={item.href} item={item} pathname={pathname} />
      ))}
      {isAdmin ? (
        <>
          <div aria-hidden="true" className="mx-2.5 my-3.5 w-px bg-divider" />
          <div className="mr-1 self-center text-[10px] uppercase tracking-[0.12em] text-neutral-700">
            {labels.nav.adminGroup}
          </div>
          {ADMIN_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </>
      ) : null}
    </nav>
  );
}
