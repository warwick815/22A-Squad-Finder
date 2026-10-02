import json
import unittest
from tools_stats import parse_profile,profile_id

class ToolsImportTests(unittest.TestCase):
    def test_parser_reads_data_without_executing_script(self):
        data={'currentValues':dict(wardogLevel=133,xp=2005734,cash=341650,gold=0,worth=2780220),'currentLevels':dict(infantry=14,medic=10,recon=16,support=34,driver=32,pilot=27),'lastPolledAt':'2026-10-01T13:45:42Z'}
        html='<script>self.__next_f.push('+json.dumps([1,json.dumps(data)])+')</script>'
        p=parse_profile(html)
        self.assertEqual(p['levels']['support'],34)
        self.assertEqual(p['values']['cash'],341650)
    def test_reject_invalid_or_unavailable_page(self):
        with self.assertRaises(ValueError):parse_profile('<html>Sign in</html>')
    def test_only_public_profile_url_accepted(self):
        valid='https://wardogs.tools/player/d8f9bef7-7dc6-4017-8228-0fd1ce527c93'
        self.assertEqual(profile_id(valid),'d8f9bef7-7dc6-4017-8228-0fd1ce527c93')
        for bad in [valid+'/og','http://localhost/player/x',valid+'?redirect=x','https://wardogs.tools.evil/player/x']:
            with self.assertRaises(ValueError):profile_id(bad)
