from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TournamentStage(Enum):
    GROUP = "group"
    ROUND_OF_16 = "round_of_16"
    QUARTER_FINAL = "quarter_final"
    SEMI_FINAL = "semi_final"
    THIRD_PLACE = "third_place"
    FINAL = "final"


class MatchStatus(Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


@dataclass
class Team:
    name: str
    fifa_rank: int = 0
    elo_rating: float = 1500.0
    group: Optional[str] = None
    flag_emoji: str = ""


@dataclass
class Match:
    match_id: str
    home_team: Team
    away_team: Team
    kickoff: datetime
    stage: TournamentStage
    status: MatchStatus = MatchStatus.SCHEDULED
    venue: Optional[str] = None
    weather: Optional[str] = None
    referee: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None
