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

    def get_updates(self):
        tokens = copy.copy(self.tokens)
        for token in tokens.keys():
            updates = telebot.apihelper.get_updates(token)
            for update in updates:
                if update['update_id'] > self.tokens[token]:
                    self.tokens[token] = update['update_id']
                    self.r.publish(token, json.dumps(update))

    def start(self):
        Listener(self.register_token, ['bots']).start()
        while True:
            self.get_updates()


if __name__ == "__main__":
    Process(target=MasterBot({'token': open('token.dev').read()}).start).start()
    PollingProcessor().start()
