import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from specialities import validate,Specialities,SpecialityPanel,SelectionView,OPTIONS

class SpecialityTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_panel_and_selection_limits(self):
        self.assertTrue(SpecialityPanel().is_persistent())
        view=SelectionView()
        self.assertEqual(view.children[1].max_values,3)
        self.assertLessEqual(len(OPTIONS),25)
        validate('inf_at',['air_attack','sup_medic'])
        for p,s in [(None,['inf_at']),('inf_at',['inf_at']),('bad',[]),('inf_at',['air_attack']*2),('inf_at',list(OPTIONS)[:4])]:
            with self.assertRaises(ValueError):validate(p,s)

    async def test_large_roster_pages_and_primary_marker(self):
        bot=Mock();bot.store.get.return_value=None
        s=Specialities(bot)
        s.state['roles']={'inf_at':123}
        bot.guild.members=[SimpleNamespace(id=n,bot=False,display_name=str(n),mention=f'<@{100000000000000000+n}>',roles=[SimpleNamespace(id=123)]) for n in range(1000)]
        s.state['members']['0']={'primary':'inf_at','secondary':[]}
        pages=s.roster('inf')
        self.assertGreater(len(pages),1)
        self.assertTrue(all(len(e)<=6000 and len(e.fields)<=25 and all(len(f.value)<=1024 for f in e.fields) for e in pages))
        self.assertIn('⭐',pages[0].fields[0].value)
        s.state['roles']={k:123 for k in OPTIONS}
        combined=s.combined_embed()
        self.assertEqual(len(combined.fields),16)
        self.assertLessEqual(len(combined),6000)
        self.assertTrue(all(len(f.value)<=1024 for f in combined.fields))
        self.assertIn('more',combined.fields[0].value)

    async def test_persistence_does_not_touch_legacy_preferences(self):
        bot=Mock();bot.store.get.return_value=None
        s=Specialities(bot)
        s.state['members']['1']={'primary':'sup_medic','secondary':['inf_at'],'pending':True}
        s.save()
        key,raw=bot.store.set.call_args.args
        self.assertEqual(key,'specialities_v1')
        bot.store.get.return_value=raw
        restored=Specialities(bot)
        self.assertEqual(restored.state,s.state)
