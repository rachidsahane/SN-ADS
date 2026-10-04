"""Figures derived from the three predictions (LLD 6.2)."""


def estimated_leads(website_visits: float, conversion_rate: float) -> float:
    return website_visits * conversion_rate


def estimated_cost_per_result(ad_spend: float, leads: float) -> float | None:
    return ad_spend / leads if leads > 0 else None
