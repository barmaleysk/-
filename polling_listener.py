from utils import Singleton
import telebot
import copy
import redis
import json
from utils import Listener
from multiprocessing import Process
from app import MasterBot


class PollingProcessor(Singleton):
    tokens = {}
    r = redis.Redis()

    def register_token(self, data):
        print data
        if isinstance(data['data'], basestring):
            self.tokens[data['data']] = 0

    def get_updates(self, silent=False):
        tokens = copy.copy(self.tokens)
        res = False
        for token in tokens.keys():
            updates = telebot.apihelper.get_updates(token, offset=self.tokens.get(token) or 0)
            for update in updates:
                if update['update_id'] > self.tokens[token]:
                    self.tokens[token] = update['update_id']
                    res = True
                    if not silent:
                        print silent
                        self.r.publish(token, json.dumps(update))
        return res

    def start(self):
        Listener(self.register_token, ['bots']).start()
        while self.get_updates(silent=True):
            pass
        while True:
            self.get_updates()


if __name__ == "__main__":
    Process(target=MasterBot({'token': open('token').read()}).start).start()
    PollingProcessor().start()