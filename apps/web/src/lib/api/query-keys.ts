/** Clés TanStack Query centralisées (LLD.md section 8). */
export const queryKeys = {
  me: () => ["me"] as const,
  adminUsers: () => ["admin", "users"] as const,
  adminAudit: () => ["admin", "audit"] as const,
  adminDataset: () => ["admin", "dataset"] as const,
  adminModels: () => ["admin", "models"] as const,
  adminModel: (id: string) => ["admin", "models", id] as const,
  activeModel: () => ["model", "active"] as const,
  referenceOptions: () => ["reference", "options"] as const,
  engagementDefaults: (channel: string, campaignType: string) =>
    ["reference", "engagement-defaults", channel, campaignType] as const,
  simulation: (modelId: string, values: unknown) => ["simulation", modelId, values] as const,
  predictions: () => ["predictions"] as const,
  prediction: (id: string) => ["predictions", id] as const,
};
