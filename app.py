# -*- coding: utf-8 -*-

import telebot
from pyexcel_xls import get_data
from StringIO import StringIO
from pymongo import MongoClient
import pandas as pd
from views import *
import redis
import json
from utils import Listener


class Convo(object):
    def __init__(self, data, bot):
        self.bot = bot
        self.redis = redis.Redis()
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

    def send_message(self, msg, markup=None):
        if self.chat_id:
            msg1 = msg.replace('<br />', '.\n')
            try:
                msg = self.bot.bot.send_message(self.chat_id, msg1, reply_markup=markup, parse_mode='HTML')
                self.log(msg1, data={'type': 'send_message', 'markup': markup.to_json()})
                self.db.convos.update_one({'bot_token': self.bot.token, 'chat_id': self.chat_id}, {'$set': {'last_message_id': msg.message_id}})
                return msg
            except Exception, e:
                print e

    def log(self, txt, data=None):
        self.db.logs.insert_one({'bot_token': self.bot.token, 'chat_id': self.chat_id, 'txt': txt, 'data': data})

    def edit_message(self, message_id, msg, markup=None):
        if self.chat_id:
            try:
                msg1 = msg.replace('<br />', '.\n')
                self.log(msg1, data={'type': 'edit_message', 'markup': markup.to_json()})
                return self.bot.bot.edit_message_text(msg1, chat_id=self.chat_id, message_id=message_id, reply_markup=markup, parse_mode='HTML')
            except:
                pass

    def process_message(self, message):
        try:
            txt = message.text.encode('utf-8')
        except:
            try:
                txt = message.contact.phone_number
            except:
                pass

        self.log(txt, data={'type': 'process_message'})
        self.get_current_view().process_message(txt)

    def process_callback(self, callback):
        self.log(callback.data, data={'type': 'process_callback'})
        self.get_current_view().process_callback(callback)

    def process_file(self, doc):
        pass

    def set_path(self, path):
        self.path = path
        self.db.convos.update_one({'bot_token': self.bot.token, 'chat_id': self.chat_id}, {'$set': {'path': path}})

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
                "Заказы": ['select_bot_orders_view'],
                "Помощь": ['help_view']
            },
            msg="Главное меню"
        )
        self.views['help_view'] = HelpView(self, links={'Главное меню': ['main_view']})
        self.views['add_view'] = BotCreatorView(self, [
            TokenDetail('shop.token', name='API token.', desc='Для этого перейдите в @BotFather и нажмите /newbot для создания бота. Придумайте название бота (должно быть на русском языке) и ссылку на бот (на английском языке и заканчиваться на bot). Далее вы увидите API token, который нужно скопировать и отправить в этот чат.', ctx=self),
            EmailDetail('shop.email', name='email для приема заказов', ctx=self),
            FileDetail('shop.items', name='файл с описанием товаров или url магазина вконтакте', desc='<a href="https://github.com/0-1-0/marketbot/blob/master/sample.xlsx?raw=true">Пример файла</a>'),
            TextDetail('shop.delivery_info', name='текст с условиями доставки'),
            TextDetail('shop.contacts_info', name='текст с контактами для связи', value='telegram: @' + str(self.bot.bot.get_chat(self.chat_id).username))
        ], final_message='Магазин создан!')
        self.views['settings_view'] = BotSettingsView(self, msg='Настройки', links={'Главное меню': ['main_view']})
        self.views['select_bot_orders_view'] = SelectBotOrdersView(self, msg='Выберите магазин')
        self.path = data.get('path')
        if not self.get_current_view():
            self.route(['main_view'])

    def process_file(self, doc):
        fid = doc.document.file_id
        file_info = self.bot.bot.get_file(fid)
        content = self.bot.bot.download_file(file_info.file_path)
        io = StringIO(content)
        try:
            df = pd.read_csv(io)
        except:
            excel_data = get_data(io)
            _keys = excel_data.values()[0][0]
            _values = excel_data.values()[0][1:]
            _items = [dict(zip(_keys, rec)) for rec in _values]
            df = pd.DataFrame(_items)

        df_keys = {k.lower(): k for k in df.to_dict().keys()}
        data = pd.DataFrame()

        mapping = {
            'id': ['id', 'product_id'],
            'active': ['active', 'visible', u'активно'],
            'cat': ['category', u'раздел 1', u'категория'],
            'name': [u'наименование', 'name'],
            'desc': [u'описание', 'description', 'description(html)'],
            'price': ['price', u'цена'],
            'img': ['img_url', u'изображение', u'ссылка на изображение']
        }

        for k, values in mapping.items():
            for col_name in values:
                if col_name in df_keys:
                    data[k] = df[df_keys[col_name]]

        data['active'] = data['active'].map(lambda x: '1' if x in [1, 'y'] else '0')
        items = data.T.to_dict().values()
        # print items
        if len(items) == 0:
            raise Exception("no items added")

        self.tmpdata = items


class MarketBot(object):
    convo_type = MarketBotConvo

    def __init__(self, data, bot_manager, db=MongoClient('localhost', 27017, connect=False)['marketbot']):
        self.token = data['token']
        self.data = data
        self.convos = {}
        self.db = db
        self.email = data.get('email')
        self.bot_manager = bot_manager

    def _init_bot(self, threaded=False):
        self.bot = telebot.TeleBot(self.token, threaded=threaded, skip_pending=True)
        self.bot.add_message_handler(self.goto_main, commands=['start'])
        self.bot.add_callback_query_handler(self.process_callback, func=lambda call: True)
        self.bot.add_message_handler(self.process_file, content_types=['document'])
        self.bot.add_message_handler(self.process_message, func=lambda message: True, content_types=['text', 'contact'])

    def init_convo(self, convo_data):
        convo_data = dict(self.data.items() + convo_data.items())
        self.convos[convo_data['chat_id']] = self.convo_type(convo_data, self)

    def get_convo(self, chat_id):
        if chat_id not in self.convos:
            convo_data = {'chat_id': chat_id, 'bot_token': self.token}
            self.db.convos.insert_one(convo_data)
            self.init_convo(convo_data)
        return self.convos[chat_id]

    def start_bot(self, bot_data):
        MarketBot(bot_data, self.bot_manager, self.db).start()

    def goto_main(self, message):
        convo = self.get_convo(message.chat.id)
        convo.route(['main_view'])

    def process_callback(self, callback):
        convo = self.get_convo(callback.message.chat.id)
        convo.process_callback(callback)

    def process_message(self, message):
        convo = self.get_convo(message.chat.id)
        convo.process_message(message)

    def process_file(self, doc):
        convo = self.get_convo(doc.chat.id)
        convo.process_file(doc)

    def start(self):
        self._init_bot()
        for convo_data in self.db.convos.find({'bot_token': self.token}):
            self.init_convo(convo_data)
        self.bot_manager.register_bot(self.bot)


class MasterBot(MarketBot):
    convo_type = MainConvo

    def process_vk_output(self, data):
        try:
            data = json.loads(data['data'])
            convo = self.get_convo(data['chat_id'])
            convo.tmpdata = data['data']
            print convo.get_current_view()
            convo.get_current_view().process_message('ОК')
        except Exception, e:
            print e

    def start(self):
        super(MasterBot, self).start()

        for bot_data in self.db.bots.find():
            try:
                self.start_bot(bot_data)
            except Exception, e:
                print e
