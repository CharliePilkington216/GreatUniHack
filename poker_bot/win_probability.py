import time
import random
import math
from card_utils import Card, evaluate

def win(
        hole_cards : tuple[Card, Card],
        opponent_hole_cards: tuple[Card, Card],
        community_cards: list[Card],
) -> float:
    """Compare the best hands available from the current cards."""
    model_rank = evaluate([*hole_cards, *community_cards])
    opponent_rank = evaluate([*opponent_hole_cards, *community_cards])
    if model_rank > opponent_rank:
        return 1
    if model_rank == opponent_rank:
        return 0.5
    return 0

def monte_carlo_win_prob(hole_cards : tuple[Card, Card],
                         community_cards : list[Card],
                         deck : list[Card],
                         time_bound : int = 5) -> float:
    n = 0
    win_prob = 0
    end_time = time.perf_counter() + time_bound

    while time.perf_counter() < end_time:
        sampled_cards = random.sample(deck, 7 - len(community_cards))
        win_prob = (win_prob
                + (win(hole_cards,
                    (sampled_cards[0], sampled_cards[1]),
                    community_cards + sampled_cards[2:])
                - win_prob) / (n + 1))
        n += 1

    return win_prob

def bankroll_percent_function(win_prob : float) -> float:
    return 0.00055 * math.exp(7.5 * win_prob) + 0.00557667204917

def bluff(win_prob : float, opponent_fold_percent : float) -> float:
    return random.random() < opponent_fold_percent * 0.05 * math.exp(-50 * (win_prob - 0.5) ** 2)