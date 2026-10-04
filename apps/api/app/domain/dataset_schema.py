"""Columns and groups of the training data (LLD 5.1, 5.2). Pure data, no I/O."""

from typing import Final

# CSV column -> internal name (LLD 5.1)
COLUMN_MAP: Final = {
    "CustomerID": "external_id",
    "Age": "age",
    "Gender": "gender",
    "Income": "income",
    "CampaignChannel": "campaign_channel",
    "CampaignType": "campaign_type",
    "AdSpend": "ad_spend",
    "ClickThroughRate": "click_through_rate",
    "ConversionRate": "conversion_rate",
    "WebsiteVisits": "website_visits",
    "PagesPerVisit": "pages_per_visit",
    "TimeOnSite": "time_on_site",
    "SocialShares": "social_shares",
    "EmailOpens": "email_opens",
    "EmailClicks": "email_clicks",
    "PreviousPurchases": "previous_purchases",
    "LoyaltyPoints": "loyalty_points",
    "AdvertisingPlatform": "advertising_platform",
    "AdvertisingTool": "advertising_tool",
    "Conversion": "conversion",
}

NUMERIC: Final = (
    "ad_spend",
    "age",
    "income",
    "previous_purchases",
    "loyalty_points",
    "pages_per_visit",
    "time_on_site",
    "social_shares",
    "email_opens",
    "email_clicks",
)
# Same values, case and spaces as the database enumerations (DATA_MODEL 3).
CATEGORICAL: Final = {
    "campaign_channel": ("Social Media", "Email", "PPC", "SEO", "Referral"),
    "campaign_type": ("Awareness", "Consideration", "Conversion", "Retention"),
    "gender": ("Male", "Female"),
}
OPTIONAL: Final = ("advertising_platform", "advertising_tool")
ENGAGEMENT: Final = (
    "pages_per_visit",
    "time_on_site",
    "social_shares",
    "email_opens",
    "email_clicks",
)

TARGETS: Final = ("click_through_rate", "conversion_rate", "website_visits")
RATE_TARGETS: Final = ("click_through_rate", "conversion_rate")

# Columns of `dataset_rows` read to train, and written by the seed command.
ROW_COLUMNS: Final = (
    "external_id",
    "is_holdout",
    *NUMERIC,
    *CATEGORICAL,
    *OPTIONAL,
    *TARGETS,
)

# Bounds of the campaign form (API_SPEC 5.1), shown by `GET /reference/options`.
LIMITS: Final = {
    "ad_spend": {"min_exclusive": 0, "max": 10_000_000},
    "age": {"min": 18, "max": 100},
    "income": {"min": 0, "max": 100_000_000},
    "previous_purchases": {"min": 0, "max": 10_000},
    "loyalty_points": {"min": 0, "max": 10_000_000},
    "pages_per_visit": {"min": 0, "max": 1000},
    "time_on_site": {"min": 0, "max": 1440},
    "social_shares": {"min": 0, "max": 10_000_000},
    "email_opens": {"min": 0, "max": 10_000_000},
    "email_clicks": {"min": 0, "max": 10_000_000},
}
