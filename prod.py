import web
from web.wsgiserver import CherryPyWSGIServer
from app import MasterBot, Singleton
import telebot

WEBHOOK_PORT = 8443
WEBHOOK_HOST = 'ec2-52-34-35-240.us-west-2.compute.amazonaws.com'
WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)

WEBHOOK_SSL_CERT = CherryPyWSGIServer.ssl_certificate = '/home/ubuntu/webhook_cert.pem'
WEBHOOK_SSL_PKEY = CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"


class WebHookBotManager(Singleton):
    bots = {}

    def register_bot(self, bot):
        bot.remove_webhook()
        webhook_url = WEBHOOK_URL_BASE + '/' + bot.token + '/'
        print 'registered bot at', webhook_url
        bot.set_webhook(url=webhook_url, certificate=open('/home/ubuntu/webhook_cert.pem', 'r'))
        self.bots[bot.token] = bot
        print self.bots

    def process_update(self, token, update):
        print self.bots
        if token in self.bots:
            self.bots[token].process_new_updates([update])
        return ''


urls = ("/.*", "hello")
app = web.application(urls, globals())


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        data = web.data()
        update = telebot.types.Update.de_json(data.encode('utf-8'))
        WebHookBotManager().process_update(token, update)
        return '!'

if __name__ == "__main__":
    mb = MasterBot({'token': "203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw"}, WebHookBotManager())
    mb.start()
    app.run()
