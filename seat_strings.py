"""Defines long strings used in discord communications with users."""
import typing

DEFAULT_OPTIONS = {
    'win_garnets': 10,
    'x_garnets': -10,
    'start_garnets': 20,
    'middle_garnets': 6,
    'garnet_reveal_bribe': 1,
    'reveal_longest_streak': True,
}


WIKIPEDIA_URL = (
    'https://en.wikipedia.org/wiki/The_Genius:_Rule_Breaker'
    '#Episode_2:_Seat_Exchange_(12_Contestants)')

YOUTUBE_URL = 'https://youtu.be/jpwIgWPfNvc'

REDDIT_URL = ('https://www.reddit.com/r/TheGenius/comments/70jog1/'
              'links_to_all_subbed_episodes_of_the_genius_s14/')

HELP_HELP = (
    'Type `!help` to see this help text.\n'
    'Type `!rules` for an overview and explanation on how the '
    'game works.\n'
    'Type `!commands` for a list of the commands available '
    'through direct messages.\n'
    'Add a command as parameter to `!help` see its help text. '
    'E.g. `!help help`.'
)


RULES_INDEX = (
    "The rules pages are divided into a number of sections.\n"
    "To view a specific section type `!rules section`, e.g `!rules index` "
    "to view this text.\n"
    "The sections are as follows:\n"
    "**Index** is this index.\n"
    "**Overview** is a basic overview of the rules.\n"
    "**Gameplay** describes typical gameplay.\n"
    "**Garnets** describes garnets, their usage and worth.\n"
    "**Streak** details rules and examples for streak calculations.\n"
    "**Bots** describes the purpose of bots and how they work.\n"
    "**Genius** has links to the game show The Genius, it's rules, and how "
    "their rules differ from this implementation and why.\n"
    "Do also check out the `!help` for different commands for more "
    "detailed explanations on specific commands."
)

RULES_OVERVIEW = (
    'This game is based on a game from the korean reality/game show '
    'The Genius.\n'
    'Each player is imagined to be sitting in a circle, on seats named '
    'from A, B, C, and so on.\n'
    'Each seat is adjacent to two other seats, wrapping around at the '
    'beginning and end.\n'
    'Every player is also assigned a secret number, from 0 up to the number '
    'of players-1.\n'
    'The game ends when a specific amount of players, depending on the total '
    'number of players, is seated such that their secret numbers are in '
    'increasing or decreasing order. In game parlance this is called a '
    '"Streak"\n'
    'Players start with a number of so-called "garnets", which is the '
    'currency as well as the ultimate objective, where the players with '
    'the most garnets win.\n'
    'Being part of the streak that finishes the game will handsomely '
    'reward you with garnets.\n'
    'There is also one number assigned to be **X**, which changes each '
    'round. X cannot form any streaks, and if the game ends while '
    'you\'re X you will lose garnets.'
    'Once each round you may swap seats with another player, this is made '
    'by sending them a "proposal", which they have to accept.\n'
    'See the sections listed under `!rules index` for more detailed rules.'
    )

RULES_GAMEPLAY = (
    "Much of the gameplay will take place in direct messages, where you "
    "DM other players, bribe or swap info with them to figure out where "
    "the numbers are, and then find players holding adjacent numbers to "
    "formulate a plan for forming a streak.\n"
    "This means that you in many cases do not need to be a singular "
    "mastermind, and you can win even as a newbie by cooperating with "
    "your neighbouring numbers.\n"
    "Do watch out for players trying to deceive you, or giving you bad "
    "information though! There are no rules against this, other than if you "
    "are completely untrustworthy and do not follow up on your promises "
    "you will likely not be trusted in future games and lose in the long "
    "run.\n"
    "At the beginning of each round the longest streak will be announced, "
    "this can be very useful to suss out liars, as well as figure out some "
    "extra numbers from people unwilling to tell you.\n"
    "During the rounds there is only one real game action, which is "
    "proposing swaps with other players, and accepting swaps, but this "
    "brings out lots of depth where you can swap seats to create streaks, "
    "break others streaks, make others streaks too long, or trying to "
    "prolong the game if you're X.\n"
    "In many cases your optimal swapping target may not want to leave their "
    "chair, but if you bribe them with enough garnets maybe they will change "
    "their mind!\n"
    "You can `!donate` garnets to other players to make them swap with "
    "other people, give info, or other things, but this is not binding "
    "and they *can* break any such arrangements. Do not let that overly "
    "hinder your creativity though!"
)

RULES_STREAK = (
    "Achieving a streak is the main way to win the game, as it's the main "
    "source of garnets, and the creation of one is also what ends the game.\n"
    "To form a streak, players holding consecutive numbers must sit in order "
    "in neighbouring chairs. No other numbers, nor X, may be in the way "
    "or the streak is broken.\n"
    "The length required to form a winning streak depends on the number of "
    "players, but there may always only be *one* instance of it (i.e. if "
    "there are two different streaks of 5 and 5 is needed, the game does not "
    "end).\n"

    "The winning streak length is not the minimum streak length either, and "
    "longer streaks will *not* terminate the game and award garnets either.\n"

    "X cannot be part of a streak, nor the seat with X, and when checking "
    "if numbers are adjacent the number that is X is skipped. Such that "
    "2 and 4 can form a streak when 3 is X.\n"
    "More details on X can be found under `!rules x`.\n"
    "Streaks can be increasing or decreasing, and can wrap around from "
    "the highest to the lowest chair.\n"
    "We finish with a few examples, we list the numbers in seat order.\n"
    "`7, 1, 2, 3, 4, 5, 8, 6` x=7 -> streak of 5\n"
    "`1, 2, 4, 3, 5` x=3 -> streak of 3 (5, 1, 2)\n"
    "`1, 3, 4, 5, 2` x=2 -> streak of 4 (1, 3, 4, 5)\n"
    "`3, 2, 1, 4, 5` x=4 -> streak of 4 (5, 3, 2, 1)\n"
    "`3, 2, 1, 4, 5, 6, 7` x=4 -> two streaks of 3 (3, 2, 1) and (5, 6, 7)"
)

RULES_GARNETS = (
    "Each player starts the game with {start_garnets} garnets, which "
    "is the currency as well as the ultimate objective of the game.\n"
    "These should be used as bribes during the course of the game when "
    "you need to convince an unwilling player (or bot) to move, or in "
    "whatever other situation you may encounter.\n"
    "Try to use them sparingly though, as they have a big impact on the "
    "final scoring!\n"
    "The players part of a winning streak will gain {win_garnets} garnets, "
    "and the player in the middle of the streak will gain an additional "
    "{middle_garnets} garnets (if the streak length is even, the middle two "
    "will divide those among them, rounded down).\n"
    "The player holding the number assigned X in the final round will lose "
    "{x_garnets} garnets.\n"
    "All these numbers can be changed before the start of the game, but "
    "these are the default numbers."
    "At a later time a leaderboard may be implemented, where players "
    "will be scored according to the average number of garnets they score "
    "in a game. You should therefore aim not to precisely beat your "
    "opponents with a single garnet, nor donate all your garnets to your "
    "best buddy to make him win a single round. Strive instead for playing "
    "what would give you the most garnets in the long run."
    "".format(
        start_garnets=DEFAULT_OPTIONS['start_garnets'],
        win_garnets=DEFAULT_OPTIONS['win_garnets'],
        middle_garnets=DEFAULT_OPTIONS['middle_garnets'],
        x_garnets=-DEFAULT_OPTIONS['x_garnets'],
    )
)


RULES_X = (
    "Depending on the number of players and settings, there may be numbers "
    "(though usually one) designated to be **X**.\n"
    "X is bad, you don't want to be X.\n"
    "By default number 0 is designated as X in the first round, and it "
    "increases each round.\n"
    "The player holding a number currently designated as X cannot form any "
    "streak, and if the game ends while they're X they will lose garnets, "
    "by default {}.\n"
    "X has some special properties when calculating streaks:\n"
    "When calculating which numbers are adjacent and can form a streak, the "
    "number[s] that are X are skipped. So if the number 3 is X, 1-2-4-5 is "
    "a streak of 4.\n"
    "Do note though that the seat with X in it is not skipped, so if the "
    "seating is 1-2-X-4-5 that is two streaks of 2.\n"
    "So as X you desperately do not want the round to end, and should try to "
    "seat yourself and others (with bribes) such that the round does not end."
)

RULES_SHOW = (
    "The rules for the Genius version can be found at <{wikipedia_url}>\n"
    "The first season is on youtube at {youtube_url} and subsequencent "
    "seasons can be found at <{reddit_url}>.\n"
    "This game is played in season 2 episode 4, but the second season spoils "
    "the results from season 1, so I recommend starting from the beginning.\n"
    "It is a very good show!!\n"
    "This implementation has a couple differences from the show.\n"
    "Biggest difference is how numbering and X is handled. In the show "
    "players assigned numbers increment each round, the player that was "
    "11 becomes X, and X becomes 1.\n"
    "In my version a player's number never changes, and instead which number "
    "that is X changes. I decided to do it this way as it seemed very "
    "confusing during the show what numbers people had and when, and their "
    "notes became incredibly messy. In exchange the rules for X, and "
    "especially which numbers are adjacent when, is more complicated.\n"
    "You can read more about how X works under `!rules X`.\n"
    "This being made to be playable repeatedly, as well as not having any "
    "tokens of life or elimination candidates, I've changed it to be "
    "primarily about garnets. You can read more about that system under "
    "`!rules garnets`.\n"
    "I have also, quite obviously, had to adapt the game to work for "
    "different amounts of people. Currently the default algorithm is the "
    "required streak length being (player_count-1)/2 rounded down above "
    "player counts of 8. With lower counts having numbers I've tried to "
    "figure out or playtested.\n"
    "There also needs to be at least 6 players to have an assigned X, "
    "and there is support for more than one X but I have yet to decide "
    "at which player counts that should start.\n"
    "Another difference is the addition of bots, you can read more about "
    "those under `!rules bots`.\n".format(
        wikipedia_url=WIKIPEDIA_URL,
        youtube_url=YOUTUBE_URL,
        reddit_url=REDDIT_URL)
)

RULES_BOTS = (
    "To make the game playable with fewer human players, I've added a system "
    "with simple bots that players can jockey over controlling.\n"
    "To add a bot to the game you use the `!addbot` command, and to remove "
    "a bot you use `!removebot`.\n"
    "In respect to the basic rules of the game, bots are just like normal "
    "players. They have a seat, a secret number, can be X, and can form "
    "streaks.\n"
    "Their discord gameplaye differs significantly though, and their "
    "behaivour is not fully decided yet and may very well change going "
    "forward.\n"
    "In their current implementation you can bribe a bot "
    "{} garnets to have them DM you their secret number, "
    'you can propose swaps with them, and you can arrange so called "bot '
    'swaps".\n'
    "Proposing a seat swap with a bot is done just like normal with "
    "`!propose`, and if nobody else proposes a swap with them they will "
    "always accept. If several people propose a swap the bot will accept "
    "the proposal with the highest garnet bribe, and if several proposals "
    "are tied the bot will choose among them randomly.\n"
    "Botswaps are swaps between two bots, sponsored by a human. Without "
    "these it was a big ordeal to make two bots switch places, so this "
    "was added as a separate command after testing.\n"
    "These can also be used to bribe a bot not to swap.\n"
    "Details on how botswaps work is found under `!help botswap`.\n"
    "".format(DEFAULT_OPTIONS['garnet_reveal_bribe'])
)

RULES_DICT: typing.Dict[str, str] = {
    'index': RULES_INDEX,
    'overview': RULES_OVERVIEW,
    'gameplay': RULES_GAMEPLAY,
    'garnets': RULES_GARNETS,
    'streak': RULES_STREAK,
    'x': RULES_X,
    'bots': RULES_BOTS,
    'genius': RULES_SHOW,
}
