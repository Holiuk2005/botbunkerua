from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Player:
    user_id: int
    username: str
    alive: bool = True
    character: dict = field(default_factory=dict)


@dataclass
class Game:
    chat_id: int
    players: Dict[int, Player] = field(default_factory=dict)  # user_id -> Player

    # votes[target_user_id] = count
    votes: dict = field(default_factory=lambda: defaultdict(int))

    # voter_id -> target_id (to enforce 1 vote per player)
    voter_map: Dict[int, int] = field(default_factory=dict)

    round: int = 0
    started: bool = False
    phase: str = "lobby"  # lobby|voting
    admin_id: Optional[int] = None

    def bunker_capacity(self) -> int:
        return math.ceil(len(self.players) / 2)

    def alive_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.alive]

    def new_game(self, requested_by: int) -> None:
        self.players.clear()
        self.votes.clear()
        self.voter_map.clear()
        self.round = 0
        self.started = False
        self.phase = "lobby"
        self.admin_id = requested_by

    def end_game(self) -> None:
        self.players.clear()
        self.votes.clear()
        self.voter_map.clear()
        self.round = 0
        self.started = False
        self.phase = "lobby"
        self.admin_id = None

    def join(self, user_id: int, username: str, character: dict) -> Player:
        if self.started:
            raise RuntimeError("Гра вже стартувала — набір закритий")
        if user_id in self.players:
            return self.players[user_id]
        player = Player(user_id=user_id, username=username, alive=True, character=character)
        self.players[user_id] = player
        return player

    def start_game(self, requested_by: int) -> None:
        if self.started:
            return
        if len(self.players) < 2:
            raise RuntimeError("Потрібно мінімум 2 гравці")
        if self.admin_id is None:
            self.admin_id = requested_by
        elif self.admin_id != requested_by:
            raise PermissionError("Тільки адміністратор може стартувати")
        self.started = True
        self.phase = "lobby"

    def start_round(self, requested_by: int) -> None:
        if not self.started:
            raise RuntimeError("Гра ще не стартувала")
        if self.admin_id != requested_by:
            raise PermissionError("Тільки адміністратор може запускати раунди")
        self.round += 1
        self.phase = "voting"
        self.votes.clear()
        self.voter_map.clear()

    def vote(self, voter_id: int, target_username: str) -> bool:
        if not self.started or self.phase != "voting" or self.round <= 0:
            raise RuntimeError("Зараз не йде голосування. Чекайте /round")
        voter = self.players.get(voter_id)
        if voter is None or not voter.alive:
            raise RuntimeError("Вас немає серед живих гравців")

        target_username = target_username.lstrip("@").lower()
        target_id: Optional[int] = None
        for p in self.players.values():
            if p.alive and p.username and p.username.lower() == target_username:
                target_id = p.user_id
                break

        if target_id is None:
            return False
        if target_id == voter_id:
            raise RuntimeError("Самоусунення заборонене")

        # Re-vote: subtract old vote, add new
        old_target = self.voter_map.get(voter_id)
        if old_target is not None:
            self.votes[old_target] -= 1
            if self.votes[old_target] <= 0:
                self.votes.pop(old_target, None)

        self.voter_map[voter_id] = target_id
        self.votes[target_id] += 1
        return True

    def eliminate_player(self) -> Optional[Player]:
        if not self.votes:
            return None

        max_votes = max(self.votes.values())
        candidates = [uid for uid, count in self.votes.items() if count == max_votes]

        # Tie-break: leave it deterministic enough by picking smallest id
        eliminated_id = sorted(candidates)[0]
        eliminated = self.players[eliminated_id]
        eliminated.alive = False

        self.votes.clear()
        self.voter_map.clear()
        self.phase = "lobby"
        return eliminated

    def is_finished(self) -> bool:
        return self.started and len(self.alive_players()) <= self.bunker_capacity()

    def status_text(self) -> str:
        phase = {"lobby": "лобі/очікування", "voting": "йде голосування"}.get(self.phase, self.phase)
        return (
            f"Статус: {'стартувала' if self.started else 'не стартувала'}\n"
            f"Раунд: {self.round}\n"
            f"Фаза: {phase}\n"
            f"Гравців: {len(self.players)} (живих: {len(self.alive_players())})\n"
            f"Місць у бункері: {self.bunker_capacity()}"
        )
