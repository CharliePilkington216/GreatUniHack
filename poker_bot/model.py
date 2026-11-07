from card_utils import Card
from game_state import GameStateView
from player_action import PlayerAction


class Model:
    """
    Your bot: change anything in this file, and add files next to it.

    This object is what gets pickled, so load weights and data in __init__
    and keep them in plain attributes.
    """

    def __init__(self):
        # Load weights, and set up anything you learn across hands (e.g.
        # about other teams, by game_state.teams), here.
        self.hand = []
        self.player_id = None

    def seed(self, hand: list[Card], player_id: int):
        """
        Called once before the hand: your two hole cards and your id.

        Store them; run() is not given them again.
        """
        self.hand = hand
        self.player_id = player_id

    def run(
        self, actions: list[PlayerAction], game_state: GameStateView
    ) -> PlayerAction:
        """
        Called on your turn.

        actions: everything done since your last turn this hand, oldest
            first: player moves, your own previous move included, and the
            dealer's reveal_card.
        game_state: the public state of the hand, read-only, e.g.
            game_state.call_amount, game_state.status(self.player_id),
            game_state.min_raise_to.
        """
        return PlayerAction.call(self.player_id)


    def end_game(
        self, actions: list[PlayerAction], game_state: GameStateView
    ):
        """
        Called after every hand, whether or not you were still in it.

        actions: everything since your last turn: the last moves, then at a
            showdown each remaining player's hole cards (reveal_card with
            that player's id; the dealer's reveal_card is a board card),
            then one win per player who won chips (amount = their total
            from every pot). A player who wins because everyone else
            folded shows nothing.
        game_state: the final state of the hand, stacks after the pot.

        Learn from the hand here. Per-hand fields need no clearing: seed()
        sets them again at the start of the next hand.
        """
        pass
