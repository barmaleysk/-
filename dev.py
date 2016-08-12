from app import MasterBot
from utils import Singleton


class SimpleBotManager(Singleton):
    bots = set()

    def register_bot(self, bot):
        self.bots.add(bot)

    def run(self):
        while True:
            for bot in self.bots:
                upd = bot.get_updates(offset=(bot.last_update_id + 1), timeout=0)
                if len(upd) > 0:
                    bot.process_new_updates(upd)


if __name__ == "__main__":
    mb = MasterBot({'token': open('token.dev').read()}, SimpleBotManager())  # test
    mb.start()
    SimpleBotManager().run()
