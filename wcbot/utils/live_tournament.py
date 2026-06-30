from datetime import datetime, timezone


def fixture_context(fixture: dict) -> dict:
    return {
        "confirmed_fixture": True,
        "fixture_id": fixture.get("id", ""),
        "commence_time": fixture.get("commence_time", ""),
        "market_home_prob": fixture.get("market_home_prob", 0.0),
        "market_draw_prob": fixture.get("market_draw_prob", 0.0),
        "market_away_prob": fixture.get("market_away_prob", 0.0),
        "bookmaker_count": fixture.get("bookmaker_count", 0),
        "live_home_score": fixture.get("home_score") if fixture.get("home_score") is not None else "not started",
        "live_away_score": fixture.get("away_score") if fixture.get("away_score") is not None else "not started",
    }


def format_kickoff(value: str) -> str:
    if not value:
        return "Kickoff time unavailable"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        return parsed.strftime("%d %b, %H:%M UTC")
    except ValueError:
        return value


def format_live_fixture_note(fixture: dict) -> str:
    lines = [
        "",
        "*Live tournament data:*",
        f"• Confirmed fixture: {format_kickoff(fixture.get('commence_time', ''))}",
    ]
    if fixture.get("bookmaker_count"):
        lines.extend([
            f"• Market: {fixture['home_team']} {fixture.get('market_home_prob', 0):.0%} | "
            f"Draw {fixture.get('market_draw_prob', 0):.0%} | "
            f"{fixture['away_team']} {fixture.get('market_away_prob', 0):.0%}",
            f"• Consensus from {fixture['bookmaker_count']} bookmakers",
        ])
    if fixture.get("status") == "live":
        lines.append(
            f"• Live score: {fixture.get('home_score', '?')}–{fixture.get('away_score', '?')}"
        )
    lines.append("• Source: The Odds API FIFA World Cup feed")
    return "\n".join(lines)


def format_completed_match(fixture: dict) -> str:
    return (
        f"✅ *Full time — {fixture['home_team']} vs {fixture['away_team']}*\n\n"
        f"*Result:* {fixture.get('home_score', '?')}–{fixture.get('away_score', '?')}\n"
        f"Played: {format_kickoff(fixture.get('commence_time', ''))}\n\n"
        "This match has finished, so I will not issue a new prediction."
    )


def format_unscheduled_match(home: str, away: str, upcoming: list) -> str:
    text = (
        f"📅 *{home} vs {away} is not in the confirmed live fixture feed.*\n\n"
        "I only issue ongoing 2026 World Cup predictions for scheduled matches."
    )
    if upcoming:
        text += "\n\n*Next confirmed fixtures:*\n"
        for event in upcoming[:4]:
            text += (
                f"• {event['home_team']} vs {event['away_team']} — "
                f"{format_kickoff(event.get('commence_time', ''))}\n"
            )
    text += "\nUse `/fixtures` for the full upcoming list."
    return text


def format_winner_market(market: list, title: str = "Live World Cup Winner Forecast") -> str:
    lines = [f"🏆 *{title}*", ""]
    for rank, item in enumerate(market[:10], 1):
        lines.append(
            f"{rank}. *{item['team']}* — {item['probability']:.1%} "
            f"(odds {item['decimal_odds']:.2f})"
        )
    lines.extend([
        "",
        "Probabilities are normalized consensus prices from the live outright market, not guarantees.",
        "Source: The Odds API FIFA World Cup Winner feed.",
    ])
    return "\n".join(lines)
