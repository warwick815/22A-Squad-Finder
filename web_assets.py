"""Builds the website's CSS bundle and serves text assets compressed and cache-friendly.

The source files in web/ stay separate so they are easy to edit. At start-up this
module reads web/index.html, joins every stylesheet it links (in the same order)
into one bundle.css, stamps each script with a hash of its contents, and keeps
gzip copies in memory. Because the URLs change whenever a file's contents change,
browsers can cache them for a year and still always get the latest version after
a redeploy. No manual ?v= bumping needed.
"""
import gzip
import hashlib
import re
from pathlib import Path

from aiohttp import web

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
TYPES = {'.css': 'text/css', '.js': 'application/javascript', '.html': 'text/html'}
LINK = re.compile(r'<link rel="stylesheet" href="/assets/([a-z0-9-]+\.css)(?:\?[^"]*)?">')
SCRIPT = re.compile(r'<script src="/assets/([a-z0-9-]+\.js)(?:\?[^"]*)?" defer></script>')
YEAR = 'public, max-age=31536000, immutable'


def digest(data):
    return hashlib.sha256(data).hexdigest()[:12]


class Asset:
    def __init__(self, body, content_type):
        self.body, self.content_type = body, content_type
        self.gzipped = gzip.compress(body, 9, mtime=0)
        self.version = digest(body)


class AssetPipeline:
    def __init__(self, web_dir=WEB):
        self.web_dir = Path(web_dir)
        self.assets = {}
        self.build()

    def build(self):
        html = (self.web_dir / 'index.html').read_text(encoding='utf-8')
        styles = LINK.findall(html)
        parts = []
        for name in styles:
            css = (self.web_dir / name).read_text(encoding='utf-8')
            parts.append(f'/* --- {name} --- */\n{css.strip()}\n')
        self.assets['bundle.css'] = Asset(''.join(parts).encode(), TYPES['.css'])
        for path in self.web_dir.iterdir():
            if path.suffix in ('.css', '.js') and path.is_file():
                self.assets[path.name] = Asset(path.read_bytes(), TYPES[path.suffix])

        bundle = '<link rel="stylesheet" href="/assets/bundle.css?v=%s">' % self.assets['bundle.css'].version
        first = True

        def style(match):
            nonlocal first
            if first:
                first = False
                return bundle
            return ''

        def script(match):
            name = match.group(1)
            asset = self.assets.get(name)
            version = asset.version if asset else '0'
            return f'<script src="/assets/{name}?v={version}" defer></script>'

        html = SCRIPT.sub(script, LINK.sub(style, html))
        self.index = Asset(html.encode(), TYPES['.html'])

    @staticmethod
    def respond(request, asset, cache):
        accepts_gzip = 'gzip' in request.headers.get('Accept-Encoding', '').lower()
        tag = f'"{asset.version}-gz"' if accepts_gzip else f'"{asset.version}"'
        headers = {'Cache-Control': cache, 'Vary': 'Accept-Encoding', 'ETag': tag}
        if request.headers.get('If-None-Match') == tag:
            return web.Response(status=304, headers=headers)
        if accepts_gzip:
            headers['Content-Encoding'] = 'gzip'
        body = asset.gzipped if accepts_gzip else asset.body
        return web.Response(body=body, headers=headers, content_type=asset.content_type, charset='utf-8')

    async def page(self, request):
        return self.respond(request, self.index, 'no-cache')

    async def text_asset(self, request):
        asset = self.assets.get(request.match_info['name'])
        if asset is None:
            raise web.HTTPNotFound()
        cache = YEAR if request.query.get('v') == asset.version else 'public, max-age=300'
        return self.respond(request, asset, cache)
