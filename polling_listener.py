from gevent import monkey; monkey.patch_all()
from utils import Singleton
import telebot
import copy
import json
from app import MasterBot, Bot


class PollingProcessor(Singleton):
    tokens = {}
    mb = MasterBot({'token': open('token').read().replace('\n', '')})

    def get_updates(self, silent=False):
        res = False
        for token in copy.copy(Bot.bots.keys()):
            updates = telebot.apihelper.get_updates(token, offset=self.tokens.get(token) or 0)
            for update in updates:
                if update['update_id'] > self.tokens.get(token):
                    self.tokens[token] = update['update_id']
                    res = True
                    if not silent:
                        self.mb.route_update(token, json.dumps(update))
        return res

    def start(self):
        while self.get_updates(silent=True):
            pass
        while True:
            self.get_updates()


if __name__ == "__main__":
    PollingProcessor().start()
