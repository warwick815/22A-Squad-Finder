import sys
out=sys.argv[1]
CREAM='#e7dcc0';OLIVE='#4f5e37';OLIVE_HI='#7d8f57';LIME='#a6e35a';PURPLE='#8e5bd0';RED='#c22b33';GOLD='#d8ad45';STEEL='#9aa3a0'
FONT="font-family=\"Oswald,'Bahnschrift SemiCondensed',Impact,'Arial Narrow',sans-serif\" font-weight=\"700\""
def patch(shape,body,label,label_y=410,size=34,width=240):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 480" width="480" height="480">
<defs>
<pattern id="twill" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="#141915"/><rect width="2.2" height="6" fill="#1b211c"/></pattern>
<pattern id="thread" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)"><rect width="3" height="3" fill="#000" fill-opacity="0"/><rect width="1" height="3" fill="#000" fill-opacity=".22"/></pattern>
<filter id="emb" x="-5%" y="-5%" width="110%" height="110%"><feDropShadow dx="0" dy="2" stdDeviation="1.4" flood-color="#000" flood-opacity=".75"/></filter>
<filter id="drop" x="-10%" y="-10%" width="120%" height="125%"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#000" flood-opacity=".55"/></filter>
<clipPath id="clip"><path d="{shape}"/></clipPath>
</defs>
<g>
<path d="{shape}" fill="#151a16"/>
<g clip-path="url(#clip)">{body}
<text x="240" y="{label_y}" text-anchor="middle" font-size="{size}" textLength="{width}" lengthAdjust="spacingAndGlyphs" {FONT} fill="{CREAM}" stroke="#0b0d0b" stroke-width="5" paint-order="stroke" stroke-linejoin="round">{label}</text></g>
<path d="{shape}" fill="none" stroke="{OLIVE}" stroke-width="22"/>
</g></svg>'''
shield='M60 40H420V250C420 360 330 420 240 452C150 420 60 360 60 250Z'
circle='M240 28A212 212 0 1 1 239.9 28Z'
hexagon='M240 24L432 130V350L240 456L48 350V130Z'
rect='M64 30H416Q432 30 432 46V434Q432 450 416 450H64Q48 450 48 434V46Q48 30 64 30Z'
pennant='M52 40H428V300L240 450L52 300Z'

def hills(y, far='#2c3a26', near='#3b4b2e'):
    return (f'<path d="M30 {y}L110 {y-46}L170 {y-18}L250 {y-70}L330 {y-26}L400 {y-54}L460 {y-20}V480H30Z" fill="{far}"/>'
            f'<path d="M30 {y+18}L140 {y-14}L230 {y+10}L320 {y-22}L460 {y+12}V480H30Z" fill="{near}"/>')
def pines(y, xs, h=34, c='#1f2a1c'):
    return ''.join(f'<path d="M{x} {y-h}L{x+11} {y}H{x-11}Z" fill="{c}"/><path d="M{x} {y-h-14}L{x+8} {y-h+8}H{x-8}Z" fill="{c}"/>' for x in xs)
def stars3(y):
    star = lambda x, c, r: f'<path transform="translate({x} {y}) scale({r})" d="M0 -10l2.9 6 6.6.9-4.8 4.6 1.2 6.5L0 14.9-5.9 18l1.2-6.5-4.8-4.6 6.6-.9z" fill="{c}"/>'
    return star(200, PURPLE, 1.1) + star(240, LIME, 1.5) + star(280, PURPLE, 1.1)
def laurel(cx, cy, side):
    s = -1 if side == 'l' else 1
    leaves = ''.join(f'<ellipse cx="{cx+s*(8+i*3)}" cy="{cy-i*26}" rx="8" ry="15" transform="rotate({s*(25+i*6)} {cx+s*(8+i*3)} {cy-i*26})" fill="#6f8a45"/>' for i in range(5))
    return f'<path d="M{cx} {cy+10}C{cx+s*24} {cy-40} {cx+s*20} {cy-90} {cx+s*6} {cy-130}" stroke="#55703a" stroke-width="6" fill="none"/>' + leaves
designs={
'thinred':(shield,hills(300)+pines(296,[110,150,330,372])+f'''<rect x="40" y="226" width="400" height="16" fill="{RED}"/>
<g stroke="{STEEL}" stroke-width="13" stroke-linecap="round"><path d="M140 110L330 320"/><path d="M340 110L150 320"/></g>
<g fill="{STEEL}"><path d="M128 92L162 104L146 122Z"/><path d="M352 92L318 104L334 122Z"/></g>
<g stroke="#5c3b22" stroke-width="20" stroke-linecap="round"><path d="M276 260L330 320"/><path d="M204 260L150 320"/></g>
<g fill="{LIME}"><circle cx="240" cy="96" r="7"/><circle cx="208" cy="96" r="5"/><circle cx="272" cy="96" r="5"/></g>''','THIN RED LINE',358,34),
'tinhat':(circle,f'''<ellipse cx="240" cy="236" rx="150" ry="30" fill="{OLIVE}"/>
<path d="M120 232C120 138 175 104 240 104S360 138 360 232Z" fill="#5f6f45"/>
<path d="M150 214C156 150 196 122 240 122" stroke="{OLIVE_HI}" stroke-width="10" fill="none" stroke-linecap="round"/>
<ellipse cx="240" cy="236" rx="150" ry="30" fill="none" stroke="#2e3622" stroke-width="6"/>
<g fill="{LIME}"><path d="M240 288l9 18 20 3-14 14 3 20-18-9-18 9 3-20-14-14 20-3z"/></g>
<path d="M118 330H362" stroke="{PURPLE}" stroke-width="6"/>''','TIN HAT',398,40),
'stagon':(rect,f'''<circle cx="345" cy="104" r="34" fill="{CREAM}" opacity=".85"/><circle cx="360" cy="96" r="30" fill="#141915"/>
<g fill="{CREAM}" opacity=".9"><circle cx="110" cy="80" r="2.5"/><circle cx="150" cy="120" r="2"/><circle cx="400" cy="170" r="2"/><circle cx="90" cy="170" r="2"/></g>
<g stroke="#b99a6a" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" fill="none">
<path d="M222 200C190 170 170 140 160 96M182 142L140 128M170 116L138 84M196 174L150 176"/>
<path d="M258 200C290 170 310 140 320 96M298 142L340 128M310 116L342 84M284 174L330 176"/></g>
<path d="M240 196C214 196 204 220 210 250L226 296Q240 312 254 296L270 250C276 220 266 196 240 196Z" fill="#8a6a43"/>
<circle cx="226" cy="236" r="5" fill="#141915"/><circle cx="254" cy="236" r="5" fill="#141915"/>
<path d="M48 340L150 316L240 334L330 312L432 336V460H48Z" fill="#26301f"/>
<path d="M48 360L130 346L240 362L350 344L432 358V460H48Z" fill="#1d2519"/>''','STAG ON',414,42),
'quartermaster':(hexagon,hills(336)+pines(330,[90,130,350,392],30)+f'''<path d="M120 196L240 150L360 196L240 242Z" fill="#7a8a52"/>
<path d="M120 196V300L240 346V242Z" fill="#5f6f45"/><path d="M360 196V300L240 346V242Z" fill="#4c5a37"/>
<g stroke="#2e3622" stroke-width="5"><path d="M120 196L240 242L360 196M240 242V346"/><path d="M150 230V320M330 230V320"/></g>
<text x="300" y="304" text-anchor="middle" font-size="64" {FONT} fill="{GOLD}" transform="skewY(-21) translate(0 112)">£</text>
<g fill="{GOLD}"><circle cx="150" cy="128" r="16"/><circle cx="330" cy="128" r="16"/></g>
<g fill="#141915"><text x="150" y="135" text-anchor="middle" font-size="20" {FONT}>£</text><text x="330" y="135" text-anchor="middle" font-size="20" {FONT}>£</text></g>''','QUARTERMASTER',376,30),
'hammerdown':(pennant,'<path d="M52 300L130 210L180 250L240 170L300 240L350 200L428 300Z" fill="#2c3a26"/><path d="M222 186L240 170L258 190Z" fill="#d8d2bf"/>'+f'''<path d="M150 80L330 80L300 120H180Z" fill="{STEEL}"/>
<rect x="226" y="112" width="28" height="170" rx="8" fill="#6b4a2c"/>
<path d="M120 70H360V108H120Z" fill="#7f8786"/><path d="M120 70H360V82H120Z" fill="#b5bdbb"/>
<path d="M330 150L380 190L350 196L392 250L320 200L350 194Z" fill="{LIME}"/>
<path d="M150 150L100 190L130 196L88 250L160 200L130 194Z" fill="{PURPLE}"/>''','HAMMER DOWN',350,34),
'lionheart':(shield,f'''<path d="M150 96H330L318 146H162Z" fill="{GOLD}"/>
<g fill="{GOLD}"><circle cx="160" cy="92" r="11"/><circle cx="200" cy="80" r="11"/><circle cx="240" cy="72" r="13"/><circle cx="280" cy="80" r="11"/><circle cx="320" cy="92" r="11"/></g>
<g fill="{PURPLE}"><rect x="182" y="112" width="18" height="18" rx="3"/><rect x="231" y="112" width="18" height="18" rx="3"/><rect x="280" y="112" width="18" height="18" rx="3"/></g>
<path d="M240 330C150 268 140 214 176 188C204 168 232 184 240 206C248 184 276 168 304 188C340 214 330 268 240 330Z" fill="{RED}"/>
<path d="M188 204C200 196 214 198 222 210" stroke="#ef6b6b" stroke-width="8" fill="none" stroke-linecap="round"/>
<g fill="none" stroke="#6f8a45" stroke-width="9" stroke-linecap="round"><path d="M120 190C110 250 140 300 196 336"/><path d="M360 190C370 250 340 300 284 336"/></g>
<g fill="#7f9d4f"><ellipse cx="118" cy="226" rx="9" ry="16" transform="rotate(-20 118 226)"/><ellipse cx="134" cy="276" rx="9" ry="16" transform="rotate(-40 134 276)"/><ellipse cx="362" cy="226" rx="9" ry="16" transform="rotate(20 362 226)"/><ellipse cx="346" cy="276" rx="9" ry="16" transform="rotate(40 346 276)"/></g>''','LIONHEART',372,36),
}
W={'thinred':250,'tinhat':150,'stagon':170,'quartermaster':230,'hammerdown':220,'lionheart':210}
for k,(shape,body,label,y,size) in designs.items():
    open(f'{out}/{k}.svg','w').write(patch(shape,body,label,y,size,W[k]))
print('ok')
