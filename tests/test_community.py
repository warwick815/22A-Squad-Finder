import unittest
from datetime import datetime, timezone, timedelta
from progression import advance,new_player
from community import history_embed,week_window,weekly_embed,AdminView

class CommunityTests(unittest.TestCase):
    def test_history_snapshot_idempotency_and_floor(self):
        p=new_player(1,dict(wins=0,losses=0,kills=0,deaths=0),'2026-09-30T00:00:00+00:00')
        row=dict(wins=0,losses=1,kills=0,deaths=5)
        advance(p,row,'2026-09-30T01:00:00+00:00')
        advance(p,row,'2026-09-30T01:00:00+00:00')
        self.assertEqual(len(p['history']),1)
        self.assertEqual(p['history'][0]['after'],0)
        self.assertEqual(p['history'][0]['weights']['losses'],-10)
        self.assertLess(len(history_embed(p)),6000)

    def test_week_boundary(self):
        now=datetime(2026,10,5,18,tzinfo=timezone.utc)
        start,end=week_window(now)
        self.assertEqual(start.day,28)
        self.assertEqual(end.day,5)
        self.assertEqual(end-start,timedelta(days=7))

    def test_report_excludes_corrections(self):
        start=datetime(2026,9,28,tzinfo=timezone.utc); end=start+timedelta(days=7)
        p={'discord_id':1,'history':[{'at':start.isoformat(),'kind':'results','before':0,'after':60,'from':0,'to':0,'delta':dict(wins=1,losses=0,kills=0,deaths=0)}, {'at':start.isoformat(),'kind':'Adjust rating','before':60,'after':2000}]}
        e=weekly_embed([p],start,end,start)
        self.assertIn('+30.0',e.fields[2].value)
        self.assertIn('1 admin corrections',e.fields[3].value)

    def test_pagination_empty_legacy(self):
        p=new_player(1,None,None)
        self.assertIn('No recorded',history_embed(p).fields[0].name)

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_view_persistent(self):
        self.assertTrue(AdminView().is_persistent())

if __name__=='__main__': unittest.main()

class PreservationTests(unittest.TestCase):
    def test_history_survives_database_reopen(self):
        import tempfile,json
        from pathlib import Path
        from state import Store
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.sqlite3'
            store=Store(path)
            p=new_player(1,dict.fromkeys(('wins','losses','kills','deaths'),0),'2026-09-30T00:00:00+00:00')
            advance(p,dict(wins=1,losses=0,kills=2,deaths=1),'2026-09-30T01:00:00+00:00')
            import json
            store.set('progression_v1',json.dumps({'players':{'123':p}}))
            store.db.close()
            reopened=Store(path)
            restored=json.loads(reopened.get('progression_v1'))['players']['123']
            self.assertEqual(restored['history'],p['history'])
            self.assertEqual(restored['points2'],54)
            reopened.db.close()

class AccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_denied_on_button_and_modal(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from community import AdminModal
        i=SimpleNamespace(client=SimpleNamespace(validate_context=Mock()),user=SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=False)))
        with self.assertRaises(ValueError):
            await AdminView().interaction_check(i)
        with self.assertRaises(ValueError):
            await AdminModal('Pause').on_submit(i)

    async def test_existing_board_edited_not_sent(self):
        from unittest.mock import Mock,AsyncMock
        from types import SimpleNamespace
        from community import upsert
        import discord
        message=SimpleNamespace(id=123,edit=AsyncMock())
        channel=SimpleNamespace(fetch_message=AsyncMock(return_value=message),send=AsyncMock())
        store=SimpleNamespace(get=Mock(return_value='123'),set=Mock())
        ranks=SimpleNamespace(bot=SimpleNamespace(store=store))
        await upsert(ranks,channel,'board',discord.Embed(title='test'))
        message.edit.assert_awaited_once()
        channel.send.assert_not_awaited()
