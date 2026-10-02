import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from rank_nicknames import sync_nickname, ranked_name


class NicknameTests(unittest.IsolatedAsyncioTestCase):
    async def test_promotions_demotion_and_user_rename(self):
        ranks = Mock()
        ranks.bot.guild = SimpleNamespace(owner_id=99, me=SimpleNamespace(top_role=10, guild_permissions=SimpleNamespace(manage_nicknames=True)))
        member = SimpleNamespace(id=1, name='Warwick', nick=None, display_name='[22A]Warwick815', top_role=1, edit=AsyncMock())
        player = {'rank': 0}
        for rank in (0, 1, 0):
            player['rank'] = rank
            await sync_nickname(ranks, member, player)
            member.nick = member.display_name = member.edit.call_args.kwargs['nick']
            self.assertEqual(member.nick, ranked_name('[22A]Warwick815', rank))
        member.edit.reset_mock()
        await sync_nickname(ranks, member, player)
        member.edit.assert_not_awaited()
        member.display_name = 'New Name [PVT]'
        await sync_nickname(ranks, member, player)
        self.assertEqual(member.edit.call_args.kwargs['nick'], 'New Name [PVT]')

    async def test_owner_skipped(self):
        ranks = Mock()
        ranks.bot.guild.owner_id = 1
        member = SimpleNamespace(id=1, name='Owner', nick=None, display_name='Owner', edit=AsyncMock())
        await sync_nickname(ranks, member, {'rank': 0})
        member.edit.assert_not_awaited()

    def test_length_and_all_ranks(self):
        for rank in range(7):
            self.assertLessEqual(len(ranked_name('A'*32, rank)), 32)
