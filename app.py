# -*- coding: utf-8 -*-

import telebot
from telebot import types
from pyexcel_xls import get_data
from StringIO import StringIO
from validate_email import validate_email
from collections import defaultdict
from pymongo import MongoClient
import pymongo
import sendgrid
from multiprocessing import Process
from threading import Thread
import os
from sendgrid.helpers.mail import *
from datetime import datetime
import pandas as pd
import re
from views import *
from vk_crawler import Crawler
import trollius
import flask


def striphtml(data):
    p = re.compile(r'<[brai].*?>|<\/[a].*?>|<span.*?>|<\/span.*?>')
    res = p.sub('\n', data)
    return res.replace('&nbsp;', ' ').replace('&mdash;', '-')


sg = sendgrid.SendGridAPIClient(apikey=os.environ.get('SENDGRID_API_KEY'))


def send_order(mail, order):
    pass
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
    response = sg.client.mail.send.post(request_body=mail.get())
    return response


class ItemNode(View):
    def __init__(self, menu_item, _id, ctx, menu):
        self.editable = True
        self.description = menu_item['desc']
        self.img = menu_item['img']
        self.count = 0
        self.message_id = None
        self.price = int(menu_item['price'])
        self.name = menu_item['name']
        self._id = _id
        self.ctx = ctx
        self.ordered = False
        self.menu = menu
        self.menu_item = menu_item

    def to_dict(self):
        return dict(self.menu_item.items() + {'count': self.count}.items())

    def get_btn_txt(self):
        res = str(self.price) + ' руб.'
        if self.count > 0:
            res += ' ' + str(self.count) + ' шт.'
        return res

    def get_add_callback(self):
        return 'menu_item:' + str(self._id) + ':add'

    def get_basket_callback(self):
        return 'menu_item:' + str(self._id) + ':basket'

    def sub(self):
        self.count -= 1
        self.render()

    def add(self):
        self.count += 1
        self.render()

    def get_markup(self):
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton(self.get_btn_txt(), callback_data=self.get_add_callback()))
        if self.count > 0:
            markup.row(types.InlineKeyboardButton('Добавить в корзину', callback_data=self.get_basket_callback()))
        return markup

    def get_total(self):
        return self.count * self.price

    def get_msg(self):
        return (u'<a href="' + self.img + u'">' + self.name + u'</a>\n' + striphtml(self.description))[:500]

    def process_callback(self, call):
        _id, action = call.data.split(':')[1:]
        if action == 'add':
            self.count += 1
            self.render()
        if action == 'basket':
            # print 'got to basket'
            self.ordered = True
            self.menu.goto_basket(call)


class BasketNode(View):
    def __init__(self, menu):
        self.menu = menu
        self.chat_id = menu.ctx.chat_id
        self.message_id = None
        self.ctx = menu.ctx
        self.items = []
        self.item_ptr = 0
        self.editable = True
        self.ctx.current_basket = self

    def to_dict(self):
        return {
            'chat_id': self.chat_id,
            'items': [i.to_dict() for i in self.items if i.count > 0],
            'total': self.get_total()
        }

    def get_ordered_items(self):
        return filter(lambda i: i.ordered is True, self.menu.items.values())

    def activate(self):
        self.items = list(set(self.items + self.get_ordered_items()))
        self.item_ptr = 0

    def current_item(self):
        return self.items[self.item_ptr]

    def inc(self):
        if self.item_ptr + 1 < len(self.items):
            self.item_ptr += 1
            self.render()

    def dec(self):
        if self.item_ptr - 1 > -1:
            self.item_ptr -= 1
            self.render()

    def add(self):
        self.current_item().add()
        self.render()

    def sub(self):
        if self.current_item().count > 0:
            self.current_item().sub()
            self.render()

    def get_total(self):
        return sum(i.get_total() for i in self.items)

    def __str__(self):
        res = ""
        for item in self.items:
            if item.count > 0:
                res += item.name.encode('utf-8') + " " + str(item.count) + "шт. " + str(self.current_item().get_total()) + ' руб\n'
        res += 'Итого: ' + str(self.get_total()) + 'руб.'
        return res

    def get_msg(self):
        if self.get_total() > 0:
            res = 'Корзина:' + '\n\n'
            res += self.current_item().get_msg().encode('utf-8') + '\n'
            res += str(self.current_item().price) + ' * ' + str(self.current_item().count) + ' = ' + str(self.current_item().get_total()) + ' руб'
            return res
        else:
            return 'В Корзине пусто'

    def process_callback(self, call):
        action = call.data.split(':')[-1]
        # print action
        if action == '>':
            self.inc()
        elif action == '<':
            self.dec()
        elif action == '+':
            self.add()
        elif action == '-':
            self.sub()

    def get_markup(self):
        if self.get_total() > 0:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                self.btn('-', 'basket:-'),
                self.btn(str(self.current_item().count) + ' шт.', 'basket:cnt'),
                self.btn('+', 'basket:+')
            )
            markup.row(self.btn('<', 'basket:<'), self.btn(str(self.item_ptr + 1) + '/' + str(len(self.items)), 'basket:ptr'), self.btn('>', 'basket:>'))
            markup.row(self.btn('Заказ на ' + str(self.get_total()) + ' р. Оформить?', 'link:delivery'))
            return markup
        else:
            return None


class MenuNode(View):
    def __init__(self, msg, menu_items, ctx, links, parent=None):
        self.ctx = ctx
        self.msg = msg
        self.items = {}
        self.basket = self.ctx.current_basket or BasketNode(self)
        self.links = links
        self.ptr = 0
        self.editable = False
        self.parent = parent
        self.message_id = None
        cnt = 0
        for item in menu_items:
            try:
                _id = str(cnt)
                self.items[_id] = ItemNode(item, _id, self.ctx, self)
                cnt += 1
            except:
                pass

    # def activate(self):
    #     self.render()
    #     super(MenuNode, self).activate()

    def render(self):
        super(MenuNode, self).render()
        self.render_5()

    def render_5(self):
        for item in self.items.values()[self.ptr:self.ptr + 5]:
            try:
                item.render()
            except Exception, e:
                print e
        self.ptr += 5

    def process_message(self, message):
        txt = message
        if txt == 'Показать еще 5':
            self.render()
        elif txt == 'Назад':
            self.ctx.route(['menu_cat_view'])

    def get_msg(self):
        return self.msg

    def get_markup(self):
        if self.ptr + 6 < len(self.items):
            return self.mk_markup(['Показать еще 5', 'Назад'])
        else:
            return self.mk_markup(['Назад'])

    def process_callback(self, call):  # route callback to item node
        data = call.data.encode('utf-8')
        _type = data.split(':')[0]
        if _type == 'menu_item':
            node_id = data.split(':')[1]
            if node_id in self.items:
                self.items[node_id].process_callback(call)
        elif _type == 'basket':
            self.basket.process_callback(call)
        elif _type == 'link':
            ll = data.split(':')[1]
            # print ll
            if ll in self.links:
                self.ctx.route(self.links[ll])

    def goto_basket(self, call):
        self.basket.menu = self
        self.basket.message_id = None
        self.basket.activate()
        self.basket.render()


class OrderCreatorView(DetailsView):
    def __init__(self, ctx, details, final_message=""):
        super(OrderCreatorView, self).__init__(ctx, details, final_message)
        self.orders = list(self.ctx.db.orders.find({'token': self.ctx.bot.token, 'chat_id': self.ctx.chat_id}).sort('date', pymongo.DESCENDING))
        if len(self.orders) > 0:
            last_order = self.orders[0]['delivery']
        else:
            last_order = {}

        def _get(v):
            try:
                return last_order.get(v.decode('utf-8')).encode('utf-8')
            except:
                return last_order.get(v.decode('utf-8'))

        self.details = [
            TextDetail('delivery_type', ['Доставка до дома', 'Самовывоз'], name='тип доставки', ctx=self.ctx, value=_get('тип доставки')),
            TextDetail('address', name='Ваш адрес', ctx=self.ctx, value=_get('Ваш адрес')),
            TextDetail('phone', name='Ваш телефон', ctx=self.ctx, value=_get('Ваш телефон')),
            TextDetail('delivery_time', name='желаемое время доставки', ctx=self.ctx)
        ]

        # for d in self.details:
        #     print d.value, d.is_filled()

    def activate(self):
        self.filled = False
        self.ptr = 0
        super(DetailsView, self).activate()

    def finalize(self):
        # print str(self.ctx.current_basket)
        order = self.ctx.current_basket.to_dict()
        order['delivery'] = {}
        for d in self.details:
            order['delivery'][d.name] = d.txt()
        order['date'] = datetime.utcnow()
        order['status'] = 'В обработке'
        order['token'] = self.ctx.token
        order['number'] = len(self.orders) 
        self.ctx.db.orders.insert_one(order)
        send_order(self.ctx.get_bot_data()['email'], order)
        self.ctx.current_basket = None


    def activate(self):
        self.filled = False
        self.ptr = 0
        super(DetailsView, self).activate()



class UpdateBotView(BotCreatorView): # TODO: remove
    def activate(self):
        self.filled = False
        self.ptr = 0
        super(DetailsView, self).activate()

    def finalize(self):
        dd = {}
        for d in self.details:
            dd[d._id] = d.value
        bot_data = {'admin': self.ctx.bot.bot.get_chat(self.ctx.chat_id).username, 'token': dd['shop.token'], 'items': dd['shop.items'], 'email': dd['shop.email'], 'chat_id': self.ctx.chat_id, 'delivery_info': dd['shop.delivery_info'], 'contacts_info': dd['shop.contacts_info']}
        self.ctx.db.bots.update_one({'token': dd['shop.token']}, {"$set": bot_data})


class BotSettingsView(NavigationView):
    def route(self, path):  # TODO: remove this hack!
        if path == []:
            return self
        else:
            token = path[0]
            if not hasattr(self, 'views'):
                self.views = {}
            if token not in self.views:
                bot = self.ctx.db.bots.find_one({'chat_id': self.ctx.chat_id, 'token': token})
                self.views[token] = UpdateBotView(self.ctx, [
                    TokenDetail('shop.token', name='API token', ctx=self.ctx, value=bot['token']),
                    EmailDetail('shop.email', name='email для приема заказов', ctx=self.ctx, value=bot['email']),
                    FileDetail('shop.items', value=bot['items'], name='файл с описанием товаров', desc='<a href="https://github.com/0-1-0/marketbot/blob/master/sample.xlsx?raw=true">(Пример)</a>'),
                    TextDetail('shop.delivery_info', name='текст с условиями доставки', value=bot.get('delivery_info')),
                    TextDetail('shop.contacts_info', name='текст с контактами для связи', value=bot.get('contacts_info'))
                ], final_message='Магазин сохранен!')

            return self.views[token]

    def activate(self):
        self.links = {}
        self.views = {}
        for bot in self.ctx.db.bots.find({'chat_id': self.ctx.chat_id}):
            name = '@' + telebot.TeleBot(bot['token']).get_me().first_name
            self.links[name] = ['settings_view', bot['token']]
        self.links['Главное меню'] = ['main_view']
        super(BotSettingsView, self).activate()


class HistoryItem(object):
    def __init__(self, order):
        self.order = order

    def __str__(self):
        res = str(self.order.get('date')).split('.')[0] + '\n\n'
        res += '\n'.join(i['name'].encode('utf-8') + ' x ' + str(i['count']) for i in self.order['items'] )
        res += '\n-----\n Итого: ' + str(self.order['total']) + ' руб.'
        res += '\n-----\n Детали доставки: \n-----\n'
        try:
            res += '\n'.join(k.encode('utf-8') + ': ' + v.encode('utf-8') for k,v in self.order['delivery'].items())
        except:
            try:
                res += '\n'.join(k + ': ' + v for k,v in self.order['delivery'].items())
            except:
                pass
        return res


class HistoryView(NavigationView):
    def activate(self):
        self.cursor = 0
        self.orders = list(self.ctx.db.orders.find({'token': self.ctx.bot.token, 'chat_id': self.ctx.chat_id}).sort('date', pymongo.DESCENDING))
        self.links = {
            'Главное меню': ['main_view']
        }
        if len(self.orders) > 0:
            self.links['Еще 5'] = ['history']
        super(HistoryView, self).activate()

    def render_5(self):
        for order in self.orders[self.cursor:self.cursor + 5]:
            self.ctx.send_message(str(HistoryItem(order)))
        self.cursor += 5

    def process_message(self, message):
        # print message

        if message == 'Еще 5':
            self.render_5()
        if message == 'Главное меню':
            self.ctx.route(['main_view'])

    def get_msg(self):
        if len(self.orders) > 0:
            self.render_5()
            return ':)'
        else:
            return 'История заказов пуста'


class OrderNavView(NavigationView):
    def __init__(self, ctx, bot_token):
        self.ctx = ctx
        self.token = bot_token
        self.editable = True
        self.msg = 'Выберите статус заказа'
        self.links = {
            'В обработке': ['select_bot_orders_view', self.token, 'in_processing'],
            'Завершенные': ['select_bot_orders_view', self.token, 'done']
        }
        self.message_id = None
        self.views = {
            'in_processing': AdminOrderView(self.ctx, self.token, status=u'В обработке'),
            'done': AdminOrderView(self.ctx, self.token, status=u'Завершен')
        }


class SelectBotOrdersView(NavigationView):
    def route(self, path):   # TODO !
        if path == []:
            return self
        token = path[0]
        if not hasattr(self, 'views'):
            self.views = {}
        if token not in self.views:
            self.views[token] = OrderNavView(self.ctx, token)
        return self.views[token].route(path[1:])

    def activate(self):
        self.views = {}
        bots = self.ctx.db.bots.find({'chat_id': self.ctx.chat_id})
        self.links = {telebot.TeleBot(bot['token']).get_me().first_name: ['select_bot_orders_view', bot['token']] for bot in bots}
        super(SelectBotOrdersView, self).activate()


class MenuCatView(InlineNavigationView):
    def __init__(self, ctx, msg=''):
        super(MenuCatView, self).__init__(ctx, msg=msg)
        data = self.ctx.get_bot_data()['items']
        self.categories = defaultdict(list)
        for item_data in data:
            self.categories[item_data['cat']].append(item_data)
        if u'' in self.categories:
            del self.categories[u'']
        self.links = {cat: ['menu_cat_view', cat] for cat in self.categories.keys()}
        self.views = {cat: MenuNode(cat, items, self.ctx, links={"delivery": ['delivery']}) for cat, items in self.categories.items()}

    def process_message(self, cmd):
        if cmd == 'Назад' or cmd == 'Главное меню':
            self.ctx.route(['main_view'])
        else:
            super(MenuCatView, self).process_message(cmd)

    def route(self, path):
        if path == []:
            self.views = {cat: MenuNode(cat, items, self.ctx, links={"delivery": ['delivery']}) for cat, items in self.categories.items()}
        return super(MenuCatView, self).route(path)

    def render(self):
        self.ctx.send_message('Меню', markup=self.mk_markup(['Назад']))
        super(MenuCatView, self).render()


class OrderInfoView(HelpView):

    def get_msg(self):
        delivery_info = self.ctx.get_bot_data().get('delivery_info')
        if delivery_info:
            return delivery_info
        else:
            'Об условиях доставки пишите: @' + self.ctx.get_bot_data().get('admin')


class ContactsInfoView(HelpView):

    def get_msg(self):
        contacts_info = self.ctx.get_bot_data().get('contacts_info')
        if contacts_info:
            return contacts_info
        else:
            'Чтобы узнать подробности свяжитесь с @' + self.ctx.get_bot_data().get('admin')


class Convo(object):
    def __init__(self, data, bot):
        self.bot = bot
        self.token = bot.token
        self.db = bot.get_db()
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
            except:
                pass

    def log(self, txt, data=None):
        self.db.logs.insert_one({'bot_token': self.bot.token, 'chat_id': self.chat_id, 'txt': txt, 'data': data})

    def edit_message(self, message_id, msg, markup=None):
        # print self.chat_id, message_id
        # print self.bot.get_chat(self.chat_id)
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
        # print self, callback
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
        # categories = defaultdict(list)
        # for item_data in data['items']:
        #     categories[item_data['cat']].append(item_data)
        # for category, items in categories.items():
        #     self.menu_cat_view.add_child(category.encode('utf-8'), MenuNode(items, self.ctx, links={"delivery": self.delivery_view}))

        # self.menu_view = MenuNode(data, self.ctx, links={"delivery": self.delivery_view})
        self.views['history'] = HistoryView(self)
        self.views['main_view'] = NavigationView(self, links={
            "Меню": ['menu_cat_view'],
            "История": ['history'],
            "Доставка": ['order_info'],   # ,
            "Контакты": ['contacts']   # ContactsInfoView(self.ctx)
        }, msg="Главное меню")
        # self.history_view.links = {"Главное меню": self.main_view, 'Еще 5': self.history_view}
        # self.history_view.main_view = self.main_view
        # self.delivery_view.next_view = self.main_view
        # self.delivery_view.main_view = self.main_view
        # if data.get('last_message_id'):
        #     self.ctx.views[self.main_view] = data['last_message_id']
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
            FileDetail('shop.items', name='файл с описанием товаров', desc='<a href="https://github.com/0-1-0/marketbot/blob/master/sample.xlsx?raw=true">Пример</a>'),
            TextDetail('shop.delivery_info', name='текст с условиями доставки'),
            TextDetail('shop.contacts_info', name='текст с контактами для связи', value='telegram: @' + str(self.bot.bot.get_chat(self.chat_id).username))
        ], final_message='Магазин создан!')
        self.views['settings_view'] = BotSettingsView(self, msg='Настройки', links={'Главное меню': ['main_view']})
        self.views['select_bot_orders_view'] = SelectBotOrdersView(self, msg='Выберите магазин')
        # self.add_view.next_view = self.main_view
        # self.add_view.main_view = self.main_view
        # if data.get('last_message_id'):
        #     self.ctx.views[self.main_view] = data['last_message_id']
        #if data.get('current_view') and data['current_view'] in self.views:
        self.path = data.get('path')
        if not self.get_current_view():
            self.route(['main_view'])

    def start_bot(self, bot_data):
        mb = MarketBot(bot_data)
        WebhookProcessor().register_bot(mb.bot)

    def process_file(self, doc):
        # try:
        fid = doc.document.file_id
        file_info = self.bot.bot.get_file(fid)
        content = self.bot.bot.download_file(file_info.file_path)
        io = StringIO(content)
        try:
            df = pd.read_csv(io)
        except:
            excel_data = get_data(io)
            _keys = excel_data.values()[0][0]
            # print _keys
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


class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls._instance


class BotProcessor(Singleton):
    queue = set()
    updates = {}
    loop = trollius.get_event_loop()

    def register_bot(self, bot):
        self.loop.call_soon(self.get_updates, bot)

    def get_updates(self, bot):
        upd = bot.get_updates(offset=(bot.last_update_id + 1), timeout=0)
        self.loop.call_soon(self.process_updates, bot, upd)

    def process_updates(self, bot, upd):
        bot.process_new_updates(self.updates[bot.token])

    def run(self):
        self.loop.run_forever()
        loop.close()


class WebhookProcessor(Singleton):
    WEBHOOK_HOST = 'ec2-52-34-35-240.us-west-2.compute.amazonaws.com'
    WEBHOOK_PORT = 8443  # 443, 80, 88 or 8443 (port need to be 'open')
    WEBHOOK_LISTEN = '0.0.0.0'  # In some VPS you may need to put here the IP addr
    WEBHOOK_SSL_CERT = '/home/ubuntu/webhook_cert.pem'  # Path to the ssl certificate
    WEBHOOK_SSL_PRIV = '/home/ubuntu/webhook_pkey.pem'  # Path to the ssl private key
    WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)

    app = flask.Flask(__name__)

    def register_bot(self, bot):
        self.app.add_url_rule('/' + bot.token, bot.token, bot.webhook_handler)
        print 'registered bot at ' + self.WEBHOOK_URL_BASE + '/' + bot.bot.token + '/'
        bot.bot.set_webhook(url=self.WEBHOOK_URL_BASE + '/' + bot.bot.token + '/')

    def run(self):
        self.app.run(
            host=self.WEBHOOK_LISTEN,
            port=self.WEBHOOK_PORT,
            ssl_context=(self.WEBHOOK_SSL_CERT, self.WEBHOOK_SSL_PRIV),
            debug=True)


class MarketBot(object):
    convo_type = MarketBotConvo

    def __init__(self, data, bot_manager=BotProcessor()):
        self.token = data['token']
        self.data = data
        self.convos = {}
        self.db = None
        self.email = data.get('email')
        self.bot_manager = bot_manager

    def get_db(self):
        self.db = self.db or MongoClient('localhost', 27017, connect=False)
        return self.db['marketbot']

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
            self.get_db().convos.insert_one(convo_data)
            self.init_convo(convo_data)
        return self.convos[chat_id]

    def goto_main(self, message):
        convo = self.get_convo(message.chat.id)
        convo.route(['main_view'])

    def process_callback(self, callback):
        # print callback.message.chat.id
        convo = self.get_convo(callback.message.chat.id)
        convo.process_callback(callback)

    def process_message(self, message):
        convo = self.get_convo(message.chat.id)
        convo.process_message(message)

    def process_file(self, doc):
        chat_id = doc.chat.id
        # print chat_id
        convo = self.get_convo(chat_id)
        convo.process_file(doc)

    def start(self):
        self._init_bot()
        for convo_data in self.get_db().convos.find({'bot_token': self.token}):
            self.init_convo(convo_data)
        self.bot_manager.register_bot(self.bot)

    def webhook_handler(self):
        if flask.request.headers.get('content-type') == 'application/json':
            json_string = flask.request.get_data().encode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            self.bot.process_new_messages([update.message])
            return ''
        else:
            flask.abort(403)


class MasterBot(MarketBot):
    convo_type = MainConvo

    def start(self):
        self._init_bot()
        for convo_data in self.get_db().convos.find({'bot_token': self.token}):
            self.init_convo(convo_data)
        self.bot_manager.register_bot(self.bot)
        for bot_data in self.get_db().bots.find():
            try:
                m = MarketBot(bot_data)
                m.start()
            except:
                pass


# if __name__ == "__main__":
#     mb = MasterBot({'token': "203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw"})  # prod
#     mb.start()
#     WebhookProcessor().run()

