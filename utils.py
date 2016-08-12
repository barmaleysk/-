# -*- coding: utf-8 -*-

import sendgrid
import os
from sendgrid.helpers.mail import *
import re
import threading
from vk_crawler import Crawler
import redis


class Listener(threading.Thread):
    def __init__(self, worker_func, channels, r=redis.Redis()):
        threading.Thread.__init__(self)
        self.daemon = True
        self.redis = r
        self.worker_func = worker_func
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)

    def run(self):
        for item in self.pubsub.listen():
            if item['data'] == "KILL":
                self.pubsub.unsubscribe()
                print self, "unsubscribed and finished"
                break
            else:
                self.worker_func(item)


class VKListener(Listener):

    def __init__(self):
        super(VKListener, self).__init__(self.crawl, ['vk_input'])

    def crawl(self, data):
        print 'worker got data', data
        try:
            data = json.loads(data['data'])
            url = data['url']
            chat_id = data['chat_id']
            res = Crawler(url).fetch()
            self.redis.publish('vk_output', json.dumps({'chat_id': chat_id, 'data': res}))
        except Exception, e:
            print e


class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls._instance


class Mailer(Singleton):
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))

    def send_order(self, mail, order):
        from_email = Email("order@botmarket.com")
        subject = "Новый заказ!"
        to_email = Email(mail)
        res = 'Заказ\n====\n\n\n'
        res += '\n'.join(i['name'].encode('utf-8') + ' x ' + str(i['count']) for i in order['items'])
        res += '\n-----\n Итого: ' + str(order['total']) + ' руб.'
        res += '\n-----\n Детали доставки: \n'
        res += '\n\n'.join(k + ': ' + v for k, v in order['delivery'].items())
        res = res.replace('Ваш', '')
        content = Content("text/plain", res)
        mail = Mail(from_email, subject, to_email, content)
        response = self.sg.client.mail.send.post(request_body=mail.get())
        return response


def striphtml(data):
    p = re.compile(r'<[brai].*?>|<\/[a].*?>|<span.*?>|<\/span.*?>')
    res = p.sub('\n', data)
    return res.replace('&nbsp;', ' ').replace('&mdash;', '-')
