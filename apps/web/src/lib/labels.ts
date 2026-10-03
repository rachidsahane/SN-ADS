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
  auth: {
    signIn: {
      title: "Sign in",
      submit: "Sign in",
      submitting: "Signing in…",
      email: "Email",
      password: "Password",
      forgotLink: "Forgot password?",
      invalidCredentials: "Invalid email or password.",
    },
    forgot: {
      title: "Forgot password",
      intro: "Enter your email address and we will send you a link to set a new password.",
      submit: "Send reset link",
      submitting: "Sending…",
      sent: "If an account exists for this email, a link to set a new password has been sent.",
      backToSignIn: "Back to sign in",
    },
    setPassword: {
      title: "Set your password",
      password: "Password",
      confirmation: "Confirm password",
      submit: "Set password",
      submitting: "Saving…",
      tooShort: "Password must be at least 10 characters.",
      tooLong: "Password must be at most 72 characters.",
      mismatch: "Passwords do not match.",
      samePassword: "Choose a password you have not used before.",
    },
    invalidLink: "This link is invalid or has expired. Ask an administrator for a new invitation.",
    signOut: "Sign out",
    emailRequired: "Enter your email address.",
    emailInvalid: "Enter a valid email address.",
    passwordRequired: "Enter your password.",
    tooManyRequests: "Too many requests. Please wait a moment.",
  },
  predict: { title: "Predict" },
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
