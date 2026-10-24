import unittest
from datetime import datetime, timezone

import merits
from progression import advance

T = datetime(2026, 10, 24, 12, tzinfo=timezone.utc).timestamp()
ME, MATE, PAL = '76561198000000001', '76561198000000002', '76561198000000003'


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def state():
    players = {s: {'discord_id': i, 'rank': 0, 'points2': 0, 'active': True, 'hold': None, 'pending': None, 'history': []}
               for i, s in enumerate((ME, MATE, PAL), 1)}
    return {'season': 2, 'players': players}


def result(player, at, wins=0, losses=0, kills=0, deaths=0, frm=0, to=0):
    player['history'].append({'at': iso(at), 'kind': 'results', 'delta': {'wins': wins, 'losses': losses, 'kills': kills, 'deaths': deaths},
                              'from': frm, 'to': to})


class EarningTests(unittest.TestCase):
    def test_first_match_kills_and_promotion_once_with_no_back_pay(self):
        s = state()
        me = s['players'][ME]
        result(me, T - 3600, wins=1, kills=100)  # Before Merits started: never paid.
        merits.update(s)
        self.assertEqual(merits.member(s, 1)['balance'], 0)
        result(me, T + 60, wins=1, kills=30)
        result(me, T + 400, losses=1, kills=30, frm=0, to=1)
        merits.update(s)
        self.assertEqual(merits.member(s, 1)['balance'], 2 + 2 + 5)  # First match, 60 kills = 2, promotion.
        merits.update(s)
        self.assertEqual(merits.member(s, 1)['balance'], 9)  # Nothing twice.

    def test_kill_merits_and_the_daily_cap(self):
        s = state()
        merits.update(s)
        result(s['players'][ME], T + 60, wins=1, kills=500)
        merits.update(s)
        self.assertEqual(merits.member(s, 1)['balance'], 2 + 4)  # Kill Merits stop at 4 a day.
        for i in range(10):
            merits.credit(s, 1, 5, 'test', T + 100 + i)
        self.assertEqual(merits.member(s, 1)['days'][merits.day(T)]['earned'], merits.DAILY_CAP)

    def test_squads_bounties_operations_and_fantasy(self):
        s = state()
        merits.update(s, {'sessions': [], 'bounties': []})
        start = merits.book(s)['feed_from']
        feed = {'sessions': [{'server': 'uk2', 'start': start, 'end': start + 900, 'members': [{'steam': ME}, {'steam': MATE}, {'steam': PAL}]}],
                'bounties': [{'hour': 1, 'target': 'x', 'name': 'X', 'claimed': MATE, 'claimed_at': iso(start + 500)}]}
        s['community_hq'] = {'operations': {'o': {'id': 'o', 'title': 'Shock Troop', 'status': 'completed', 'completed': start + 10,
                                                  'members': {'1': {'total': 5}, '3': {'total': 0}}}}}
        s['fantasy'] = {'rounds': {'r': {'id': 'r', 'season': 2, 'status': 'completed', 'end': start + 20,
                                         'results': {'1': 50, '2': 50, '3': 10}}}}
        merits.update(s, feed)
        merits.update(s, feed)
        bal = {uid: merits.member(s, uid)['balance'] for uid in (1, 2, 3)}
        self.assertEqual(bal, {1: 3 + 10 + 5, 2: 3 + 5 + 5, 3: 3 + 3})  # Equal Fantasy scores share 1st.

    def test_new_season_starts_from_zero(self):
        s = state()
        merits.credit(s, 1, 10, 'x', T)
        s['season'] = 3
        self.assertEqual(merits.member(s, 1)['balance'], 0)


class HoursTests(unittest.TestCase):
    def test_two_merits_per_hour_with_part_hours_carried_and_no_back_pay(self):
        s = state()
        merits.update(s, rows={ME: {'hoursPlayed': 120.0}})  # Baseline only.
        self.assertEqual(merits.member(s, 1)['balance'], 0)
        merits.update(s, rows={ME: {'hoursPlayed': 120.6}})
        self.assertEqual(merits.member(s, 1)['balance'], 0)
        merits.update(s, rows={ME: {'hoursPlayed': 122.1}})  # 2.1 hours since the baseline.
        self.assertEqual(merits.member(s, 1)['balance'], 4)
        merits.update(s, rows={ME: {'hoursPlayed': 122.95}})  # 0.1 + 0.85: still under an hour.
        self.assertEqual(merits.member(s, 1)['balance'], 4)
        merits.update(s, rows={ME: {'hoursPlayed': 123.1}})
        self.assertEqual(merits.member(s, 1)['balance'], 6)

    def test_odd_readings_restart_without_paying(self):
        s = state()
        merits.update(s, rows={ME: {'hoursPlayed': 50}})
        merits.update(s, rows={ME: {'hoursPlayed': 10}})  # Went down: restart.
        merits.update(s, rows={ME: {'hoursPlayed': 500}})  # Impossible jump: restart.
        merits.update(s, rows={ME: {'hoursPlayed': 'x'}})
        self.assertEqual(merits.member(s, 1)['balance'], 0)
        merits.update(s, rows={ME: {'hoursPlayed': 501}})
        self.assertEqual(merits.member(s, 1)['balance'], 2)


class ArmouryTests(unittest.TestCase):
    def setUp(self):
        self.s = state()
        merits.credit(self.s, 1, 30, 'x', T - 86400)
        merits.credit(self.s, 1, 30, 'x', T - 2 * 86400)

    def test_one_item_a_day_and_balance_checks(self):
        merits.buy(self.s, 1, 'boost15', now=T)
        self.assertEqual(merits.member(self.s, 1)['balance'], 45)
        with self.assertRaisesRegex(ValueError, 'already used'):
            merits.buy(self.s, 1, 'flak', now=T + 60)
        merits.buy(self.s, 1, 'flak', now=T + 86400)  # Next day is fine.
        with self.assertRaisesRegex(ValueError, 'need 30'):
            merits.buy(self.s, 2, 'boost2', now=T)

    def test_booster_multiplies_gains_only_inside_its_window(self):
        merits.buy(self.s, 1, 'boost2', now=T)
        me = self.s['players'][ME]
        me.update(baseline={'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 0}, updated=iso(T - 60))
        advance(me, {'wins': 0, 'losses': 0, 'kills': 10, 'deaths': 5}, iso(T + 600))
        self.assertEqual(me['points2'], 2 * (10 * 5 * 2) - 2 * 15)  # Kills doubled, deaths not.
        before = me['points2']
        advance(me, {'wins': 0, 'losses': 0, 'kills': 20, 'deaths': 5}, iso(T + 3600))  # After 30 minutes.
        self.assertEqual(me['points2'], before + 2 * 50)

    def test_flak_jacket_absorbs_deaths(self):
        merits.buy(self.s, 1, 'flak', now=T)
        me = self.s['players'][ME]
        me.update(baseline={'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 0}, updated=iso(T - 60), points2=200)
        advance(me, {'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 6}, iso(T + 60))
        self.assertEqual((me['points2'], me['flak']), (200, 4))
        advance(me, {'wins': 0, 'losses': 0, 'kills': 0, 'deaths': 12}, iso(T + 120))
        self.assertEqual(me['points2'], 200 - 2 * 3 * 2)
        self.assertNotIn('flak', me)

    def test_squad_booster_needs_a_live_session_and_covers_the_squad(self):
        merits.credit(self.s, 1, 30, 'x', T - 3 * 86400)
        with self.assertRaisesRegex(ValueError, 'squad session'):
            merits.buy(self.s, 1, 'squad', feed={'open': {}}, now=T)
        feed = {'open': {'uk2': {'last': T - 60, 'members': {ME: {}, MATE: {}, PAL: {}}}}}
        self.s['players'][PAL]['booster'] = {'item': 'boost2', 'multiplier': 2.0, 'from': T - 60, 'until': T + 600}
        msg = merits.buy(self.s, 1, 'squad', feed=feed, now=T)
        self.assertIn('2 members', msg)
        self.assertEqual(self.s['players'][MATE]['booster']['multiplier'], 1.25)
        self.assertEqual(self.s['players'][PAL]['booster']['multiplier'], 2.0)  # Their stronger booster stays.

    def test_paused_members_and_unknown_items_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'Choose an item'):
            merits.buy(self.s, 1, 'nuke', now=T)
        self.s['players'][ME]['active'] = False
        with self.assertRaisesRegex(ValueError, 'paused'):
            merits.buy(self.s, 1, 'boost15', now=T)


if __name__ == '__main__':
    unittest.main()
