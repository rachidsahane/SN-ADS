/** Clés TanStack Query centralisées (LLD.md section 8). */
export const queryKeys = {
  me: () => ["me"] as const,
  adminUsers: () => ["admin", "users"] as const,
  adminAudit: () => ["admin", "audit"] as const,
};
