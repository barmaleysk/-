import web
from web.wsgiserver import CherryPyWSGIServer
from app import MasterBot, MarketBot
import telebot

CherryPyWSGIServer.ssl_certificate = "/home/ubuntu/webhook_cert.pem"
CherryPyWSGIServer.ssl_private_key = "/home/ubuntu/webhook_pkey.pem"

urls = ("/.*", "hello")
app = web.application(urls, globals())

mb = MasterBot({'token': "203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw"}) 
mb.start()


class hello:
    def POST(self):
        token = web.ctx.path.split('/')[1]
        data = web.data()
        update = telebot.types.Update.de_json(data.encode('utf-8'))
        mb.process_updates([update])
        return '!'

if __name__ == "__main__":
    app.run()