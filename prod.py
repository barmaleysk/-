import web
from web.wsgiserver import CherryPyWSGIServer
import redis

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
    app.run()
