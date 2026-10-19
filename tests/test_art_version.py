import tempfile
import unittest
from pathlib import Path

from web_assets import AssetPipeline


class ArtVersionTests(unittest.TestCase):
    def test_replacing_artwork_changes_the_page_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = Path(tmp)
            (web / 'index.html').write_text('<body data-art="__ART_VERSION__"></body>')
            (web / 'patches').mkdir()
            (web / 'patches' / 'tinhat.webp').write_bytes(b'old art')
            first = AssetPipeline(web).index.body
            (web / 'patches' / 'tinhat.webp').write_bytes(b'new art')
            second = AssetPipeline(web).index.body
            self.assertNotIn(b'__ART_VERSION__', first)
            self.assertNotEqual(first, second)


if __name__ == '__main__':
    unittest.main()
