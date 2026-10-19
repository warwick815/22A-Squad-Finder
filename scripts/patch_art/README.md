# Morale patch artwork

The six newer patches (Thin Red Line, Tin Hat, Stag On, Quartermaster, Hammer Down,
Lionheart) are drawn in code and then given an embroidered finish: woven backing,
satin-stitch thread, raised shading and a merrowed edge.

To rebuild them, or add a new design to `designs.py`, run from this folder:

```
mkdir -p build
cp path/to/oswald-latin-700-normal.woff2 build/oswald-700.woff2   # e.g. from the @fontsource/oswald npm package
python designs.py build                                          # flat SVG artwork
node render.js                                                   # build/*.png at 960px (needs Playwright)
python embroider.py build ../../web/patches                      # embroidered 480px WebP files
```

`embroider.py` needs numpy, scipy and Pillow. To use a different image for a patch,
for example AI-generated art, save it as `web/patches/<id>.webp` (480×480, transparent background).
