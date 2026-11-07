"""River-only raising poker bot for the Manchester AI Society poker arena."""

import math
import random
import time

from card_utils import Card, evaluate, full_deck
from game_state import GameStateView
from player_action import PlayerAction


def win(
    hole_cards: tuple[Card, Card],
    opponent_hole_cards: tuple[Card, Card],
    community_cards: list[Card],
) -> float:
    """1 for a win, 0.5 for a tie, 0 for a loss."""
    my_rank = evaluate([*hole_cards, *community_cards])
    their_rank = evaluate([*opponent_hole_cards, *community_cards])
    if my_rank > their_rank:
        return 1.0
    if my_rank == their_rank:
        return 0.5
    return 0.0


def monte_carlo_win_prob(
    hole_cards: tuple[Card, Card],
    community_cards: list[Card],
    deck: list[Card],
    time_bound: float = 0.2,
) -> float:
    """Estimate heads-up equity against uniformly random opponent hole cards."""
    score = 0.0
    n = 0
    count_to_draw = 7 - len(community_cards)
    deadline = time.perf_counter() + time_bound

    while time.perf_counter() < deadline:
        sampled = random.sample(deck, count_to_draw)
        score += win(
            hole_cards,
            (sampled[0], sampled[1]),
            community_cards + sampled[2:],
        )
        n += 1

    return score / n if n else 0.0


def bankroll_percent_function(win_prob: float) -> float:
    return 0.00055 * math.exp(7.5 * win_prob) + 0.00557667204917


def bluff(win_prob: float, opponent_fold_percent: float) -> bool:
    probability = opponent_fold_percent * 0.05 * math.exp(
        -50 * (win_prob - 0.5) ** 2
    )
    return random.random() < probability


class Model:
    def __init__(self):
        self.hand: list[Card] = []
        self.player_id: int | None = None
        self.raised_on_river = False
        # Opponent team -> (hands where they folded, hands observed).
        # Plain data is compatible with the organiser's pickle format.
        self.opponent_folds: dict[str, tuple[int, int]] = {}

    def seed(self, hand: list[Card], player_id: int):
        self.hand = list(hand)
        self.player_id = player_id
        self.raised_on_river = False

    def run(
        self, actions: list[PlayerAction], game_state: GameStateView
    ) -> PlayerAction:
        me = self.player_id
        call_amount = game_state.call_amount
        river = game_state.street == "river"

        # If someone raises after our river bet, always fold.
        if river and self.raised_on_river:
            return (PlayerAction.fold(me) if call_amount > 0
                    else PlayerAction.call(me))

        # Checking costs nothing. No need to simulate until the river.
        if not river and call_amount == 0:
            return PlayerAction.call(me)

        community_cards = list(game_state.board)
        known = set(self.hand) | set(community_cards)
        deck = [card for card in full_deck() if card not in known]

        equity = monte_carlo_win_prob(
            (self.hand[0], self.hand[1]),
            community_cards,
            deck,
            time_bound=5,
        )

        # "Bankroll" means the chips we can commit this street,
        # including chips already bet on this street.
        bankroll = game_state.stacks[me] + game_state.bets[me]
        adjusted_probability = min(1.0, equity + 0.05)
        fraction = min(1.0, bankroll_percent_function(adjusted_probability))
        call_budget = bankroll * fraction

        # Call only when affordable under the sizing rule AND pot odds justify it.
        should_call = (
            call_amount == 0
            or (equity >= game_state.pot_odds and call_amount <= call_budget)
        )

        # Before the river, never raise.
        if not river:
            return PlayerAction.call(me) if should_call else PlayerAction.fold(me)

        # On the river, try a bluff or a normally distributed value bet.
        if game_state.can_raise:
            opponents = [
                player for player in game_state.players_in_hand if player != me
            ]
            opponent_bet = max((game_state.bets[p] for p in opponents), default=0)

            # Smoothed observed folding frequency (initial prior 2/5 = 40%).
            opponent = opponents[0] if opponents else None
            if opponent is None:
                opponent_fold_percent = 0.4
            else:
                team = game_state.teams[opponent]
                folds, hands = self.opponent_folds.get(team, (0, 0))
                opponent_fold_percent = (folds + 2) / (hands + 5)

            is_bluff = (
                opponent_bet <= 0.25 * bankroll
                and bluff(equity, opponent_fold_percent)
            )

            target_fraction = None
            if is_bluff:
                # Bluff around 90% of bankroll with a 5% standard deviation.
                target_fraction = random.gauss(0.90, 0.05)
            elif should_call:
                target_fraction = fraction + random.gauss(0.0, 0.025)

            if target_fraction is not None:
                desired_total = int(round(bankroll * target_fraction))
                low, high = game_state.raise_range
                # Cap an oversized bet, but do not force a too-small bet
                # into a raise the strategy did not intend to make.
                raise_total = min(desired_total, high)
                if low <= raise_total <= high:
                    action = PlayerAction.raise_to(me, raise_total)
                    game_state.validate_action(action)
                    self.raised_on_river = True
                    return action

        return PlayerAction.call(me) if should_call else PlayerAction.fold(me)

    def end_game(self, actions: list[PlayerAction], game_state: GameStateView):
        """Record the frequency each opponent folded during complete hands."""
        for player in range(game_state.num_players):
            if player == self.player_id:
                continue
            team = game_state.teams[player]
            folds, hands = self.opponent_folds.get(team, (0, 0))
            self.opponent_folds[team] = (
                folds + int(game_state.folded[player]),
                hands + 1,
            )
