import gevent
from gevent import monkey; monkey.patch_all()
import web
from web.wsgiserver import CherryPyWSGIServer
import redis
from utils import Singleton
import telebot
from utils import Listener
from app import MasterBot


CherryPyWSGIServer.ssl_certificate = "/home/ubuntu/webhook_cert.pem"
CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"

urls = ("/.*", "hello")
app = web.application(urls, globals())
# r = redis.Redis()
mb = MasterBot({'token': open('token').read().replace('\n', '')})


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        mb.route_update(token, web.data())
        return 'ok'

if __name__ == "__main__":
    app.run()
