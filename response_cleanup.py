"""Best-effort deletion of private replies while interaction tokens remain valid."""
import asyncio
import discord

PENDING=set()

def later(delete, seconds=180):
    async def run():
        await asyncio.sleep(seconds)
        try:
            await delete()
        except discord.HTTPException:
            pass
    task=asyncio.create_task(run())
    PENDING.add(task)
    task.add_done_callback(PENDING.discard)


async def clean_followup(interaction, *args, **kwargs):
    message=await interaction.followup.send(*args, wait=True, **kwargs)
    if kwargs.get('ephemeral'):
        later(message.delete)
    return message
