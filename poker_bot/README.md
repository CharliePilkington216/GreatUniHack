# Poker bot hackathon

Write a bot that plays no-limit Texas hold'em. Your bot is a `Model` in
`model.py`. It is pickled and submitted, and the organisers' engine plays it
against other teams' bots.

**Join the participants' WhatsApp group** for announcements and questions: https://tr.ee/5W_MS_DJK9

## 1. Fork and set up

1. **Fork the repo.** Fork https://github.com/Manchester-AI-Society/poker_bot
   on GitHub (your own copy, under your account) and clone **your fork**. Do
   not clone the original: you would have nowhere to keep your work.
2. Create a virtual environment and install the dependencies (Python 3.10+;
   Windows, macOS and Linux all work):

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt          # Windows: .venv\Scripts\pip ...
```

Run everything with the venv's Python from the repo root: `.venv/bin/python`
(Windows: `.venv\Scripts\python`). In VS Code, select `.venv` as the
interpreter. If `venv` is missing on Ubuntu:
`sudo apt install python3-venv python3-pip`. The commands below say
`.venv/bin/python`; on Windows read it as `.venv\Scripts\python`.

## 2. Implement `model.py`

**`model.py` is the one file you must implement.** Add your own files next to
it if you need them. The template calls every hand, so fill in:

- `seed(hand, player_id)`: your two hole cards and your seat, once per hand.
  Store them.
- `run(actions, game_state)`: on each of your turns, return one
  `PlayerAction`: `fold`, `call` (also checks) or `raise_to`.
- `end_game(actions, game_state)` (optional): called after every hand. Learn
  from it, for example about opponents, using `game_state.teams`.

Rules that matter:

- Keep the model's attributes plain data (numbers, lists, dicts, numpy
  arrays, weights). No lambdas, open files, sockets or threads: the model is
  pickled. Load weights and data in `__init__`.
- Do not edit `card_utils.py`, `player_action.py`, `game_state.py` or
  `game_interface.py`. The organisers' copies are what play.
- Only use `GameStateView` names listed in [CLAUDE.md](CLAUDE.md): any other
  name raises `AttributeError`.

[CLAUDE.md](CLAUDE.md) has the full rules, the API tables and the common
mistakes. Read it before you start.

## 3. Check and measure your bot

```sh
# Is it a valid submission? (pickles, plays legally, no faults, in time)
.venv/bin/python -m pytest tests/test_model.py -q

# How strong is it? bb/100 against each dummy bot, with a 95% interval
.venv/bin/python -m evals
.venv/bin/python -m evals --opponents tight equity --deals 1000 --table
```

Beating the dummy bots shows your bot works, not that it will win the
tournament: that depends on the other teams. Results are only meaningful when
the interval does not include 0, so add `--deals` to narrow it.

## 4. Submit

Your bot is submitted as a **pickle plus the code it came from**, so the
organisers can read the code before anything runs. From the repo root:

```sh
.venv/bin/python -m submit --team myteam
```

This does `pickle.dump(Model(), ...)` into `myteam.pkl` and then checks it
the way the organisers will: it lists the files you must upload, shows
anything the code review will flag, and plays your model from a clean copy of
just those files against the dummy bots. Fix anything it reports, then upload
**every file it lists** (`myteam.pkl` and your `.py` files) in the submission
form. The form opens at 16:00 and its link appears then on the event
website (until then submissions are closed); the deadline is 18:00. Submit
again before the deadline if
you improve it: the newest upload that works is the one that plays.

What the review looks for:

- **The pickle** may only name your own modules and plain data (numbers,
  lists, dicts, sets, numpy arrays, `Card`, `PlayerAction`). A pickle that
  names anything else, such as `os.system`, is refused and never run.
- **Your `.py` files** are read for imports such as `os`, `subprocess` or
  `socket`, for `eval`/`exec`/`open`, and for reaching into the engine's
  internals (`_state`, `__globals__`, `_getframe`). A flagged file waits for
  an organiser to read it, so keep your code plain: no network, no files, no
  tricks.
- Keep your files flat next to `model.py` (no folders), named with letters,
  digits and `_`, and not like a standard library module (`random.py`).
- Put weights and data inside the model object (load them in `__init__`);
  files on disk are not available when your bot plays.

## For the organiser

Everything is under `event/` (`--root` to change it). Python 3.10+ on Windows,
macOS or Linux.

```sh
.venv/bin/python -m arena.event import DOWNLOADS   # the form's downloads
.venv/bin/python -m arena.event status             # who is ready / waiting
.venv/bin/python -m arena.event review TEAM        # findings, then the code
.venv/bin/python -m arena.event approve TEAM       # after reading it
.venv/bin/python -m arena.event run --deals 200    # every bot plays every other
.venv/bin/python -m arena.event export --out site_out --delay 120 --spacing 20 --loop 30
```

`import` reads either one folder per team or the flat folder Google Forms
makes (files named `<file> - <respondent>`, one respondent's files belong
together; a team's name is its `.pkl` name). Each upload is vetted
(`arena/vet.py`) before its code runs: a pickle naming anything but the team's
own modules and plain data is `REFUSED`; a team whose code has flagged lines
(or every team, with `--review-all`) is `NEEDS_REVIEW` until you have read it
with `review` and run `approve`; the rest are played against dummy bots and
become `READY`. A newer upload that fails never replaces one that works.

`run` plays one round: every ready team against every other, heads-up, each
pairing as duplicate deals (seats swapped), so card luck mostly cancels; the
best bb/100 is the champion. It saves every hand, can be stopped and started
again (finished pairings are skipped), and `--concurrency` sets how many
pairings play at once.

`export` writes the results site (the organiser's pages, kept outside this
repository in `site/`, plus `data/`). With
`--delay` and `--spacing` each finished pairing is shown (with a replay of its
biggest hands) some time after it ended and at least that far after the
previous one, so the site feels live but runs behind; standings are computed
from what is shown and the champion appears with the last pairing. `--loop`
keeps exporting; `--git-push` commits and pushes the folder (a git clone that
a static host serves). The Home page text is `event.json`.

Unpickling runs the team's code. Vetting keeps out the obvious attacks and
shows you the code, but it is not a sandbox: for real isolation run the
workers under `--launcher` (for example `bwrap` on Linux, or a container or
VM), on a machine you can spare.
