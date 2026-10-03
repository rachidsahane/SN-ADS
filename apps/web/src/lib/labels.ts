/**
 * Tous les textes affichés par l'interface (anglais). Glossaire : docs/PRD.md section 8.
 * Les textes de chaque phase s'ajoutent ici, jamais en dur dans les composants.
 */
export const labels = {
  app: {
    name: "Soro Nua Campaign Predictor",
    wordmark: "SN ADS",
    tagline: "Predict the performance of online advertising campaigns.",
    agency: "Soro Nua Agency",
  },
  status: {
    sectionTitle: "System status",
    api: {
      checking: "API: checking…",
      healthy: "API: healthy",
      unreachable: "API: unreachable",
    },
  },
  errors: {
    generic: "Something went wrong.",
    genericHint: "Please try again. If the problem continues, contact an administrator.",
    reference: (reference: string) => `Reference: ${reference}`,
    tryAgain: "Try again",
    notFoundTitle: "Page not found",
    notFoundHint: "The page you are looking for does not exist.",
    backHome: "Back to home",
    serviceUnavailable:
      "The service is temporarily unavailable. Please try again in a few minutes.",
  },
  /** Glossaire du PRD section 8 : libellé affiché de chaque champ et de chaque résultat. */
  glossary: {
    campaignChannel: "Channel",
    campaignType: "Campaign type",
    adSpend: "Ad spend (USD)",
    age: "Age",
    gender: "Gender",
    income: "Income (USD / year)",
    previousPurchases: "Previous purchases",
    loyaltyPoints: "Loyalty points",
    pagesPerVisit: "Pages per visit",
    timeOnSite: "Time on site (minutes)",
    socialShares: "Social shares",
    emailOpens: "Email opens",
    emailClicks: "Email clicks",
    advertisingPlatform: "Advertising platform",
    advertisingTool: "Advertising tool",
    clickThroughRate: "Click-through rate",
    conversionRate: "Conversion rate",
    websiteVisits: "Website visits",
    estimatedLeads: "Estimated leads",
    estimatedCostPerResult: "Estimated cost per result",
    performanceLevel: "Performance level",
  },
} as const;

export type Labels = typeof labels;
