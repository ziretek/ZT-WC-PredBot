from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LeaderboardTimeframe(Enum):
    ALL = "all"
    MATCHDAY = "matchday"
    GROUP_STAGE = "group_stage"
    KNOCKOUT = "knockout"


@dataclass
class LeaderboardEntry:
    rank: int
    username: Optional[str]
    first_name: Optional[str]
    points: int
    total_predictions: int
    correct_predictions: int
    accuracy: float
    avatar_url: Optional[str] = None
