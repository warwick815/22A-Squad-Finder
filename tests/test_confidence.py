import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import community_hq


def bot_with(player, rounds):
    state = {'season': 1, 'players': {'steam1': player}, 'fantasy': {'rounds': rounds}}
    progression = SimpleNamespace(state=state, find=lambda uid: ('steam1', player) if uid == 7 else None)
    return SimpleNamespace(progression=progression)


class ConfidenceTests(unittest.TestCase):
    def test_fantasy_tracking_notes_do_not_mark_standings_recovering(self):
        now = 1_800_000_000
        stamp = datetime.fromtimestamp(now - 60, timezone.utc).isoformat()
        player = {'discord_id': 7, 'active': True, 'updated': stamp}
        snap = {'at': now - 60, 'source': 'feed', 'values': {}}
        late_round = {'season': 1, 'status': 'live', 'start': now - 3600, 'entries': {'9': {'players': ['7']}},
                      'track': {'7': {'banked': 0, 'start': snap, 'last': snap, 'final': None, 'late': True, 'notes': ['Tracking restarted']}}}
        result = community_hq.confidence(bot_with(player, {'r': late_round}), '7', now)
        self.assertEqual(result['status'], 'Verified')

    def test_old_snapshot_is_delayed(self):
        now = 1_800_000_000
        stamp = datetime.fromtimestamp(now - 7200, timezone.utc).isoformat()
        player = {'discord_id': 7, 'active': True, 'updated': stamp}
        self.assertEqual(community_hq.confidence(bot_with(player, {}), '7', now)['status'], 'Delayed')


if __name__ == '__main__':
    unittest.main()
