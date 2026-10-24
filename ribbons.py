"""Ribbon designs for the Discord honours card, copied from web/medals.js so a ribbon
looks the same on the website and in Discord (tests keep the two in sync).

Each design lists stripes from the left edge to the centre; the right half mirrors it.
A device (metal pin) sits in the middle; season podium medals get a star.
"""
INK = {'black': '#18181a',
 'bronze': '#a5662f',
 'gold': '#d4a32a',
 'green': '#2c6a37',
 'khaki': '#a8935a',
 'navy': '#1c2752',
 'orange': '#cf6b1f',
 'purple': '#5b2d84',
 'red': '#a8182c',
 'royal': '#2a5cae',
 'scarlet': '#cf2f2f',
 'silver': '#b9bcc0',
 'sky': '#7fb2dc',
 'white': '#efece2'}

DESIGNS = {'armourer': {'stripes': (('khaki', 3), ('black', 2), ('bronze', 2), ('black', 1), ('khaki', 4))},
 'bounty1': {'stripes': (('black', 3), ('scarlet', 3), ('gold', 1), ('scarlet', 3), ('black', 2))},
 'bounty5': {'device': 'gold',
             'stripes': (('black', 3), ('scarlet', 3), ('gold', 1), ('scarlet', 3), ('black', 2))},
 'cash10m': {'stripes': (('khaki', 4), ('gold', 2), ('green', 3), ('gold', 1), ('green', 3))},
 'cash50m': {'device': 'gold',
             'stripes': (('khaki', 4), ('gold', 2), ('green', 3), ('gold', 1), ('green', 3))},
 'club1': {'stripes': (('purple', 4), ('gold', 3), ('black', 2), ('gold', 4))},
 'club10': {'device': 'silver', 'stripes': (('purple', 4), ('gold', 3), ('black', 2), ('gold', 4))},
 'club25': {'device': 'gold', 'stripes': (('purple', 4), ('gold', 3), ('black', 2), ('gold', 4))},
 'crewman': {'stripes': (('black', 3), ('khaki', 2), ('green', 3), ('khaki', 1), ('black', 3))},
 'grenadier': {'stripes': (('orange', 3), ('green', 2), ('orange', 2), ('black', 1), ('green', 4))},
 'hawkeye': {'device': 'gold',
             'stripes': (('green', 3), ('khaki', 2), ('green', 2), ('white', 1), ('black', 4))},
 'headhunter': {'stripes': (('scarlet', 3), ('black', 2), ('white', 1), ('black', 2), ('scarlet', 4))},
 'hours100': {'stripes': (('green', 6), ('gold', 2), ('green', 2), ('white', 1), ('green', 2))},
 'hours250': {'device': 'silver',
              'stripes': (('green', 6), ('gold', 2), ('green', 2), ('white', 1), ('green', 2))},
 'hours500': {'device': 'gold',
              'stripes': (('green', 6), ('gold', 2), ('green', 2), ('white', 1), ('green', 2))},
 'kills100': {'stripes': (('black', 4), ('scarlet', 2), ('black', 2), ('scarlet', 5))},
 'kills1000': {'device': 'silver', 'stripes': (('black', 4), ('scarlet', 2), ('black', 2), ('scarlet', 5))},
 'kills10000': {'device': 'gold',
                'stripes': (('black', 3),
                            ('gold', 1),
                            ('black', 2),
                            ('scarlet', 2),
                            ('black', 1),
                            ('scarlet', 4))},
 'kills5000': {'device': 'gold', 'stripes': (('black', 4), ('scarlet', 2), ('black', 2), ('scarlet', 5))},
 'linked': {'stripes': (('navy', 6), ('red', 3), ('white', 1), ('red', 3))},
 'marksman': {'stripes': (('green', 3), ('khaki', 2), ('green', 2), ('white', 1), ('black', 4))},
 'nco': {'stripes': (('red', 4), ('gold', 2), ('red', 3), ('gold', 1), ('navy', 3))},
 'patches3': {'stripes': (('khaki', 3), ('purple', 2), ('khaki', 2), ('white', 1), ('purple', 4))},
 'patches6': {'device': 'silver',
              'stripes': (('khaki', 3), ('purple', 2), ('khaki', 2), ('white', 1), ('purple', 4))},
 'rapidfire': {'stripes': (('orange', 3), ('black', 2), ('orange', 2), ('black', 1), ('scarlet', 4))},
 'relentless': {'device': 'gold',
                'stripes': (('orange', 3), ('scarlet', 2), ('black', 2), ('gold', 1), ('scarlet', 4))},
 'revenge': {'stripes': (('purple', 3), ('black', 2), ('scarlet', 3), ('black', 1), ('purple', 3))},
 'sapper': {'stripes': (('royal', 3), ('red', 2), ('royal', 2), ('khaki', 1), ('red', 4))},
 'sergeant': {'device': 'silver', 'stripes': (('red', 4), ('gold', 2), ('red', 3), ('gold', 1), ('navy', 3))},
 'sharpshooter': {'stripes': (('green', 4), ('black', 2), ('white', 1), ('black', 2), ('green', 3))},
 'squad5': {'stripes': (('green', 3), ('white', 1), ('green', 2), ('purple', 2), ('green', 4))},
 'staffsgt': {'device': 'gold', 'stripes': (('red', 4), ('gold', 2), ('red', 3), ('gold', 1), ('navy', 3))},
 'stripes': {'stripes': (('green', 5), ('khaki', 3), ('white', 1), ('khaki', 4))},
 'taggold': {'device': 'gold',
             'stripes': (('black', 3), ('gold', 2), ('black', 2), ('white', 1), ('gold', 4))},
 'tags1': {'stripes': (('black', 3), ('bronze', 2), ('black', 2), ('white', 1), ('bronze', 4))},
 'tags10': {'device': 'bronze',
            'stripes': (('black', 3), ('bronze', 2), ('black', 2), ('white', 1), ('bronze', 4))},
 'tagsilver': {'device': 'silver',
               'stripes': (('black', 3), ('silver', 2), ('black', 2), ('white', 1), ('silver', 4))},
 'unstoppable': {'stripes': (('orange', 3), ('scarlet', 2), ('black', 2), ('gold', 1), ('scarlet', 4))},
 'veteran': {'stripes': (('purple', 5), ('white', 2), ('purple', 3), ('white', 1), ('purple', 2))},
 'veteran2': {'device': 'silver',
              'stripes': (('purple', 5), ('white', 2), ('purple', 3), ('white', 1), ('purple', 2))},
 'warrant': {'device': 'gold',
             'stripes': (('navy', 3), ('gold', 2), ('red', 2), ('gold', 2), ('navy', 2), ('white', 1))},
 'weaponmaster': {'device': 'gold',
                  'stripes': (('khaki', 3), ('black', 2), ('gold', 2), ('black', 1), ('khaki', 4))},
 'wins10': {'stripes': (('navy', 3), ('white', 2), ('red', 3), ('white', 2), ('royal', 3))},
 'wins100': {'device': 'gold',
             'stripes': (('navy', 3), ('white', 2), ('red', 3), ('white', 2), ('royal', 3))},
 'wins250': {'stripes': (('red', 3), ('navy', 2), ('white', 1), ('navy', 2), ('red', 2), ('gold', 3))},
 'wins50': {'device': 'silver',
            'stripes': (('navy', 3), ('white', 2), ('red', 3), ('white', 2), ('royal', 3))}}

KEYS = ('navy', 'red', 'green', 'purple', 'royal', 'khaki', 'gold', 'black')


def design(medal):
    """The stripes and device for a medal, matching ribbonDesign() in medals.js."""
    metal = medal.get('metal')
    if metal in ('gold', 'silver', 'bronze'):
        return {'stripes': (('navy', 3), ('white', 1), ('red', 4), (metal, 5)), 'device': metal, 'star': True}
    if medal.get('id') in DESIGNS:
        return DESIGNS[medal['id']]
    h = 0
    for c in str(medal.get('id') or medal.get('name')):
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return {'stripes': ((KEYS[h % 8], 5), ('white', 1), (KEYS[(h >> 3) % 8], 4), (KEYS[(h >> 6) % 8], 3))}
