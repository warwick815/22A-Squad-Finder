import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import discord
from roasts import eligible, Roasts, ManualRoastView, send_roast

class ManualRoastTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_attachment_sends_and_closes_on_success_or_failure(self):
        member = SimpleNamespace(id=1, mention='<@1>')
        for fails in (False, True):
            channel = Mock()
            async def send(**kwargs):
                self.assertFalse(kwargs['file'].fp.closed)
                self.assertEqual(kwargs['file'].filename, 'corporal.png')
                self.assertEqual(kwargs['allowed_mentions'].users, [member])
                if fails:
                    raise RuntimeError('send failed')
                return 'sent'
            channel.send = AsyncMock(side_effect=send)
            if fails:
                with self.assertRaises(RuntimeError):
                    await send_roast(channel, member, discord.Embed())
            else:
                self.assertEqual(await send_roast(channel, member, discord.Embed()), 'sent')
            self.assertTrue(channel.send.call_args.kwargs['file'].fp.closed)

    async def test_picker_requires_requester_and_current_staff_permission(self):
        view = ManualRoastView(1)
        interaction = Mock()
        interaction.user = SimpleNamespace(id=1, guild_permissions=SimpleNamespace(manage_guild=True))
        self.assertTrue(await view.interaction_check(interaction))
        interaction.user.id = 2
        with self.assertRaises(ValueError):
            await view.interaction_check(interaction)
        interaction.user.id = 1
        interaction.user.guild_permissions.manage_guild = False
        with self.assertRaises(ValueError):
            await view.interaction_check(interaction)
        view.stop()

class RoastTests(unittest.TestCase):
    def test_online_voice_visibility_and_cooldown(self):
        m=SimpleNamespace(id=1, bot=False, status=discord.Status.online, voice=SimpleNamespace(channel=object()))
        channel=Mock()
        channel.permissions_for.return_value=SimpleNamespace(view_channel=True)
        self.assertTrue(eligible(m,channel,{},100000))
        self.assertFalse(eligible(m,channel,{'1':99999},100000))
        m.status=discord.Status.offline
        self.assertFalse(eligible(m,channel,{},100000))
        m.status=discord.Status.online;m.voice=None
        self.assertFalse(eligible(m,channel,{},100000))
    def test_schedule_persists_across_restart(self):
        import time
        bot=Mock();bot.store.get.return_value=None
        before=time.time();r=Roasts(bot)
        self.assertTrue(before+3600<=r.state['next']<=time.time()+10800)
        bot.store.get.return_value=bot.store.set.call_args.args[1]
        restored=Roasts(bot)
        self.assertEqual(restored.state['next'],r.state['next'])
