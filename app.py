# -*- coding: utf-8 -*-
import gevent
from gevent import monkey; monkey.patch_all()
import telebot
from telebot import apihelper
from pymongo import MongoClient
from views import *
from utils import get_address
import botan
import time

botan_token = 'BLe0W1GY8SwbNijJ0H-lroERrA9BnK0t'


class Convo(object):
    def __init__(self, data, bot):
        self.bot = bot
        self.token = bot.token
        self.db = bot.db
        self.chat_id = data['chat_id']
        self.views = {}
        self.path = data.get('path')
        self.tmpdata = None

    def get_current_view(self):
        if self.path and self.path[0] in self.views:
            return self.views[self.path[0]].route(self.path[1:])
        return None

    def get_bot_data(self):
        return self.db.bots.find_one({'token': self.token})

    def _send_msg(self, msg1, markup):
        try:
            apihelper.send_message(self.token, self.chat_id, msg1, reply_markup=markup, parse_mode='HTML')
        except Exception, e:
            self.bot.log_error({'func': '_send_msg', 'token': self.token, 'chat_id': self.chat_id, 'message': msg1, 'error': str(e)})

    def send_message(self, msg, markup=None):
        if self.chat_id:
            msg1 = msg.replace('<br />', '.\n')
            gevent.spawn(self._send_msg, msg1, markup)
            return

    def edit_message(self, message_id, msg, markup=None):
        if self.chat_id:
            msg1 = msg.replace('<br />', '.\n')
            gevent.spawn(apihelper.edit_message_text, self.token, msg1, self.chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            return

    def process_message(self, message):
        try:
            txt = message.text.encode('utf-8')
        except:
            if hasattr(message, 'contact') and message.contact is not None:
                txt = message.contact.phone_number
            if hasattr(message, 'location') and message.location is not None:
                txt = get_address(message.location.latitude, message.location.longitude).encode('utf-8')
                if txt:
                    self.send_message(txt)
        self.get_current_view().process_message(txt)

    def process_photo(self, photo):
        self.get_current_view().process_photo(photo)

    def process_sticker(self, sticker):
        self.get_current_view().process_sticker(sticker)

    def process_video(self, video):
        self.get_current_view().process_video(video)

    def process_callback(self, callback):
        self.get_current_view().process_callback(callback)

    def process_file(self, doc):
        self.get_current_view().process_file(doc)

    def set_path(self, path):
        self.path = path
        gevent.spawn(self.db.convos.update_one, {'bot_token': self.bot.token, 'chat_id': self.chat_id}, {'$set': {'path': path}})

    def route(self, path):
        self.set_path(path)
        self.get_current_view().activate()


class MarketBotConvo(Convo):
    def __init__(self, data, bot):
        super(MarketBotConvo, self).__init__(data, bot)
        self.current_basket = None
        self.views['delivery'] = OrderCreatorView(self, [], final_message='Заказ сформирован!')
        self.views['menu_cat_view'] = MenuCatView(self, msg="Выберите категорию:")
        self.views['order_info'] = OrderInfoView(self, msg="Тут должны быть условия доставки", links={'Главное меню': ['main_view']})
        self.views['contacts'] = ContactsInfoView(self, links={'Главное меню': ['main_view']})
        self.views['history'] = HistoryView(self)
        self.views['main_view'] = NavigationView(self, links={
            "Меню": ['menu_cat_view'],
            "История": ['history'],
            "Доставка": ['order_info'],   # ,
            "Контакты": ['contacts']   # ContactsInfoView(self.ctx)
        }, msg="Главное меню")
        self.path = data.get('path')
        if not self.get_current_view():
            self.route(['main_view'])


class MainConvo(Convo):
    def __init__(self, data, bot):
        super(MainConvo, self).__init__(data, bot)
        self.views['main_view'] = NavigationView(
            self,
            links={
                "Добавить магазин": ['add_view'],
                "Настройки": ['settings_view'],
                "Заказы": ['orders_view'],
                "Помощь": ['help_view'],
                "Рассылка новостей": ['mailing_view']
            },
            msg="Главное меню"
        )
        self.views['help_view'] = HelpView(self, links={'Назад': ['main_view']})
        self.views['add_view'] = BotCreatorView(self, [
            TokenDetail('shop.token', name='API token.', desc='Для этого перейдите в @BotFather и нажмите /newbot для создания бота. Придумайте название бота (должно быть на русском языке) и ссылку на бот (на английском языке и заканчиваться на bot). Далее вы увидите API token, который нужно скопировать и отправить в этот чат.', ctx=self),
            EmailDetail('shop.email', name='email для приема заказов', ctx=self),
            FileDetail('shop.items', name='файл с описанием товаров или url магазина вконтакте', desc='<a href="https://github.com/0-1-0/marketbot/blob/master/sample.xlsx?raw=true">Пример файла</a>'),
            TextDetail('shop.delivery_info', name='текст с условиями доставки'),
            TextDetail('shop.contacts_info', name='текст с контактами для связи', value='telegram: @' + str(self.bot.bot.get_chat(self.chat_id).username)),
            NumberDetail('shop.total_threshold', name='минимальную сумму заказа', value='0')
        ], final_message='Магазин создан!')
        self.views['settings_view'] = SelectBotView(self, bot_view={'link': 'settings_view', 'view': SettingsView})
        self.views['orders_view'] = SelectBotView(self, bot_view={'link': 'orders_view', 'view': OrdersView})
        self.views['mailing_view'] = SelectBotView(self, bot_view={'link': 'mailing_view', 'view': MailingView})
        self.path = data.get('path')
        if not self.get_current_view():
            self.route(['main_view'])


class Bot(object):
    bots = {}
    WEBHOOK_HOST = 'ec2-52-34-35-240.us-west-2.compute.amazonaws.com'
    WEBHOOK_PORT = 8443
    WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
    WEBHOOK_SSL_CERT = '/home/ubuntu/webhook_cert.pem'

    def __init__(self, token):
        self.token = token
        Bot.bots[self.token] = self
        gevent.spawn(self.set_webhook, self.token)

    def log_error(self, e):
        pass

    def set_webhook(self, token, retries=0):
        try:
            bot = telebot.TeleBot(token)
            bot.remove_webhook()
            bot.set_webhook(url=self.WEBHOOK_URL_BASE + '/' + bot.token + '/', certificate=open(self.WEBHOOK_SSL_CERT, 'r'))
            print token, 'registered'
        except Exception, e:
            self.log_error(e)
            print token, e
            if retries < 2:
                time.sleep(1)
                self.set_webhook(token, retries+1)



class MarketBot(Bot):
    convo_type = MarketBotConvo

    def __init__(self, data, db=MongoClient()['marketbot']):
        super(MarketBot, self).__init__(data['token'])

        self.convos = {}
        self.db = db
        if not self.db.bots.update_one({'token': self.token}, {'$set': apihelper.get_me(self.token)}):
            self.db.bots.insert_one({'token': self.token})
        self.email = data.get('email')
        self.last_update_id = data.get('last_update_id') or 0
        self._init_bot()
        for convo_data in self.db.convos.find({'bot_token': self.token}):
            self.init_convo(convo_data)

    def log_error(self, e):
        gevent.spawn(self.db.errors.insert_one, {'error': str(e)})

    def _init_bot(self, threaded=False):
        self.bot = telebot.TeleBot(self.token, threaded=threaded, skip_pending=True)
        self.bot.add_message_handler(self.goto_main, commands=['start'])
        self.bot.add_callback_query_handler(self.process_callback, func=lambda call: True)
        self.bot.add_message_handler(self.process_photo, content_types=['photo'])
        self.bot.add_message_handler(self.process_video, content_types=['video'])
        self.bot.add_message_handler(self.process_sticker, content_types=['sticker'])
        self.bot.add_message_handler(self.process_file, content_types=['document'])
        self.bot.add_message_handler(self.process_message, func=lambda message: True, content_types=['text', 'contact', 'location'])

    def init_convo(self, convo_data):
        self.convos[convo_data['chat_id']] = self.convo_type(convo_data, self)

    def get_convo(self, chat_id):
        if chat_id not in self.convos:
            convo_data = {'chat_id': chat_id, 'bot_token': self.token}
            self.db.convos.insert_one(convo_data)
            self.init_convo(convo_data)
        return self.convos[chat_id]

    def goto_main(self, message):
        convo = self.get_convo(message.chat.id)
        convo.route(['main_view'])

    def process_callback(self, callback):
        convo = self.get_convo(callback.message.chat.id)
        gevent.spawn(convo.process_callback, callback)

    def process_message(self, message):
        convo = self.get_convo(message.chat.id)
        gevent.spawn(convo.process_message, message)

    def start_bot(self, bot_data):
        MarketBot(bot_data, self.db)

    def process_file(self, doc):
        convo = self.get_convo(doc.chat.id)
        convo.process_file(doc)

    def process_sticker(self, sticker):
        convo = self.get_convo(sticker.chat.id)
        convo.process_sticker(sticker)

    def process_video(self, video):
        convo = self.get_convo(video.chat.id)
        convo.process_video(video)

    def process_photo(self, photo):
        convo = self.get_convo(photo.chat.id)
        gevent.spawn(convo.process_photo, photo)

    def update_last_id(self):
        self.db.bots.update_one({'token': self.token}, {'$set': {'last_update_id': self.last_update_id}})

    def process_redis_update(self, update):
        if isinstance(update, basestring):
            update = telebot.types.Update.de_json(update.encode('utf-8'))
            if update.update_id > self.last_update_id:
                self.last_update_id = update.update_id
                gevent.spawn(self.bot.process_new_updates, [update])
                gevent.spawn(self.update_last_id)


class MasterBot(MarketBot):
    convo_type = MainConvo

    def process_message(self, message):
        gevent.spawn(botan.track, botan_token, message.chat.id, {'from_user': message.from_user.username}, message.text)
        super(MasterBot, self).process_message(message)

    def __init__(self, data):
        super(MasterBot, self).__init__(data)

        for bot_data in self.db.bots.find():
            if bot_data['token'] != self.token:
                try:
                    MarketBot(bot_data, self.db)
                except Exception, e:
                    self.log_error(e)

    def route_update(self, token, update):
        if token in Bot.bots:
            gevent.spawn(Bot.bots[token].process_redis_update, update)
            return

if __name__ == "__main__":
    m = MasterBot({'token': open('token').read().replace('\n', '')})
    gevent.spawn(m.run).join()
