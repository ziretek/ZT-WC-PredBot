from datetime import datetime
from typing import Optional

from wcbot.models.prediction import PredictionResult


def format_prediction(result: PredictionResult, home: str, away: str) -> str:
    parts = []

    parts.append(f"🎯 *{home} vs {away}*\n")

    parts.append(f"*Prediction:* {result.winner} "
                 f"({result.home_score}–{result.away_score})")

    conf_bar = _confidence_bar(result.confidence)
    parts.append(f"*Confidence:* {result.confidence:.0%} {conf_bar}")
    parts.append(f"*Model:* `{result.model_version}`")
    parts.append("")

    eb = result.ensemble_breakdown
    parts.append("*Ensemble Breakdown:*")
    parts.append(f"▸ Elo: {eb.elo.get('winner', '?')} "
                 f"({eb.elo.get('home_score', '?')}–{eb.elo.get('away_score', '?')}, "
                 f"conf {eb.elo.get('confidence', 0):.0%})")
    parts.append(f"▸ Poisson xG: {eb.poisson_xg.get('winner', '?')} "
                 f"({eb.poisson_xg.get('home_score', '?')}–{eb.poisson_xg.get('away_score', '?')}, "
                 f"conf {eb.poisson_xg.get('confidence', 0):.0%})")
    parts.append(f"▸ Gradient Boosting: {eb.gradient_boosting.get('winner', '?')} "
                 f"({eb.gradient_boosting.get('home_score', '?')}–{eb.gradient_boosting.get('away_score', '?')}, "
                 f"conf {eb.gradient_boosting.get('confidence', 0):.0%})")
    parts.append(f"▸ LLM Weighted: {eb.llm_weighted.get('winner', '?')} "
                 f"({eb.llm_weighted.get('home_score', '?')}–{eb.llm_weighted.get('away_score', '?')}, "
                 f"conf {eb.llm_weighted.get('confidence', 0):.0%})")
    parts.append("")

    factors = "\n".join(
        f"• {f['factor'].replace('_', ' ').title()}: {f['direction']} "
        f"(impact {f['impact']:.0%})"
        for f in result.key_factors[:3]
    )
    parts.append(f"*Key Factors:*\n{factors}")
    parts.append("")

    parts.append(f"*Analysis:*\n{result.reasoning}")

    if result.low_consensus:
        parts.append("\n⚠️ *Low Consensus* — Ensemble models disagree on this outcome")

    return "\n".join(parts)


def format_tentative_prediction(result: PredictionResult, home: str, away: str,
                                min_models: int, min_confidence: float) -> str:
    parts = [
        f"🎯 *{home} vs {away}*",
        "",
        f"*Prediction (low confidence):* {result.winner} "
        f"({result.home_score}–{result.away_score})",
        f"*Model confidence:* {result.confidence:.0%} {_confidence_bar(result.confidence)}",
        "",
        "⚠️ Treat this as a lean, not a strong pick. It misses one or more reliability checks:",
        f"• Needs ≥{min_models} of 4 models agreeing",
        f"• Needs ≥{min_confidence:.0%} ensemble confidence",
        "",
        f"*Why it leans this way:*\n{result.reasoning}",
        "",
        "Use `/match` for the full dossier or `/simulate` for tournament odds.",
    ]

    if result.low_consensus:
        parts.insert(6, "• Current model consensus is low")

    return "\n".join(parts)


def format_leaderboard(entries: list, title: str = "🏆 Leaderboard") -> str:
    if not entries:
        return f"{title}\n\nNo predictions yet — be the first!"

    lines = [f"{title}\n"]
    for e in entries[:20]:
        name = e.first_name or e.username or f"User_{e.rank}"
        lines.append(
            f"{_rank_emoji(e.rank)} *{name}* — {e.points} pts "
            f"({e.correct_predictions}/{e.total_predictions}, {e.accuracy:.0%})"
        )
    return "\n".join(lines)


def format_simulation(results: dict) -> str:
    text = "🎲 *Monte Carlo Simulation* (10k iterations)\n\n"
    text += "*Champion Odds:*\n"
    for team, pct in list(results.get("champion_pct", {}).items())[:5]:
        bar = "█" * int(pct / 5)
        text += f"• {team}: {pct}% {bar}\n"
    text += "\n*Top 4 Odds:*\n"
    for team, pct in list(results.get("top4_pct", {}).items())[:5]:
        text += f"• {team}: {pct}%\n"
    return text


def format_model_card(card: dict) -> str:
    parts = [
        "🧠 *Model Card*\n",
        f"*Version:* `{card.get('model_version')}`",
        f"*Accuracy:* {card.get('accuracy', 0):.1%}",
        f"*Brier Score:* {card.get('brier_score', 0):.3f}",
        f"*Log Loss:* {card.get('log_loss', 0):.3f}",
        f"*Teams Tracked:* {card.get('elo_teams_tracked', 0)}",
        f"*Matches Recorded:* {card.get('elo_matches_recorded', 0)}",
        f"*Last Updated:* {card.get('last_update', 'N/A')[:10]}\n",
        "*Ensemble Weights:*",
    ]
    weights = card.get("model_weights", {})
    for model, weight in sorted(weights.items(), key=lambda x: -x[1]):
        parts.append(f"▸ {model.title()}: {weight:.0%}")
    parts.append("")
    parts.append("*Models:*")
    for m in card.get("ensemble_models", []):
        parts.append(f"• {m}")
    return "\n".join(parts)


def format_standings(standings: list, group: Optional[str] = None) -> str:
    title = f"📊 *Group {group or 'Standings'}*\n\n"
    if not standings:
        return title + "No data available yet."

    lines = [title]
    for i, team in enumerate(standings[:8]):
        lines.append(
            f"{i + 1}. {team.get('name', 'Unknown')} — "
            f"{team.get('points', 0)}pts | "
            f"GD: {team.get('goal_diff', 0)}"
        )
    return "\n".join(lines)


def format_team_list(teams: list) -> str:
    text = "🌍 *Qualified Teams — Power Rankings*\n\n"
    for i, t in enumerate(teams[:30], 1):
        text += f"{i}. {t.get('name', '?')} — Rating: {t.get('rating', 70)}/100\n"
    return text


def format_insights(predictions: list) -> str:
    text = "🔮 *Today's High-Value Upset Predictions*\n\n"
    for p in predictions[:3]:
        text += (
            f"• *{p.get('home', '?')} vs {p.get('away', '?')}*\n"
            f"  Prediction: {p.get('winner', '?')} "
            f"({p.get('confidence', 0):.0%} confidence)\n"
            f"  Reasoning: {p.get('reasoning', '')}\n\n"
        )
    return text or "No upsets detected today."


def format_help() -> str:
    return (
        "⚽ *ZT WC PredBot — 2026 World Cup Predictions*\n\n"
        "*Commands:*\n"
        "`/predict <home> vs <away>` — Get AI prediction\n"
        "`/predict round of 32` — Round of 32 outlook\n"
        "`/round32` — Round of 32 outlook\n"
        "`/winner` — World Cup winner forecast\n"
        "`/predictions` — Your prediction history\n"
        "`/leaderboard` — Global rankings\n"
        "`/standings` — Group tables\n"
        "`/teams` — All qualified teams\n"
        "`/match <t1> vs <t2>` — Match dossier\n"
        "`/simulate` — Monte Carlo simulation\n"
        "`/model` — Live model performance\n"
        "`/insights` — Today's upset picks\n"
        "`/subscribe <team>` — Team alerts\n"
        "`/feedback <id> <y/n>` — Flag prediction\n"
        "`/settings` — Your preferences\n"
        "`/help` — This message\n\n"
        "Built with a 4-model ensemble plus optional LLM reasoning."
    )


def format_prediction_history(predictions: list, username: str) -> str:
    if not predictions:
        return f"📋 *{username}'s Predictions*\n\nNo predictions yet."

    text = f"📋 *{username}'s Predictions*\n\n"
    correct = sum(1 for p in predictions if p.was_correct)
    total = len(predictions)
    text += f"Accuracy: {correct}/{total} ({correct / total:.0%})\n\n"

    for p in predictions[-10:]:
        icon = "✅" if p.was_correct else "❌" if p.was_correct is False else "⏳"
        text += (
            f"{icon} *{p.home_team} vs {p.away_team}*\n"
            f"   Predicted: {p.predicted_home_score}-{p.predicted_away_score} "
            f"(conf: {p.confidence:.0%})\n"
        )
        if p.actual_home_score is not None:
            text += f"   Actual: {p.actual_home_score}-{p.actual_away_score} | "
            text += f"Points: {p.points_awarded or 0}\n"
        text += "\n"
    return text


def format_settings(settings) -> str:
    return (
        f"⚙️ *Your Settings*\n\n"
        f"Language: `{settings.language}`\n"
        f"Units: `{settings.units}`\n"
        f"Lineup alerts: {'✅' if settings.alert_on_lineups else '❌'}\n"
        f"Prediction alerts: {'✅' if settings.alert_on_prediction else '❌'}\n"
        f"Live score alerts: {'✅' if settings.alert_on_live_score else '❌'}\n"
        f"Model verbosity: `{settings.model_verbosity}`"
    )


def _confidence_bar(confidence: float) -> str:
    bars = int(confidence * 10)
    return "█" * bars + "░" * (10 - bars)


def _rank_emoji(rank: int) -> str:
    if rank == 1:
        return "🥇"
    if rank == 2:
        return "🥈"
    if rank == 3:
        return "🥉"
    return f"{rank}."
