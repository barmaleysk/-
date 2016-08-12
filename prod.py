import web
from web.wsgiserver import CherryPyWSGIServer
from app import MasterBot
from utils import Singleton, VKListener, Listener
import telebot
import redis

CherryPyWSGIServer.ssl_certificate = "/home/ubuntu/webhook_cert.pem"
CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"

urls = ("/.*", "hello")
app = web.application(urls, globals())
r = redis.Redis()
DELIMETER = '::::$$$$$$:::'


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

    def process_update(self, token, update):
        if token in self.bots:
            self.bots[token].process_new_updates([update])
        return ''

    def process_redis_update(self, data):
        try:
            data = data['data']
            token, update = data.split(DELIMETER)
            update = telebot.types.Update.de_json(update.encode('utf-8'))
            self.process_update(token, update)
        except Exception, e:
            print e


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        update = web.data()
        r.publish('updates', token + DELIMETER + update)
        return ''

if __name__ == "__main__":
    mb = MasterBot({'token': '203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw'}, BotManager())
    mb.start()
    VKListener().start()
    Listener(mb.process_vk_output, ['vk_output']).start()
    Listener(BotManager().process_redis_update, ['updates']).start()
    app.run()
