"""/merits: a member's Merits balance, active booster and the Armoury, in Discord."""
from datetime import datetime

import discord
from discord import app_commands

import merits


def armoury_embed(state, uid, feed):
    v = merits.view(state, uid, feed)
    embed = discord.Embed(title='🎖️ The Armoury', colour=0xA6E35A,
                          description=f"**{v['balance']:,} Merits** · earned today {v['earned_today']}/{v['daily_cap']} · season {v['season']}")
    if v['booster']:
        until = int(v['booster']['until'])
        embed.add_field(name='Active', value=f"⚡ {v['booster']['name']} until <t:{until}:t> (<t:{until}:R>)", inline=False)
    if v['flak']:
        embed.add_field(name='Flak jacket', value=f"🛡 Next {v['flak']} deaths cost no ELO", inline=False)
    embed.add_field(name='Shop', value='\n'.join(f"**{i['name']}** · {i['cost']} Merits\n{i['detail']}" for i in v['items']), inline=False)
    embed.add_field(name='Earn Merits', value='\n'.join(f"{k}: **+{p}**" for k, p in v['earn']), inline=False)
    embed.set_footer(text=f"One Armoury item a day{' · used today: ' + v['used_today'] if v['used_today'] else ''} · Merits reset each season")
    return embed, v


class ArmouryView(discord.ui.View):
    def __init__(self, owner, v):
        super().__init__(timeout=180)
        self.owner = owner
        select = discord.ui.Select(placeholder='Use an item (one a day)…', min_values=1, max_values=1,
                                   disabled=bool(v['used_today']) or not v['linked'],
                                   options=[discord.SelectOption(label=f"{i['name']} · {i['cost']} Merits", value=i['id'],
                                                                 description=i['detail'][:100]) for i in v['items']])
        select.callback = self.choose
        self.add_item(select)

    async def interaction_check(self, interaction):
        interaction.client.validate_context(interaction)
        if interaction.user.id != self.owner:
            raise ValueError('Open your own Armoury with /merits.')
        return True

    async def choose(self, interaction):
        item = merits.ITEMS[interaction.data['values'][0]]
        await interaction.response.send_message(
            f"Use the **{item['name']}** for **{item['cost']} Merits**? {item['detail']} This is your one Armoury item for today.",
            view=ConfirmView(self.owner, interaction.data['values'][0]), ephemeral=True)

    async def on_error(self, interaction, error, item):
        from bot import handle_error
        await handle_error(interaction, error)


class ConfirmView(discord.ui.View):
    def __init__(self, owner, item_id):
        super().__init__(timeout=60)
        self.owner, self.item_id = owner, item_id

    async def interaction_check(self, interaction):
        interaction.client.validate_context(interaction)
        return interaction.user.id == self.owner

    @discord.ui.button(label='Use it', emoji='⚡', style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        ranks = interaction.client.progression
        feed = getattr(getattr(interaction.client, 'kill_feed', None), 'state', None)
        async with ranks.lock:
            message = merits.buy(ranks.state, interaction.user.id, self.item_id, feed)
            ranks.save()
        self.stop()
        await interaction.response.edit_message(content=f"✅ {message}", view=None)
        from website_merits import announce
        await announce(interaction.client, interaction.user, self.item_id, message)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        self.stop()
        await interaction.response.edit_message(content='Nothing spent.', view=None)

    async def on_error(self, interaction, error, item):
        from bot import handle_error
        await handle_error(interaction, error)


@app_commands.command(name='merits', description='Your Merits, active booster and the Armoury')
@app_commands.guild_only()
async def merits_command(interaction: discord.Interaction):
    interaction.client.validate_context(interaction)
    ranks = getattr(interaction.client, 'progression', None)
    if ranks is None:
        raise ValueError('Rank progression is not set up.')
    feed = getattr(getattr(interaction.client, 'kill_feed', None), 'state', None)
    embed, v = armoury_embed(ranks.state, interaction.user.id, feed)
    await interaction.response.send_message(embed=embed, view=ArmouryView(interaction.user.id, v), ephemeral=True)


COMMANDS = (merits_command,)
