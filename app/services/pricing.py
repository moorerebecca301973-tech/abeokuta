from app.models import Addon, Attraction


def child_fee(attraction: Attraction) -> int:
    """Mirrors the React client's fallback: half the adult fee, rounded."""
    if attraction.child_entry_fee is not None:
        return attraction.child_entry_fee
    return round(attraction.entry_fee * 0.5)


def quote(
    attraction: Attraction, adults: int, children: int, addons: list[Addon]
) -> dict:
    """The single source of truth for money. The client never sends a total."""
    adult_total = attraction.entry_fee * adults
    child_total = child_fee(attraction) * children
    base = adult_total + child_total
    extras = sum(a.price for a in addons)

    breakdown = [
        {"label": f"Adults x {adults}", "amount": adult_total},
    ]
    if children:
        breakdown.append({"label": f"Children x {children}", "amount": child_total})
    breakdown.extend({"label": a.name, "amount": a.price} for a in addons)

    return {
        "currency": "NGN",
        "adult_fee": attraction.entry_fee,
        "child_fee": child_fee(attraction),
        "base_amount": base,
        "addons_amount": extras,
        "total_amount": base + extras,
        "breakdown": breakdown,
    }
