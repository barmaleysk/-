# -*- coding: utf-8 -*-

import sendgrid
import os
from sendgrid.helpers.mail import *
import re
import requests
import json


def get_address(lat, lng):
    resp = requests.get('http://maps.googleapis.com/maps/api/geocode/json?latlng=' + str(lat) + ',' + str(lng) + '&language=ru')
    return json.loads(resp.content).get('results')[0].get('formatted_address')


class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls._instance


class Mailer(Singleton):
    sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))

    def send(self, mail, subj, txt):
        from_email = Email("order@botmarket.com")
        subject = subj
        to_email = Email(mail)
        content = Content("text/plain", txt)
        mail = Mail(from_email, subject, to_email, content)
        return self.sg.client.mail.send.post(request_body=mail.get())

    def send_order(self, mail, order):
        res = 'Заказ\n====\n\n\n'
        res += '\n'.join(i['name'].encode('utf-8') + ' x ' + str(i['count']) for i in order['items'])
        res += '\n-----\n Итого: ' + str(order['total']) + ' руб.'
        res += '\n-----\n Детали доставки: \n'
        try:
            res += '\n\n'.join(k.encode('utf-8') + ': ' + v.encode('utf-8') for k, v in order['delivery'].items())
        except:
            res += '\n\n'.join(k + ': ' + v for k, v in order['delivery'].items())
        res = res.replace('Ваш', '')
        return self.send(mail, 'Новый заказ!', res)


def striphtml(data):
    p = re.compile(r'<[brai].*?>|<\/[a].*?>|<span.*?>|<\/span.*?>')
    res = p.sub('\n', data)
    return res.replace('&nbsp;', ' ').replace('&mdash;', '-')
