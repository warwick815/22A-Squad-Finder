import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock,AsyncMock
from preferences import Preferences,PreferenceView,TEAMS,CLASSES,preference_embed

class PreferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_view_and_limits(self):
        v=PreferenceView()
        self.assertTrue(v.is_persistent())
        self.assertEqual(v.children[0].max_values,1)
        self.assertEqual(v.children[1].max_values,6)
        self.assertLess(len(preference_embed()),6000)
    async def test_invalid_choices_cannot_assign_roles(self):
        bot=MagicMock();bot.store.get.return_value=None
        p=Preferences(bot)
        with self.assertRaises(ValueError):
            await p.choose(MagicMock(),'team',['lonestar','valkyra'])
        with self.assertRaises(ValueError):
            await p.choose(MagicMock(),'classes',['administrator'])
    async def test_selection_only_changes_own_category(self):
        bot=MagicMock();bot.store.get.return_value=None
        p=Preferences(bot)
        roles=[SimpleNamespace(id=i) for i in range(3)]
        p.state['roles']=dict(zip(TEAMS,[0,1,2]))
        p.safe=MagicMock()
        bot.guild.fetch_roles=AsyncMock(return_value=roles)
        unrelated=SimpleNamespace(id=999)
        member=SimpleNamespace(id=123,roles=[roles[0],unrelated],remove_roles=AsyncMock(),add_roles=AsyncMock())
        bot.guild.fetch_member=AsyncMock(return_value=member)
        i=MagicMock();i.user.id=123;i.response.defer=AsyncMock();i.followup.send=AsyncMock()
        await p.choose(i,'team',['valkyra'])
        self.assertEqual(member.remove_roles.call_args.args,(roles[0],))
        self.assertEqual(member.add_roles.call_args.args,(roles[1],))
        bot.store.get.return_value=bot.store.set.call_args.args[1]
        restored=Preferences(bot)
        self.assertEqual(restored.state['members']['123']['team'],['valkyra'])
