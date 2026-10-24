"""Armoury patch shop: morale patches members buy with Merits for their locker.

Bought patches are kept for good (Merits reset each season, patches do not) and can be
displayed on the profile like patches earned in operations. Buying a patch does not use
the one-booster-a-day allowance. Role patches (22A Originals, 22B Prospects) cannot be
bought: each belongs to members with that role in Discord, and goes if the role is removed.
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
PROSPECTS = '51-22b-prospects'
# Role patches: patch id -> (role name to match, Railway variable to set a role ID instead).
ROLE_PATCHES = {ORIGINALS: ('22A', 'ORIGINALS_ROLE_ID'), PROSPECTS: ('22B', 'PROSPECTS_ROLE_ID')}
# Display names, as printed on each patch (some differ from the file names).
NAMES = {'08-hurry-up-wait': 'Hurry Up & Wait', '15-low-and-fast': 'Low & Fast', '09-map-upside-down': 'Tactically Lost', '11-field-medic': 'Patch You Up',
         '17-long-game': 'The Long Game', '20-check-check': 'Radio Check', '24-build-it': 'Build It Hold It',
         '25-eod-coffee': 'Keep Calm', '26-boom-delivery': 'Special Delivery', '29-no-sleep': 'Sleep Optional',
         '30-friendly-fire': 'Check Your Fire', '32-no-one-left': 'No One Left', '33-brothers-in-mud': 'Brothers in Mud',
         '34-grumpy-effective': 'Grumpy but Effective', '36-not-retired': 'Still in the Fight',
         '39-biscuit-reserve': 'Emergency Rations', '41-st-george': 'St George', '49-against-odds': 'Against the Odds',
         '50-22a-originals': '22A Originals', '51-22b-prospects': '22B The Prospects'}
IDS = ('01-old-guard', '02-silent-watch', '03-union-jack', '04-british-grit', '05-first-in', '06-last-out',
       '07-tea-before-chaos', '08-hurry-up-wait', '09-map-upside-down', '10-dangerous-vintage', '11-field-medic',
       '12-dustoff', '13-armoured-attitude', '14-steel-cavalry', '15-low-and-fast', '16-rotor-head', '17-long-game',
       '18-eyes-on', '19-wire-whisperer', '20-check-check', '21-heavy-lifter', '22-supply-line', '23-dig-in',
       '24-build-it', '25-eod-coffee', '26-boom-delivery', '27-overwatch', '28-night-shift', '29-no-sleep',
       '30-friendly-fire', '31-squad-anchor', '32-no-one-left', '33-brothers-in-mud', '34-grumpy-effective',
       '35-knees-optional', '36-not-retired', '37-rain-certified', '38-full-english', '39-biscuit-reserve',
       '40-morale-officer', '41-st-george', '42-saltire', '43-welsh-dragon', '44-irish-tricolour',
       '45-celtic-sentinel', '46-guardian', '47-steady-faith', '48-iron-will', '49-against-odds', ORIGINALS, PROSPECTS)


def name(pid):
    return NAMES.get(pid) or pid.split('-', 1)[1].replace('-', ' ').title()


def tier(pid):
    return 'role' if pid in ROLE_PATCHES else 'legendary' if pid in LEGENDARY else 'rare' if pid in RARE else 'common'


CATALOGUE = [{'id': pid, 'name': name(pid), 'tier': tier(pid), 'cost': PRICES.get(tier(pid)),
              'role': ROLE_PATCHES[pid][0] if pid in ROLE_PATCHES else None} for pid in IDS]
BY_ID = {p['id']: p for p in CATALOGUE}


def _plain(name):
    """'[22B]' and '22b' both become '22b', so role names match however they are bracketed."""
    return ''.join(c for c in str(name) if c.isalnum()).casefold()


def role_for(guild, pid):
    """The Discord role that owns a role patch: the role ID in its Railway variable, else the role with that name."""
    wanted, env = ROLE_PATCHES[pid]
    raw = os.getenv(env, '').strip()
    if raw.isdecimal() and guild is not None:
        return guild.get_role(int(raw))
    roles = getattr(guild, 'roles', None)
    if not isinstance(roles, (list, tuple)):
        return None
    return next((r for r in roles if _plain(r.name) == _plain(wanted)), None)


def originals_role(guild):
    return role_for(guild, ORIGINALS)


def has_role_for(member, pid):
    role = role_for(getattr(member, 'guild', None), pid)
    return bool(role and any(r.id == role.id for r in getattr(member, 'roles', [])))


def sync_role_patches(state, guild):
    """Give each role patch to everyone with its role, and take it from anyone without it."""
    from community_hq import locker, state as hq
    for pid in ROLE_PATCHES:
        role = role_for(guild, pid)
        if role is None:
            continue  # Role missing: leave things as they are rather than strip everyone.
        holders = {str(m.id) for m in role.members}
        for uid in holders:
            locker(state, uid)['earned'].setdefault(pid, {'role': True, 'at': time.time()})
        for uid, box in hq(state)['lockers'].items():
            if uid not in holders and pid in box.get('earned', {}):
                box['earned'].pop(pid)
                box['display'] = [p for p in box.get('display', []) if p != pid]


sync_originals = sync_role_patches  # Older name.


def buy(state, uid, pid, now=None):
    """Spend Merits on a patch for the member's locker. Returns a message."""
    import merits
    from community_hq import locker
    now = time.time() if now is None else now
    patch = BY_ID.get(pid)
    if not patch:
        raise ValueError('Choose a patch from the Armoury.')
    if pid in ROLE_PATCHES:
        raise ValueError(f"The {patch['name']} patch cannot be bought: it belongs to members with the {ROLE_PATCHES[pid][0]} role.")
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
    return [{**p, 'owned': p['id'] in owned,
             'eligible': p['id'] not in ROLE_PATCHES or (member is not None and has_role_for(member, p['id']))} for p in CATALOGUE]
