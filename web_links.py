"""Website link buttons derived from the configured public origin."""
import os
from urllib.parse import urlsplit
import discord


def web_button(section, row=None):
    origin=os.getenv('STEAM_LINK_BASE_URL','').strip().rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        return None
    return discord.ui.Button(label='Web View',style=discord.ButtonStyle.link,url=origin+'/#'+section,row=row)


def web_view(section):
    view=discord.ui.View(timeout=None)
    button=web_button(section)
    if button:view.add_item(button)
    return view


def components_changed(message,view):
    return [c.to_dict() for c in getattr(message,'components',[])]!=view.to_components()
