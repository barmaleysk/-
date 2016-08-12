from app import MasterBot
from utils import Singleton


class BotManager(Singleton):
    WEBHOOK_HOST = 'ec2-52-34-35-240.us-west-2.compute.amazonaws.com'
    WEBHOOK_PORT = 8443
    WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
    WEBHOOK_SSL_CERT = '/home/ubuntu/webhook_cert.pem'
    bots = {}

    def register_bot(self, bot):
        bot.remove_webhook()
        print 'registered bot at', self.WEBHOOK_URL_BASE + '/' + bot.token + '/'
        bot.set_webhook(url=self.WEBHOOK_URL_BASE + '/' + bot.token + '/', certificate=open(self.WEBHOOK_SSL_CERT, 'r'))
        self.bots[bot.token] = bot

if __name__ == "__main__":
    MasterBot({'token': '203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw'}, BotManager()).start()
