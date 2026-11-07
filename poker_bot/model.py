"""Heads-up no-limit hold'em agent for the Manchester AI Society arena.

Drop this file next to the organisers' card_utils.py, player_action.py and
engine files. No third-party dependencies or external data files are needed.
"""

from bisect import bisect_left
import math
import random

# Cards are encoded as 4 * (rank - 2) + suit, where suits are C, D, H, S.
_RANK = tuple(i // 4 + 2 for i in range(52))
_SUIT = tuple(i % 4 for i in range(52))
_DECK = tuple(range(52))
_SUITS = "CDHS"


def _straight(mask):
    """Largest 5-card straight in a rank bitmask; 5 for the wheel."""
    if mask & (1 << 14):
        mask |= 1 << 1
    for top in range(14, 4, -1):
        if (mask >> (top - 4)) & 31 == 31:
            return top
    return 0


def _rank7(cards):
    """Fast exact 5-7-card hand evaluator, higher tuple wins."""
    count = [0] * 15
    suits = [0] * 4
    suitmask = [0] * 4
    mask = 0
    for c in cards:
        r = _RANK[c]
        s = _SUIT[c]
        count[r] += 1
        suits[s] += 1
        suitmask[s] |= 1 << r
        mask |= 1 << r
    for s in range(4):
        if suits[s] >= 5:
            st = _straight(suitmask[s])
            if st:
                return (8, st)
            flush = [r for r in range(14, 1, -1) if suitmask[s] & (1 << r)]
            flush = tuple(flush[:5])
            break
    else:
        flush = None
    fours = [r for r in range(14, 1, -1) if count[r] == 4]
    if fours:
        return (7, fours[0], max(r for r in range(2, 15) if r != fours[0] and count[r]))
    trips = [r for r in range(14, 1, -1) if count[r] >= 3]
    if trips:
        pairs = [r for r in range(14, 1, -1) if r != trips[0] and count[r] >= 2]
        if pairs:
            return (6, trips[0], pairs[0])
    if flush:
        return (5,) + flush
    straight = _straight(mask)
    if straight:
        return (4, straight)
    if trips:
        return (3, trips[0]) + tuple(r for r in range(14, 1, -1) if r != trips[0] and count[r])[:2]
    pairs = [r for r in range(14, 1, -1) if count[r] >= 2]
    if len(pairs) >= 2:
        kicker = max(r for r in range(2, 15) if r != pairs[0] and r != pairs[1] and count[r])
        return (2, pairs[0], pairs[1], kicker)
    if pairs:
        return (1, pairs[0]) + tuple(r for r in range(14, 1, -1) if r != pairs[0] and count[r])[:3]
    return (0,) + tuple(r for r in range(14, 1, -1) if count[r])[:5]


# Monte Carlo preflop equities vs a uniform random heads-up hand (3,600
# independently sampled runouts per hand class; generated offline). Row/column
# ranks descend A..2. Upper triangle = suited, lower = offsuit.
_PREFLOP_EQUITY = (
    (0.8392, 0.6774, 0.6624, 0.6338, 0.6476, 0.6235, 0.6076, 0.6228, 0.5846, 0.6104, 0.5867, 0.5724, 0.5693),
    (0.6643, 0.8208, 0.6321, 0.6194, 0.6397, 0.6024, 0.5740, 0.5707, 0.5661, 0.5475, 0.5410, 0.5378, 0.5340),
    (0.6419, 0.6253, 0.8044, 0.5965, 0.5993, 0.5746, 0.5657, 0.5476, 0.5376, 0.5225, 0.5236, 0.5053, 0.5071),
    (0.6319, 0.6139, 0.5815, 0.7890, 0.5707, 0.5567, 0.5339, 0.5271, 0.5144, 0.4965, 0.4958, 0.4994, 0.4721),
    (0.6157, 0.5908, 0.5851, 0.5571, 0.7547, 0.5432, 0.5175, 0.5119, 0.4803, 0.4590, 0.4581, 0.4593, 0.4558),
    (0.6036, 0.5796, 0.5387, 0.5364, 0.5276, 0.7054, 0.5064, 0.4938, 0.4947, 0.4497, 0.4407, 0.4386, 0.4346),
    (0.6082, 0.5474, 0.5336, 0.5164, 0.4924, 0.4813, 0.6871, 0.4743, 0.4544, 0.4532, 0.4214, 0.4142, 0.4049),
    (0.5893, 0.5536, 0.5196, 0.4917, 0.4690, 0.4507, 0.4633, 0.6622, 0.4415, 0.4424, 0.4240, 0.3975, 0.3757),
    (0.5778, 0.5314, 0.4971, 0.4854, 0.4640, 0.4474, 0.4371, 0.4182, 0.6393, 0.4343, 0.4078, 0.3851, 0.3833),
    (0.5786, 0.5204, 0.5065, 0.4814, 0.4475, 0.4214, 0.4165, 0.4147, 0.3931, 0.6000, 0.4210, 0.3997, 0.3703),
    (0.5582, 0.5215, 0.4839, 0.4590, 0.4551, 0.3994, 0.4046, 0.3840, 0.3768, 0.3867, 0.5732, 0.3743, 0.3935),
    (0.5536, 0.5044, 0.4794, 0.4550, 0.4238, 0.4014, 0.3736, 0.3668, 0.3624, 0.3721, 0.3504, 0.5219, 0.3521),
    (0.5482, 0.5008, 0.4658, 0.4518, 0.4082, 0.3987, 0.3629, 0.3468, 0.3331, 0.3415, 0.3337, 0.2901, 0.5058),
)

def _holdem_strength(a, b):
    """Approximately exact HU preflop equity against a random holding."""
    x, y = sorted((_RANK[a], _RANK[b]), reverse=True)
    if x == y or _SUIT[a] == _SUIT[b]:
        return _PREFLOP_EQUITY[14 - x][14 - y]
    return _PREFLOP_EQUITY[14 - y][14 - x]


def _texture(cards, board):
    """Opponent's approximate *current* showdown strength + draw quality."""
    made = _rank7(cards + board)
    cat = made[0]
    board_ranks = [_RANK[c] for c in board]
    top = max(board_ranks)
    if cat >= 6:
        value = 1.0
    elif cat == 5:
        value = .99
    elif cat == 4:
        value = .97
    elif cat == 3:
        value = .93
    elif cat == 2:
        value = .82 if made[1] >= top else .70
    elif cat == 1:
        pair = made[1]
        if pair > top:
            value = .78
        elif pair == top:
            value = .72 if pair in (_RANK[cards[0]], _RANK[cards[1]]) else .38
        elif pair in board_ranks:
            value = .35 if pair not in (_RANK[cards[0]], _RANK[cards[1]]) else .55
        else:
            value = .51 if pair >= sorted(board_ranks, reverse=True)[min(1, len(board_ranks) - 1)] else .37
    else:
        value = .08 + .015 * (max(_RANK[c] for c in cards) - 7)
    if len(board) < 5:
        suit_count = [0] * 4
        for c in cards + board:
            suit_count[_SUIT[c]] += 1
        flush_draw = any(suit_count[s] == 4 and any(_SUIT[c] == s for c in cards) for s in range(4))
        if flush_draw:
            value = max(value, .53 if cat <= 1 else .68)
        m = 0
        for c in cards + board:
            m |= 1 << _RANK[c]
        if m & (1 << 14):
            m |= 1 << 1
        draws = 0
        for top_rank in range(5, 15):
            bits = (m >> (top_rank - 4)) & 31
            if bits.bit_count() == 4:
                draws += 1
        if draws and cat < 4:
            value = max(value, .56 if draws >= 2 else .41)
    return min(1.0, value)


def _normal(x):
    return 1.0 / (1.0 + math.exp(-max(-24.0, min(24.0, x))))


class Model:
    """Single-file opponent-adaptive, equity-sampling poker agent."""

    def __init__(self):
        self.hand = []
        self.player_id = None
        self.history = []
        self.seen_board = []
        self.observations = {}  # team -> primitive counts, survives hands
        self.opponent = None
        self.revealed = []
        self.hand_index = 0

    def seed(self, hand, player_id):
        self.hand = list(hand)
        self.player_id = player_id
        self.history = []
        self.seen_board = []
        self.opponent = None
        self.revealed = []
        self.hand_index += 1

    @staticmethod
    def _encode(cards):
        return [4 * (c.value - 2) + _SUITS.index(c.suit) for c in cards]

    def _get_stats(self, team):
        if team not in self.observations:
            self.observations[team] = dict(hands=0, vpip=0, pfr=0, raises=0,
                                           calls=0, checks=0, folds=0,
                                           faced_hero_raise=0, folded_to_hero_raise=0,
                                           showdowns=0, bluff_showdowns=0,
                                           pre_shoves=0)
        return self.observations[team]

    def _ingest(self, actions):
        """Annotate an incremental action log with the board *at that moment*."""
        for action in actions:
            if action.kind == 'reveal_card' and action.player_id == -1:
                if action.card is not None:
                    self.seen_board.append(4 * (action.card.value - 2) + _SUITS.index(action.card.suit))
            elif action.kind == "reveal_card":
                self.revealed.append((action.player_id, 4 * (action.card.value - 2) + _SUITS.index(action.card.suit)))
            else:
                self.history.append((action.player_id, action.kind, action.amount,
                                     tuple(self.seen_board),
                                     0 if len(self.seen_board) < 3 else len(self.seen_board) - 2))

    def _styles(self, stats):
        n = stats['hands']
        looseness = (stats['vpip'] + 7.5) / (n + 11)
        aggression = (stats['raises'] + 2.8) / (stats['raises'] + stats['calls'] + stats['checks'] + 6.2)
        foldiness = (stats['folded_to_hero_raise'] + 3.2) / (stats['faced_hero_raise'] + 7.5)
        shove = (stats['pre_shoves'] + .20) / (n + 3.5)
        return looseness, aggression, foldiness, shove

    def _opp_events(self, opp_id):
        return [row for row in self.history if row[0] == opp_id and row[1] in ('raise', 'call')]

    def _range(self, hero, board, opp_id, gs, stats):
        """Belief over legal opponent hole pairs updated from betting history.

        This is a deliberately smoothed range: even strong actions retain some
        bluff probability, so the model can adapt to volatile opponents.
        """
        seen = set(hero + board)
        cards = [c for c in _DECK if c not in seen]
        loose, aggro, _, shove = self._styles(stats)
        events = self._opp_events(opp_id)
        pre = [e for e in events if e[4] == 0]
        post = [e for e in events if e[4] > 0]
        first_raise = next((e for e in pre if e[1] == 'raise'), None)
        first_bet = first_raise[2] if first_raise else 0
        previous_hero_raise = False
        forced_3bet = False
        for e in self.history:
            if e[4] != 0:
                continue
            if e[0] == self.player_id and e[1] == 'raise':
                previous_hero_raise = True
            if e[0] == opp_id and e[1] == 'raise':
                forced_3bet = previous_hero_raise
                break
        # Positions change the amount of prior information in an opening raise.
        large_raise = first_bet >= max(gs.big_blind * 7, 140)
        potential_shover = shove > .13
        observed_bluffs = (stats['bluff_showdowns'] + .65) / (stats['showdowns'] + 5.0)
        candidate = []
        weights = []
        texture_scores = []
        for i in range(len(cards)):
            a = cards[i]
            for b in cards[i + 1:]:
                h = _holdem_strength(a, b)
                # Boost likely entries while never dropping the bluff tail.
                weight = 1.0
                if first_raise:
                    if forced_3bet:
                        threshold = .59 - .08 * (aggro - .33)
                        slope = .050
                    elif large_raise:
                        threshold = .59 - .15 * min(1.0, shove * 4.0)
                        slope = .070
                    else:
                        threshold = .47 - .12 * (loose - .5)
                        slope = .070
                    weight *= .13 + .87 * _normal((h - threshold) / slope)
                elif pre and pre[0][1] == 'call':
                    # Limping or calling usually removes premiums, but slowplays exist.
                    weight *= .38 + .62 * _normal((.67 - h) / .080)
                if first_raise and large_raise and potential_shover:
                    weight = .40 + .60 * weight
                for event in post:
                    event_board = list(event[3])
                    if len(event_board) < 3 or any(c in (a, b) for c in event_board):
                        continue
                    quality = _texture([a, b], event_board)
                    if event[1] == 'raise':
                        bluff_floor = .10 + .24 * aggro + .24 * observed_bluffs
                        weight *= bluff_floor + (1 - bluff_floor) * _normal((quality - .50) / .115)
                    elif event[1] == 'call':
                        weight *= .38 + .62 * _normal((quality - .32) / .17)
                candidate.append((a, b))
                weights.append(max(.00001, weight))
                texture_scores.append(_texture([a, b], board) if board else h)
        return candidate, weights, texture_scores

    def _sample(self, hero, board, candidate, weights, samples):
        """Samples full runouts; yields opponent index and equity of each deal."""
        cdf = []
        total = 0.0
        for w in weights:
            total += w
            cdf.append(total)
        dead = set(hero + board)
        deck = [c for c in _DECK if c not in dead]
        n_to_deal = 5 - len(board)
        rng = random
        # For deterministic river spots, ranks are cached for speed.
        fixed_hero = _rank7(hero + board) if not n_to_deal else None
        values = []
        for _ in range(samples):
            idx = bisect_left(cdf, rng.random() * total)
            idx = min(len(candidate) - 1, idx)
            a, b = candidate[idx]
            if n_to_deal:
                # Sample from 50/47/etc cards, rejecting the sampled villain hand.
                # Rejection rather than rebuilding a 45-card list is much faster.
                runout = []
                while len(runout) < n_to_deal:
                    c = deck[rng.randrange(len(deck))]
                    if c != a and c != b and c not in runout:
                        runout.append(c)
                fullboard = board + runout
                hr = _rank7(hero + fullboard)
                vr = _rank7([a, b] + fullboard)
            else:
                hr = fixed_hero
                vr = _rank7([a, b] + board)
            values.append((idx, 1.0 if hr > vr else (.5 if hr == vr else 0.0)))
        return values

    @staticmethod
    def _call_chance(quality, pct, station, aggro):
        """Approx P(villain continues after a bet of pct pot)."""
        threshold = .33 + .15 * min(2.3, pct)
        # Stationary opponents call with substantially more holdings.
        threshold += .16 * (station - .5)
        call = .025 + .94 * _normal((quality - threshold) / .095)
        # Even poor hands sometimes call a tiny bet or slowplay a monster.
        return min(.99, max(.025, call))

    def _raise_candidates(self, gs):
        if not gs.can_raise or gs.raise_range is None:
            return []
        lo, hi = gs.raise_range
        ownbet = gs.bets[self.player_id]
        existing = gs.pot + gs.call_amount
        base = ownbet + gs.call_amount
        # Mix small and large bets, giving the EV engine a choice.
        options = [int(base + .37 * existing), int(base + .68 * existing),
                   int(base + 1.12 * existing), int(base + 1.8 * existing), hi]
        return sorted({min(hi, max(lo, x)) for x in options if lo <= hi})

    def _preflop(self, gs, hero, candidate, weights, stats):
        from player_action import PlayerAction
        me = self.player_id
        other = 1 - me
        bb = gs.big_blind
        call = gs.call_amount
        pot = gs.pot
        ownbet = gs.bets[me]
        oppbet = gs.bets[other]
        strength = _holdem_strength(*hero)
        loose, aggro, foldiness, shove = self._styles(stats)
        rng = random
        def raise_to(total):
            if not gs.can_raise or gs.raise_range is None:
                return PlayerAction.call(me)
            lo, hi = gs.raise_range
            return PlayerAction.raise_to(me, int(min(hi, max(lo, total))))

        # Unopened small blind / button: 25bb start makes limping useful.
        if gs.button == me and gs.current_bet <= bb and call <= bb:
            if strength >= .515 or (strength >= .465 and rng.random() < .48):
                # Open to 2.25-2.65bb; some premiums play slightly larger.
                return raise_to(round(bb * (2.35 + .25 * (strength > .65))))
            return PlayerAction.call(me)

        # Big blind vs the button's limp. Check marginal holdings for free.
        if gs.button != me and gs.current_bet <= bb and call == 0:
            if strength >= .60 or (strength >= .545 and rng.random() < .34):
                return raise_to(round(bb * 3.1))
            return PlayerAction.call(me)

        # Pot-odds-aware all-in defence, with opponent range estimate.
        effective = min(gs.stacks[me], gs.stacks[other] + max(0, oppbet - ownbet))
        future_big = call >= max(bb * 4, pot * .7) or effective <= call * 1.5
        if future_big:
            deals = self._sample(hero, [], candidate, weights, 1700)
            equity = sum(x for _, x in deals) / len(deals)
            threshold = call / max(1, pot + call)
            # A little margin for opponent range error and future play.
            if equity + .015 < threshold + (.023 if effective > call else 0):
                return PlayerAction.fold(me)
            # Re-shove value if sufficiently strong and near-committed.
            if gs.can_raise and gs.raise_range and (strength >= .67 or equity >= .67):
                if gs.stacks[me] <= bb * 15 or strength >= .76:
                    return raise_to(gs.max_raise_to)
            return PlayerAction.call(me)

        # Normal blind-defence and 3bet decisions.
        if oppbet <= bb * 3.1:
            # HU BB: 3bet a polarised range, with blocker bluffs.
            if gs.button != me and gs.can_raise and (strength >= .635 or
                (strength >= .49 and strength < .55 and rng.random() < .18 * foldiness)):
                return raise_to(round(max(oppbet * 3.35, bb * 5.6)))
            # Calling 2bb/2.5bb raises is cheap, even OOP.
            if strength >= (.392 if oppbet <= bb * 2.5 else .432):
                return PlayerAction.call(me)
            return PlayerAction.fold(me)

        # Facing 3bet / 4bet non-shove.
        if strength >= .70 and gs.can_raise and gs.raise_range:
            return raise_to(gs.max_raise_to if gs.stacks[me] <= bb * 18 else round(oppbet * 2.4))
        if strength >= .525 or (strength >= .49 and call <= pot * .33):
            return PlayerAction.call(me)
        return PlayerAction.fold(me)

    def _postflop(self, gs, hero, board, candidate, weights, qualities, stats):
        from player_action import PlayerAction
        me = self.player_id
        other = 1 - me
        pot = max(1, gs.pot)
        call = gs.call_amount
        ownbet = gs.bets[me]
        oppbet = gs.bets[other]
        loose, aggro, foldiness, shove = self._styles(stats)
        # Game-state values describe this street only.
        all_in = gs.stacks[other] == 0 or gs.stacks[me] <= call
        rounds = 2600 if (all_in or len(board) == 5) else 1900
        samples = self._sample(hero, board, candidate, weights, rounds)
        equity = sum(win for _, win in samples) / len(samples)
        # This small penalty adjusts for positional disadvantage and future bets.
        in_position = (gs.button == me)
        realize = 1.0 if all_in or len(board) == 5 else (.94 if in_position else .85)
        ev_call = (equity * realize) * pot - (1 - equity * realize) * call
        # A check is free, while a fold gives up future equity.
        if call == 0:
            baseline = max(0.0, equity * pot * realize)
            best = ('call', 0, baseline)
        elif ev_call > 0:
            best = ('call', 0, ev_call)
        else:
            best = ('fold', 0, 0.0)

        if gs.can_raise and gs.raise_range and gs.stacks[other] > 0:
            for total in self._raise_candidates(gs):
                bet_add = total - ownbet
                opp_add = max(0, total - oppbet)
                # Opponent cannot call more than chips behind.
                opp_add = min(opp_add, gs.stacks[other])
                if bet_add <= call:
                    continue
                pct = (bet_add - call) / max(1, pot + call)
                sum_call = 0.0
                win_when_called = 0.0
                faced = stats['faced_hero_raise']
                observed_fold_rate = ((stats['folded_to_hero_raise'] + 1.0) /
                                      (faced + 2.0))
                for idx, win in samples:
                    c = self._call_chance(qualities[idx], pct, foldiness, aggro)
                    # A confirmed calling station continues with almost
                    # anything; a confirmed overfolder does the reverse.
                    if faced >= 6 and observed_fold_rate < .20:
                        c = .65 + .35 * c
                    elif faced >= 6 and observed_fold_rate > .80:
                        c *= .34
                    sum_call += c
                    win_when_called += c * win
                p_call = sum_call / len(samples)
                eq_called = win_when_called / max(.001, sum_call)
                # EV relative to *this* decision; committed chips are sunk.
                ev_bet = ((1 - p_call) * pot +
                          p_call * (eq_called * (pot + opp_add) - (1 - eq_called) * bet_add))
                # A postflop raise can trigger a reraise; apply conservative
                # future-risk estimates when we're bluffing into deep stacks.
                if len(board) < 5 and not all_in:
                    ev_bet -= .055 * bet_add * (1 - eq_called) * (1.1 if not in_position else .8)
                # Large bluffs need robust reads; the smooth range prior alone
                # is not reliable enough to justify repeated huge shoves.
                if equity < .30 and pct > 1.0:
                    ev_bet -= .15 * bet_add
                if ev_bet > best[2] + (.035 * pot if best[0] == 'call' else 0):
                    best = ('raise', total, ev_bet)

        if best[0] == 'raise':
            return PlayerAction.raise_to(me, int(best[1]))
        if best[0] == 'fold':
            return PlayerAction.fold(me)
        return PlayerAction.call(me)

    def run(self, actions, game_state):
        """Decision typically in well under one second, with a bounded workload."""
        from player_action import PlayerAction
        me = self.player_id
        self._ingest(actions)
        if game_state.num_players != 2:
            # The requested competition is heads-up; legal fallback for 3+ seats.
            return PlayerAction.call(me) if game_state.call_amount == 0 else PlayerAction.fold(me)
        opp = 1 - me
        self.opponent = game_state.teams[opp]
        stats = self._get_stats(self.opponent)
        hero = self._encode(self.hand)
        board = self._encode(game_state.board)
        if game_state.call_amount == 0 and not game_state.can_raise:
            return PlayerAction.call(me)
        candidate, weights, quality = self._range(hero, board, opp, game_state, stats)
        if not board:
            return self._preflop(game_state, hero, candidate, weights, stats)
        return self._postflop(game_state, hero, board, candidate, weights, quality, stats)

    def end_game(self, actions, game_state):
        self._ingest(actions)
        if game_state.num_players != 2 or self.player_id is None:
            return
        other = 1 - self.player_id
        opponent = game_state.teams[other]
        stats = self._get_stats(opponent)
        stats['hands'] += 1
        opponent_events = [a for a in self.history if a[0] == other]
        opp_pre = [a for a in opponent_events if a[4] == 0]
        if any(a[1] == 'raise' for a in opp_pre):
            stats['pfr'] += 1
        # VPIP excludes a free BB check.
        hero_pfr = any(a[0] == self.player_id and a[1] == 'raise' and a[4] == 0 for a in self.history)
        if any(a[1] == 'raise' for a in opp_pre) or (
                any(a[1] == 'call' for a in opp_pre) and
                (game_state.button == other or hero_pfr)):
            stats['vpip'] += 1
        if any(a[1] == 'raise' and a[2] >= game_state.big_blind * 8 for a in opp_pre):
            stats['pre_shoves'] += 1
        # Reconstruct response opportunities: our last raise on that street.
        last_aggressor = None
        street = None
        for pid, kind, amt, board_at_action, street_num in self.history:
            if street_num != street:
                street = street_num
                last_aggressor = None
            if kind == 'raise':
                if pid == other:
                    stats['raises'] += 1
                last_aggressor = pid
            elif pid == other and kind in ('call', 'fold'):
                if last_aggressor == self.player_id:
                    stats['faced_hero_raise'] += 1
                    if kind == 'fold':
                        stats['folded_to_hero_raise'] += 1
                stats['calls' if kind == 'call' else 'folds'] += 1
                last_aggressor = None
        for row in opponent_events:
            if row[1] == 'call' and row[4] > 0:
                stats['checks'] += 1  # Conservative estimate: calls include checks.
        villain_hole = [card for pid, card in self.revealed if pid == other]
        if len(villain_hole) == 2 and len(self.seen_board) == 5:
            stats['showdowns'] += 1
            river_bets = [a for a in opponent_events if a[1] == 'raise' and a[4] == 3]
            if river_bets and _texture(villain_hole, self.seen_board) < .43:
                stats['bluff_showdowns'] += 1
