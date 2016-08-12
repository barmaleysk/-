import web
from web.wsgiserver import CherryPyWSGIServer
from app import MasterBot
from utils import Singleton, VKListener, Listener
import telebot

CherryPyWSGIServer.ssl_certificate = "/home/ubuntu/webhook_cert.pem"
CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"

urls = ("/.*", "hello")
app = web.application(urls, globals())


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


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        data = web.data()
        update = telebot.types.Update.de_json(data.encode('utf-8'))
        BotManager().process_update(token, update)
        return '!'

if __name__ == "__main__":
    VKListener().start()
    mb = MasterBot({'token': '203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw'}, BotManager())
    Listener(mb.process_vk_output, ['vk_output']).start()
    mb.start()
    app.run()
