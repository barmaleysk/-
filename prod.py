#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This is a simple echo bot using decorators and webhook with flask
# It echoes any incoming text messages and does not use the polling method.

import flask
import telebot
import logging
from app import MasterBot, Singleton


# API_TOKEN = '203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw'

WEBHOOK_HOST = 'ec2-52-34-35-240.us-west-2.compute.amazonaws.com'
WEBHOOK_PORT = 8443  # 443, 80, 88 or 8443 (port need to be 'open')
WEBHOOK_LISTEN = '0.0.0.0'  # In some VPS you may need to put here the IP addr

WEBHOOK_SSL_CERT = '/home/ubuntu/webhook_cert.pem'  # Path to the ssl certificate
WEBHOOK_SSL_PRIV = '/home/ubuntu/webhook_pkey.pem'  # Path to the ssl private key

# Quick'n'dirty SSL certificate generation:
#
# openssl genrsa -out webhook_pkey.pem 2048
# openssl req -new -x509 -days 3650 -key webhook_pkey.pem -out webhook_cert.pem
#
# When asked for "Common Name (e.g. server FQDN or YOUR name)" you should reply
# with the same value in you put in WEBHOOK_HOST

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
# WEBHOOK_URL_PATH = "/%s/" % (API_TOKEN)


logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

app = flask.Flask(__name__)
bots = {}


class WebhookProcessor(Singleton):

    def register_bot(self, bot):
        bot.remove_webhook()
        print 'registered bot at ', WEBHOOK_URL_BASE + '/' + bot.token + '/'
        bot.set_webhook(url=WEBHOOK_URL_BASE + '/' + bot.token + '/', certificate=open(WEBHOOK_SSL_CERT, 'r'))

    def get_bot(self, token):
        if token in bots:
            return bots[token]
        return None

mb = MasterBot({'token': "203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw"})
mb.bot_manager = WebhookProcessor()


# Empty webserver index, return nothing, just http 200
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return ''


# Process webhook calls
@app.route('/<token>/', methods=['POST'])
def webhook(token):
    print 'ok!'
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().encode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        mb.route(token).process_new_messages([update.message])
        # if token in bots:
        #     bots[token].process_new_messages([update.message])
        return ''
    else:
        flask.abort(403)


# # Remove webhook, it fails sometimes the set if there is a previous webhook
# bot.remove_webhook()

# # Set webhook
# print bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH,
                # certificate=open(WEBHOOK_SSL_CERT, 'r'))

if __name__ == "__main__":
    mb.start()

    # Start flask server
    app.run(
        host=WEBHOOK_LISTEN,
        port=WEBHOOK_PORT,
        ssl_context=(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV),
        debug=True)
