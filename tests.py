import utils
import pymongo
import unittest


class MailerTestCase(unittest.TestCase):
    def test_basic(self):
        db = pymongo.MongoClient()['marketbot']
        order = list(db.orders.find({}))[-1]
        resp = utils.Mailer().send_order('marketbottest@gmail.com', order)
        self.assertEquals(resp.status_code, 202)
