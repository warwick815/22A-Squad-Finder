import sys, glob, numpy as np
from PIL import Image
from scipy import ndimage as nd
src_dir, out_dir = sys.argv[1], sys.argv[2]
N = 960
rng = np.random.default_rng(11)
yy, xx = np.mgrid[0:N, 0:N].astype(float)

def hash1(v): return (np.sin(v*12.9898)*43758.5453) % 1.0

# Fine twill backing: tight diagonal weave with fibre noise.
u = (xx + yy)/2.0; v = (xx - yy)/2.0
twill = 0.82 + 0.22*(0.5+0.5*np.sin(2*np.pi*u/2.6)) * (0.6+0.4*(0.5+0.5*np.sin(2*np.pi*v/11)))
twill *= 1 + rng.normal(0, 0.06, (N, N))
fibre = nd.gaussian_filter(rng.normal(0, 1, (N, N)), 6); twill *= 1 + 0.06*fibre/fibre.std()

def satin(angle, period=3.4):
    a = np.deg2rad(angle); s = xx*np.cos(a)+yy*np.sin(a); t = -xx*np.sin(a)+yy*np.cos(a)
    row = np.floor(t/period); ph = hash1(row)
    f = 0.5+0.5*np.cos(2*np.pi*(t/period))           # thread rounding across the stitch
    stagger = 0.5+0.5*np.sin(2*np.pi*(s/38 + ph))       # long stitch lengths
    return 0.62 + 0.45*f**0.8 + 0.08*(ph-0.5) + 0.05*stagger

def muted(rgb, amount=0.22, darken=0.92):
    g = rgb.mean(-1, keepdims=True)
    return (rgb*(1-amount) + g*amount)*darken

for path in sorted(glob.glob(src_dir+'/*.png')):
    name = path.rsplit('/', 1)[1][:-4]
    im = np.asarray(Image.open(path).convert('RGBA').resize((N, N))).astype(float)
    rgb, A = im[..., :3], im[..., 3]/255
    inside = A > 0.5
    dist = nd.distance_transform_edt(inside)
    BW = 26
    border = inside & (dist <= BW)
    bgcol = np.array([0x15, 0x1a, 0x16], float)
    bg = inside & ~border & (np.abs(rgb-bgcol).sum(-1) < 24)
    design = inside & ~border & ~bg
    out = np.zeros_like(rgb)

    # 1. backing fabric, with shadow where stitching sits on it
    ao = nd.gaussian_filter(design.astype(float), 6)
    base = np.array([20, 24, 21], float)
    out[bg] = base * twill[bg][:, None] * (1-0.6*ao[bg])[:, None]

    # 2. stitched artwork: split into colour regions, each with its own stitch angle
    q = (rgb[..., 0]//24)*10000 + (rgb[..., 1]//24)*100 + (rgb[..., 2]//24)
    angles = [38, 142, 62, 118, 25, 155, 80]
    k = 0
    for val in np.unique(q[design]):
        lab, n = nd.label(design & (q == val))
        for i in range(1, n+1):
            reg = lab == i
            if reg.sum() < 30: continue
            k += 1
            d = nd.distance_transform_edt(reg)
            puff = np.sin(np.clip(d/7, 0, 1)*np.pi/2)          # rounded, padded fill
            colour = muted(rgb[reg])
            tex = satin(angles[k % len(angles)])[reg]
            shade = (0.70 + 0.30*puff[reg])
            out[reg] = colour*tex[:, None]*shade[:, None]
            # dark running stitch around each shape
            edge = reg & (d <= 1.6)
            out[edge] = out[edge]*0.45
    # light from the top-left across the raised stitching
    H = nd.gaussian_filter(design.astype(float), 2.5)
    gy, gx = np.gradient(H)
    lit = np.clip((-gx-gy)*1.1, -0.5, 0.5)
    out[design] *= (1 + lit[design])[:, None]

    # 3. merrowed edge: thread wrapped tightly over a cord
    # Position along the outline: arc length of the nearest edge point, measured
    # round the (convex) shape by angle from its centre.
    cy, cx = nd.center_of_mass(inside)
    outline = inside & ~nd.binary_erosion(inside)
    oy, ox = np.nonzero(outline)
    th = np.arctan2(oy-cy, ox-cx); rr = np.hypot(oy-cy, ox-cx)
    bins = np.linspace(-np.pi, np.pi, 2049)
    idx = np.clip(np.digitize(th, bins)-1, 0, 2047)
    rad = np.zeros(2048); np.maximum.at(rad, idx, rr)
    rad = np.interp(np.arange(2048), np.nonzero(rad)[0], rad[np.nonzero(rad)[0]])
    seg = np.hypot(rad, np.gradient(rad)/(2*np.pi/2048))*(2*np.pi/2048)
    arc = np.concatenate([[0], np.cumsum(seg)])[:-1]
    _, (iy, ix) = nd.distance_transform_edt(~outline, return_indices=True)
    near_th = np.arctan2(iy-cy, ix-cx)
    along = arc[np.clip(np.digitize(near_th, bins)-1, 0, 2047)]
    # Merrow stitch: each wrap slants across the cord.
    wrap = 0.5+0.5*np.sin(2*np.pi*(along/5.0 + dist/14.0))
    cord = np.sin(np.clip(dist/BW, 0, 1)*np.pi)
    olive = np.array([0x4b, 0x58, 0x33], float)
    shade = (0.28 + 0.72*cord**0.6) * (0.30 + 0.95*wrap**1.8)
    out[border] = olive*shade[border][:, None]
    inner_line = inside & (np.abs(dist-BW) < 1.3)
    out[inner_line] *= 0.35

    out += rng.normal(0, 2.5, out.shape)
    out = np.clip(out, 0, 255)
    # slightly fuzzy outer edge, like thread
    alpha = nd.gaussian_filter(inside.astype(float), 0.9) * (1 - 0.25*(dist < 2)*rng.random((N, N)))
    img = Image.fromarray(np.dstack([out, alpha*255]).astype(np.uint8), 'RGBA')
    shadow = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    shadow.putalpha(Image.fromarray((nd.gaussian_filter(np.roll(inside.astype(float), 12, 0), 10)*170).astype(np.uint8)))
    Image.alpha_composite(shadow, img).resize((480, 480), Image.LANCZOS).save(f'{out_dir}/{name}.webp', 'WEBP', quality=90, method=6)
    print(name, 'stitched regions', k)
