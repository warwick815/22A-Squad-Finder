"""Armoury patch shop: morale patches members buy with Merits for their locker.

Bought patches are kept for good (Merits reset each season, patches do not) and can be
displayed on the profile like patches earned in operations. Buying a patch does not use
the one-booster-a-day allowance. The 22A Originals patch cannot be bought: it belongs
to members with the 22A role in Discord, and goes if the role is removed.
"""
import os
import time

# Price by rarity.
PRICES = {'common': 20, 'rare': 40, 'legendary': 75}
LEGENDARY = {'01-old-guard', '02-silent-watch', '05-first-in', '32-no-one-left', '33-brothers-in-mud',
             '46-guardian', '48-iron-will', '49-against-odds'}
RARE = {'03-union-jack', '06-last-out', '10-dangerous-vintage', '11-field-medic', '13-armoured-attitude',
        '14-steel-cavalry', '16-rotor-head', '17-long-game', '26-boom-delivery', '27-overwatch', '28-night-shift',
        '41-st-george', '42-saltire', '43-welsh-dragon', '44-irish-tricolour', '45-celtic-sentinel', '47-steady-faith'}
ORIGINALS = '50-22a-originals'
# Display names, as printed on each patch (some differ from the file names).
NAMES = {'08-hurry-up-wait': 'Hurry Up & Wait', '15-low-and-fast': 'Low & Fast', '09-map-upside-down': 'Tactically Lost', '11-field-medic': 'Patch You Up',
         '17-long-game': 'The Long Game', '20-check-check': 'Radio Check', '24-build-it': 'Build It Hold It',
         '25-eod-coffee': 'Keep Calm', '26-boom-delivery': 'Special Delivery', '29-no-sleep': 'Sleep Optional',
         '30-friendly-fire': 'Check Your Fire', '32-no-one-left': 'No One Left', '33-brothers-in-mud': 'Brothers in Mud',
         '34-grumpy-effective': 'Grumpy but Effective', '36-not-retired': 'Still in the Fight',
         '39-biscuit-reserve': 'Emergency Rations', '41-st-george': 'St George', '49-against-odds': 'Against the Odds',
         '50-22a-originals': '22A Originals'}
IDS = ('01-old-guard', '02-silent-watch', '03-union-jack', '04-british-grit', '05-first-in', '06-last-out',
       '07-tea-before-chaos', '08-hurry-up-wait', '09-map-upside-down', '10-dangerous-vintage', '11-field-medic',
       '12-dustoff', '13-armoured-attitude', '14-steel-cavalry', '15-low-and-fast', '16-rotor-head', '17-long-game',
       '18-eyes-on', '19-wire-whisperer', '20-check-check', '21-heavy-lifter', '22-supply-line', '23-dig-in',
       '24-build-it', '25-eod-coffee', '26-boom-delivery', '27-overwatch', '28-night-shift', '29-no-sleep',
       '30-friendly-fire', '31-squad-anchor', '32-no-one-left', '33-brothers-in-mud', '34-grumpy-effective',
       '35-knees-optional', '36-not-retired', '37-rain-certified', '38-full-english', '39-biscuit-reserve',
       '40-morale-officer', '41-st-george', '42-saltire', '43-welsh-dragon', '44-irish-tricolour',
       '45-celtic-sentinel', '46-guardian', '47-steady-faith', '48-iron-will', '49-against-odds', ORIGINALS)


def name(pid):
    return NAMES.get(pid) or pid.split('-', 1)[1].replace('-', ' ').title()


def tier(pid):
    return 'originals' if pid == ORIGINALS else 'legendary' if pid in LEGENDARY else 'rare' if pid in RARE else 'common'


CATALOGUE = [{'id': pid, 'name': name(pid), 'tier': tier(pid), 'cost': PRICES.get(tier(pid))} for pid in IDS]
BY_ID = {p['id']: p for p in CATALOGUE}


def originals_role(guild):
    """The Discord role whose members own the 22A Originals patch (ORIGINALS_ROLE_ID, else the role named 22A)."""
    raw = os.getenv('ORIGINALS_ROLE_ID', '').strip()
    if raw.isdecimal() and guild is not None:
        return guild.get_role(int(raw))
    roles = getattr(guild, 'roles', None)
    if not isinstance(roles, (list, tuple)):
        return None
    return next((r for r in roles if str(r.name).strip().casefold() == '22a'), None)


def has_originals_role(member):
    role = originals_role(getattr(member, 'guild', None))
    return bool(role and any(r.id == role.id for r in getattr(member, 'roles', [])))


def sync_originals(state, guild):
    """Give the 22A Originals patch to everyone with the role, and take it from anyone without it."""
    from community_hq import locker, state as hq
    role = originals_role(guild)
    if role is None:
        return
    holders = {str(m.id) for m in role.members}
    for uid in holders:
        box = locker(state, uid)
        box['earned'].setdefault(ORIGINALS, {'role': True, 'at': time.time()})
    for uid, box in hq(state)['lockers'].items():
        if uid not in holders and ORIGINALS in box.get('earned', {}):
            box['earned'].pop(ORIGINALS)
            box['display'] = [p for p in box.get('display', []) if p != ORIGINALS]


def buy(state, uid, pid, now=None):
    """Spend Merits on a patch for the member's locker. Returns a message."""
    import merits
    from community_hq import locker
    now = time.time() if now is None else now
    patch = BY_ID.get(pid)
    if not patch:
        raise ValueError('Choose a patch from the Armoury.')
    if pid == ORIGINALS:
        raise ValueError('The 22A Originals patch cannot be bought: it belongs to members with the 22A role.')
    if not any(str(p['discord_id']) == str(uid) for p in state['players'].values()):
        raise ValueError('Link your Steam account first.')
    box = locker(state, uid)
    if pid in box['earned']:
        raise ValueError(f"You already own the {patch['name']} patch.")
    entry = merits.member(state, uid)
    if entry['balance'] < patch['cost']:
        raise ValueError(f"You need {patch['cost']} Merits for the {patch['name']} patch; you have {entry['balance']}.")
    entry['balance'] -= patch['cost']
    entry['log'].append({'at': now, 'amount': -patch['cost'], 'reason': f"{patch['name']} patch"})
    del entry['log'][:-merits.LOG_KEEP]
    box['earned'][pid] = {'bought': now, 'cost': patch['cost'], 'season': state.get('season', 1)}
    if len(box['display']) < 3:
        box['display'].append(pid)  # Show it straight away if there is a free slot.
    return f"{patch['name']} patch added to your locker" + (' and displayed on your profile.' if pid in box['display'] else '. Choose it in your Locker to display it.')


def view(state, uid, member=None):
    """The patch shop for one member: every patch with price and whether they own it."""
    from community_hq import locker_view
    owned = locker_view(state, uid)['earned'] if uid is not None else {}
    eligible = has_originals_role(member) if member is not None else False
    return [{**p, 'owned': p['id'] in owned, 'eligible': p['id'] != ORIGINALS or eligible} for p in CATALOGUE]
