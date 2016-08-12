# -*- coding: utf-8 -*-

import sendgrid
import os
from sendgrid.helpers.mail import *
import re


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
