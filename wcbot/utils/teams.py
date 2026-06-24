import re
import unicodedata
from typing import Optional

from wcbot.data.teams import WORLD_CUP_TEAMS_2026


ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u s a": "United States",
    "united states of america": "United States",
    "america": "United States",
    "usmnt": "United States",
    "south korea": "South Korea",
    "korea republic": "South Korea",
    "republic of korea": "South Korea",
    "korea": "South Korea",
    "ivory coast": "Ivory Coast",
    "cote d ivoire": "Ivory Coast",
    "cote divoire": "Ivory Coast",
    "dr congo": "DR Congo",
    "d r congo": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "congo dr": "DR Congo",
    "curacao": "Curaçao",
    "curacao national team": "Curaçao",
    "czechia": "Czech Republic",
    "czech republic": "Czech Republic",
    "bosnia": "Bosnia and Herzegovina",
    "bosnia herzegovina": "Bosnia and Herzegovina",
}


def normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


TEAM_LOOKUP = {normalize_key(team): team for team in WORLD_CUP_TEAMS_2026}
TEAM_LOOKUP.update(ALIASES)


def normalize_team_name(raw: str) -> Optional[str]:
    key = normalize_key(raw)
    if not key:
        return None
    if key in TEAM_LOOKUP:
        return TEAM_LOOKUP[key]

    compact = key.replace(" ", "")
    for lookup_key, team in TEAM_LOOKUP.items():
        if compact == lookup_key.replace(" ", ""):
            return team
    return None


def unknown_team_message(raw: str) -> str:
    examples = ", ".join(WORLD_CUP_TEAMS_2026[:8])
    return (
        f"Unknown team: `{raw}`.\n\n"
        f"Use `/teams` to see supported teams. Examples: {examples}."
    )
