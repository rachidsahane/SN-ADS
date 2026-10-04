import {
  ArrowDown,
  ArrowUp,
  CircleAlert,
  Info,
  LogOut,
  Trash2,
  TriangleAlert,
  Upload,
} from "lucide-react";
import type { ComponentProps } from "react";

/** Icônes de trait fin (1,5 px) du prototype ; décoratives, donc masquées aux lecteurs d'écran. */
type IconProps = Omit<ComponentProps<typeof Info>, "ref">;

const base = { strokeWidth: 1.5, "aria-hidden": true, focusable: false } as const;

export const LogOutIcon = (p: IconProps) => <LogOut size={15} {...base} {...p} />;
export const UploadIcon = (p: IconProps) => <Upload size={15} {...base} {...p} />;
export const TrashIcon = (p: IconProps) => <Trash2 size={15} {...base} {...p} />;
export const WarningIcon = (p: IconProps) => <TriangleAlert size={18} {...base} {...p} />;
export const InfoIcon = (p: IconProps) => <Info size={16} {...base} {...p} />;
export const ErrorIcon = (p: IconProps) => <CircleAlert size={13} {...base} {...p} />;
export const ArrowUpIcon = (p: IconProps) => <ArrowUp size={13} {...base} {...p} />;
export const ArrowDownIcon = (p: IconProps) => <ArrowDown size={13} {...base} {...p} />;

/** Anneau qui tourne ; on dessine l arc du prototype. */
export function SpinnerIcon({ size = 14 }: { size?: number }) {
  return (
    <span className="spin inline-flex" aria-hidden="true">
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      >
        <path d="M21 12a9 9 0 1 1-6.2-8.56" />
      </svg>
    </span>
  );
}
