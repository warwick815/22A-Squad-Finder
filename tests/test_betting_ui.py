import unittest
from unittest.mock import Mock
from betting import Book, OfferModal, panel_embed

class BettingUITests(unittest.IsolatedAsyncioTestCase):
    async def test_forms_only_show_relevant_fields(self):
        for mode,count in [('race',2),('kills',3),('limit',4)]:
            modal=OfferModal(2,mode)
            self.assertEqual(len(modal.children),count)
            self.assertFalse(any('Mode:' in c.label for c in modal.children))

    async def test_reset_cancels_bets_resets_wallets_and_rejects_old_confirmation(self):
        store=Mock();store.get.return_value=None
        book=Book(store)
        b=book.offer(1,2,500,'kills',20,1,10,1000)
        book.reset(99,0,1100)
        self.assertEqual(book.data['wallets'],{'1':10000,'2':10000})
        self.assertEqual(b['status'],'settled')
        self.assertFalse(book.finish(b,1,'late payout'))
        self.assertEqual(book.data['reset_history'][0]['actor'],99)
        with self.assertRaises(ValueError):book.reset(99,0,1200)

    async def test_embed_limits(self):
        e=panel_embed()
        self.assertLess(len(e),6000)
        self.assertTrue(all(len(f.value)<=1024 for f in e.fields))
