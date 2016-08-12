import web
from web.wsgiserver import CherryPyWSGIServer
import redis
from utils import Singleton
import telebot
from utils import Listener


class WebhookRegister(Singleton):
    WEBHOOK_HOST = 'ec2-52-34-35-240.us-west-2.compute.amazonaws.com'
    WEBHOOK_PORT = 8443
    WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
    WEBHOOK_SSL_CERT = '/home/ubuntu/webhook_cert.pem'

    def set_webhook(self, token):
        bot = telebot.TeleBot(token)
        bot.remove_webhook()
        print 'registered bot at', self.WEBHOOK_URL_BASE + '/' + bot.token + '/'
        bot.set_webhook(url=self.WEBHOOK_URL_BASE + '/' + bot.token + '/', certificate=open(self.WEBHOOK_SSL_CERT, 'r'))

    def register_bot_by_redis(self, data):
        try:
            self.set_webhook(data['data'])
        except Exception, e:
            print e

CherryPyWSGIServer.ssl_certificate = "/home/ubuntu/webhook_cert.pem"
CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"

urls = ("/.*", "hello")
app = web.application(urls, globals())
r = redis.Redis()


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        print token
        r.publish(token, web.data())
        return ''

if __name__ == "__main__":
    Listener(WebhookRegister().register_bot_by_redis, ['bots']).start()
    app.run()
