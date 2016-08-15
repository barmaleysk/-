from gevent import monkey; monkey.patch_all()
import web
from web.wsgiserver import CherryPyWSGIServer
from app import MasterBot


CherryPyWSGIServer.ssl_certificate = "/home/ubuntu/webhook_cert.pem"
CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"

urls = ("/.*", "hello")
app = web.application(urls, globals())
mb = MasterBot({'token': open('token').read().replace('\n', '')})


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        mb.route_update(token, web.data())
        return 'ok'

if __name__ == "__main__":
    app.run()
