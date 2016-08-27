# -*- coding: utf-8 -*-

from collections import OrderedDict
import gevent
from gevent import monkey; monkey.patch_all()
from telebot import types
import telebot
from telebot import apihelper
from validate_email import validate_email
import pymongo
from io import BytesIO
from StringIO import StringIO
from datetime import datetime
from utils import Mailer, striphtml
from collections import defaultdict
from vk_crawler import Crawler
from pyexcel_xls import get_data
import pandas as pd
import md5
from datetime import datetime


class MarkupMixin(object):
    def mk_markup(self, command_list):
        markup = types.ReplyKeyboardMarkup(row_width=2)
        btns = [self.BTN(cmd) for cmd in command_list]
        for btn in btns[:min(3, len(btns))]:
            markup.row(btn)

        markup.add(*btns[3:])
        return markup

    def BTN(self, txt, request_contact=None, request_location=None):
        return types.KeyboardButton(txt, request_contact=request_contact, request_location=request_location)

    def mk_inline_markup(self, command_list):
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(cmd, callback_data=cmd) for cmd in command_list]
        for btn in btns:
            markup.row(btn)
        return markup

    def btn(self, txt, callback_data):
        return types.InlineKeyboardButton(txt, callback_data=callback_data)


class View(MarkupMixin):
    def __init__(self, ctx, editable=True, msg=''):
        self.ctx = ctx
        self.editable = editable
        self.active = False
        self.message_id = None
        self.msg = msg
        self.views = {}

    def route(self, path):
        if path == []:
            return self
        else:
            return self.get_subview(path[0]).route(path[1:])

    def get_subview(self, _id):
        return self.views.get(_id) or self

    def process_message(self, message):
        pass

    def process_callback(self, callback):
        pass

    def process_photo(self, photo):
        pass

    def process_file(self, doc):
        pass

    def process_sticker(self, sticker):
        pass

    def process_video(self, video):
        pass

    def activate(self):
        self.deactivate()
        for v in self.ctx.views.values():
            v.deactivate()
        self.active = True
        self.render()

    def deactivate(self):
        self.active = False
        self.message_id = None

    def get_msg(self):
        return self.msg

    def get_markup(self):
        return None

    def render(self):
        if not (self.editable and self.message_id):
            self.ctx.send_message(self.get_msg(), self.get_markup())
        else:
            self.ctx.edit_message(self.message_id, self.get_msg(), self.get_markup())


class NavigationView(View):
    def __init__(self, ctx, links={}, msg=""):
        self.links = links
        super(NavigationView, self).__init__(ctx, False, msg)

    def get_markup(self):
        return self.mk_markup([l.decode('utf-8') for l in self.links.keys()])

    def process_message(self, message):
        if message in self.links:
            self.ctx.route(self.links[message])


class InlineNavigationView(NavigationView):
    def get_markup(self):
        markup = types.InlineKeyboardMarkup(row_width=2)
        for k in self.links.keys():
            markup.row(self.btn(k, callback_data=k))
        return markup

    def process_callback(self, callback):
        cmd = callback.data
        self.message_id = callback.message.message_id
        self.process_message(cmd)


class OrderView(View):
    def __init__(self, ctx, data):
        self.ctx = ctx
        self.data = data
        self.editable = True
        self.message_id = None

    def get_msg(self):
        res = 'Заказ #' + str(self.data['number']) + '\n'
        res += 'Статус: ' + self.data['status'].encode('utf-8') + '\n'
        res += '\n'.join(i['name'].encode('utf-8') + ' x ' + str(i['count']) for i in self.data['items'])
        res += '\n-----\n Итого: ' + str(self.data['total']) + ' руб.'
        res += '\n-----\n Детали доставки: \n'
        res += '\n\n'.join(k.encode('utf-8') + ': ' + v.encode('utf-8') for k, v in self.data['delivery'].items())
        res = res.replace('Ваш', '')
        return res

    def get_markup(self):
        markup = types.InlineKeyboardMarkup(row_width=2)
        if self.data['status'] == u'В обработке':
            markup.row(self.btn(u'Завершить', str(self.data['number']) + ':complete'))
        else:
            markup.row(self.btn(u'Перенести в обработку', str(self.data['number']) + ':reactivate'))
        return markup

    def process_callback(self, callback):
        action = callback.data.split(':')[1]
        self.message_id = callback.message.message_id

        if action == 'complete':
            self.ctx.db.orders.update_one({'_id': self.data['_id']}, {'$set': {'status': 'Завершен'}})
            self.data = self.ctx.db.orders.find_one({'_id': self.data['_id']})
            self.render()
        elif action == 'reactivate':
            self.ctx.db.orders.update_one({'_id': self.data['_id']}, {'$set': {'status': 'В обработке'}})
            self.data = self.ctx.db.orders.find_one({'_id': self.data['_id']})
            self.render()


class AdminOrderView(View):
    def __init__(self, ctx, bot_token, status=u'В обработке'):
        self.ctx = ctx
        self.token = bot_token
        self.editable = True
        self.status = status
        self.orders = [OrderView(self.ctx, o) for o in self.ctx.db.orders.find({'token': self.token, 'status': status}).sort('date', pymongo.DESCENDING)]
        self._orders = {}
        for o in self.orders:
            self._orders[str(o.data['number'])] = o

    def render(self):
        if len(self.orders) > 0:
            self.ctx.send_message('Заказы', markup=self.mk_markup(['Еще 5', 'Главное меню']))
        else:
            self.ctx.send_message('Нет заказов', markup=self.mk_markup(['Главное меню']))
        self.ptr = 0
        self.render_5()

    def render_5(self):
        for order in self.orders[self.ptr: self.ptr + 5]:
            order.render()
        self.ptr += 5

    def process_message(self, message):
        if message == 'Главное меню':
            self.ctx.route(['main_view'])
        elif message == 'Еще 5':
            self.render_5()

    def process_callback(self, callback):
        data = callback.data.encode('utf-8')
        number, action = data.split(':')
        self._orders[number].process_callback(callback)


class DetailsView(View):
    def __init__(self, ctx, details, final_message=""):
        self.ctx = ctx
        self.details = details
        self.ptr = 0
        self.editable = False
        self.filled = False
        self.final_message = final_message

    def activate(self):
        self.filled = False
        for d in self.details:
            d.value = None
        self.ptr = 0
        super(DetailsView, self).activate()

    def details_dict(self):
        return {d._id: d.value for d in self.details}

    def prefinalize(self):
        pass

    def finalize(self):
        pass

    def current(self):
        return self.details[self.ptr]

    def get_msg(self):
        if self.filled:
            res = self.final_message + '\n'
            if not isinstance(self, BotCreatorView):  # TODO /hack
                for d in self.details:
                    res += (d.name + ": " + d.txt() + '\n')
            return res
        else:
            res = 'Укажите ' + self.current().name
            if self.current().is_filled():
                try:
                    res += '\n(Сейчас: ' + self.current().value + ' )'
                except:
                    try:
                        res += '\n(Сейчас: ' + self.current().value.encode('utf-8') + ' )'
                    except:
                        pass
            res += '\n' + self.current().desc
            return res

    def get_markup(self):
        if not self.filled:
            markup = types.ReplyKeyboardMarkup()
            if self.current().is_filled() or isinstance(self.current(), FileDetail):
                markup.row(self.BTN('ОК'))
            if self.current()._id == 'phone':
                markup.row(self.BTN('отправить номер', request_contact=True))
            if self.current()._id == 'address':
                markup.row(self.BTN('отправить геолокацию', request_location=True))
            if len(self.current().default_options) > 0:
                markup.row(*[self.BTN(opt) for opt in self.current().default_options])
            if self.ptr > 0:
                markup.row(self.BTN('Назад'))

            markup.row(self.BTN('Главное меню'))

            return markup
        else:
            return None

    def next(self):
        if self.ptr + 1 < len(self.details):
            if self.current().is_filled():
                self.ptr += 1
            self.render()
        else:
            self.filled = True
            self.prefinalize()
            self.render()
            self.ctx.route(['main_view'])
            self.finalize()

    def prev(self):
        if self.ptr > 0:
            self.ptr -= 1
            self.render()

    def analyze_vk_link(self, url):
        self.ctx.tmpdata = Crawler(url).fetch()
        self.process_message('ОК')

    def process_message(self, cmd):
        if cmd == 'ОК':
            if isinstance(self.current(), FileDetail) and self.ctx.tmpdata is not None:
                if self.current().validate(self.ctx.tmpdata):
                    self.current().value = self.ctx.tmpdata
                    self.ctx.tmpdata = None
                    self.next()
                else:
                    self.ctx.send_message('Неверный формат файла')
            elif self.current().is_filled():
                self.next()
            else:
                self.render()
        elif cmd == 'Назад':
            self.prev()
        elif cmd == 'Главное меню':
            self.ctx.route(['main_view'])
        elif isinstance(self.current(), TextDetail):
            if self.current().validate(cmd):
                self.current().value = cmd
                self.next()
            else:
                self.ctx.send_message('Неверный формат')
        elif isinstance(self.current(), NumberDetail):
            if self.current().validate(cmd):
                self.current().value = cmd
                self.next()
            else:
                self.ctx.send_message('Введите целое число')
        elif isinstance(self.current(), FileDetail):
            if 'vk.com' in cmd:
                try:
                    # self.ctx.redis.publish('vk_input', json.dumps({'token': self.ctx.token, 'chat_id': self.ctx.chat_id, 'url': cmd}))
                    gevent.spawn(self.analyze_vk_link, cmd)
                    self.ctx.send_message('Анализирую..')
                    self.ctx.tmpdata = None
                except Exception:
                    self.ctx.send_message('Неверный формат магазина')


class BotCreatorView(DetailsView):
    def prefinalize(self):
        self._final_message = self.final_message
        self.final_message += '\n Ссылка на бота: @' + telebot.TeleBot(self.details_dict()['shop.token']).get_me().username.encode('utf-8')

    def bot_data(self):
        dd = self.details_dict()
        return {
            'admin': self.ctx.bot.bot.get_chat(self.ctx.chat_id).username,
            'token': dd['shop.token'],
            'items': dd['shop.items'],
            'email': dd['shop.email'],
            'chat_id': self.ctx.chat_id,
            'delivery_info': dd['shop.delivery_info'],
            'contacts_info': dd['shop.contacts_info'],
            'total_threshold': dd['shop.total_threshold']
        }

    def finalize(self):
        self.final_message = self._final_message
        bot_data = self.bot_data()
        self.ctx.db.bots.save(bot_data)
        self.ctx.bot.start_bot(bot_data)

    def process_file(self, doc):
        fid = doc.document.file_id
        file_info = self.ctx.bot.bot.get_file(fid)
        file_format = file_info.file_path.split('.')[-1]
        if file_format in ['csv', 'xls', 'xlsx']:
            content = self.ctx.bot.bot.download_file(file_info.file_path)
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
            if len(items) == 0:
                raise Exception("no items added")

            self.ctx.tmpdata = items
        else:
            pass


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
        self.message_id = call.message.message_id
        _id, action = call.data.split(':')[1:]
        if action == 'add':
            self.count += 1
            self.render()
        if action == 'basket':
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
        self.total_threshold = int(self.ctx.get_bot_data().get('total_threshold') or 0)
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
        self.message_id = call.message.message_id
        action = call.data.split(':')[-1]
        if action == '>':
            self.inc()
        elif action == '<':
            self.dec()
        elif action == '+':
            self.add()
        elif action == '-':
            self.sub()
        elif action == '<<':
            self.ctx.send_message('Минимальная сумма заказа ' + str(self.total_threshold) + ' рублей')

    def get_markup(self):
        if self.get_total() > 0:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                self.btn('-', 'basket:-'),
                self.btn(str(self.current_item().count) + ' шт.', 'basket:cnt'),
                self.btn('+', 'basket:+')
            )
            markup.row(self.btn('<', 'basket:<'), self.btn(str(self.item_ptr + 1) + '/' + str(len(self.items)), 'basket:ptr'), self.btn('>', 'basket:>'))
            if self.get_total() < self.total_threshold:
                markup.row(self.btn('Минимальная сумма заказа ' + str(self.total_threshold) + ' рублей', 'basket:<<'))
            else:
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
            except Exception:
                pass

    def render(self):
        super(MenuNode, self).render()
        self.render_5()

    def render_5(self):
        for item in self.items.values()[self.ptr:self.ptr + 5]:
            try:
                item.render()
            except Exception:
                pass
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
        self.message_id = call.message.message_id
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

    def activate(self):
        self.filled = False
        self.ptr = 0
        super(DetailsView, self).activate()

    def finalize(self):
        order = self.ctx.current_basket.to_dict()
        order['delivery'] = {}
        for d in self.details:
            order['delivery'][d.name] = d.txt()
        order['date'] = datetime.utcnow()
        order['status'] = 'В обработке'
        order['token'] = self.ctx.token
        order['number'] = len(self.orders)
        self.ctx.db.orders.insert_one(order)
        gevent.spawn(Mailer().send_order, self.ctx.get_bot_data()['email'], order)
        self.ctx.current_basket = None


class UpdateBotView(BotCreatorView):
    def __init__(self, ctx, token, details, final_message=""):
        self.token = token
        super(UpdateBotView, self).__init__(ctx, details, final_message=final_message)

    def activate(self):
        self.filled = False
        self.ptr = 0
        super(DetailsView, self).activate()

    def get_markup(self):
        markup = types.ReplyKeyboardMarkup()
        if isinstance(self.current(), FileDetail):
            markup.row(self.BTN('ОК'))
        if self.current()._id == 'phone':
            markup.row(self.BTN('отправить номер', request_contact=True))
        if self.current()._id == 'address':
            markup.row(self.BTN('отправить геолокацию', request_location=True))
        if len(self.current().default_options) > 0:
            markup.row(*[self.BTN(opt) for opt in self.current().default_options])
        markup.row(self.BTN('Назад'))
        return markup

    def process_message(self, cmd):
        if cmd == 'ОК':
            if isinstance(self.current(), FileDetail) and self.ctx.tmpdata is not None:
                if self.current().validate(self.ctx.tmpdata):
                    self.current().value = self.ctx.tmpdata
                    self.ctx.tmpdata = None
                    self.next()
                else:
                    self.ctx.send_message('Неверный формат файла')
            elif self.current().is_filled():
                self.finalize()
                self.ctx.route(['settings_view', self.token])
            else:
                self.render()
        elif cmd == 'Назад':
            self.ctx.route(['settings_view', self.token])
        elif cmd == 'Главное меню':
            self.ctx.route(['main_view'])
        elif isinstance(self.current(), TextDetail):
            if self.current().validate(cmd):
                self.current().value = cmd
                self.finalize()
                self.ctx.route(['settings_view', self.token])
            else:
                self.ctx.send_message('Неверный формат')
        elif isinstance(self.current(), NumberDetail):
            if self.current().validate(cmd):
                self.current().value = cmd
                self.finalize()
                self.ctx.route(['settings_view', self.token])
            else:
                self.ctx.send_message('Введите целое число')
        elif isinstance(self.current(), FileDetail):
            if 'vk.com' in cmd:
                try:
                    # self.ctx.redis.publish('vk_input', json.dumps({'token': self.ctx.token, 'chat_id': self.ctx.chat_id, 'url': cmd}))
                    gevent.spawn(self.analyze_vk_link, cmd)
                    self.ctx.send_message('Анализирую..')
                    self.ctx.tmpdata = None
                except Exception:
                    self.ctx.send_message('Неверный формат магазина')

    def finalize(self):
        self.ctx.db.bots.update_one({'token': self.token}, {'$set': {self.current()._id.split('.')[-1]: self.current().value}})


class MenuCatView(InlineNavigationView):
    def __init__(self, ctx, msg=''):
        super(MenuCatView, self).__init__(ctx, msg=msg)
        self.init_categories()

    def activate(self):
        self.init_categories()
        super(MenuCatView, self).activate()

    def init_categories(self):
        data = self.ctx.get_bot_data()['items']
        self.categories = defaultdict(list)
        for item_data in data:
            self.categories[item_data['cat'].split('.')[0][:80]].append(item_data)  # TODO HACK
        if u'' in self.categories:
            del self.categories[u'']
        self.links = OrderedDict([(cat, ['menu_cat_view', cat]) for cat in self.categories.keys()])
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


class OrderInfoView(NavigationView):

    def get_msg(self):
        return self.ctx.get_bot_data().get('delivery_info') or 'Об условиях доставки пишите: @' + self.ctx.get_bot_data().get('admin')


class ContactsInfoView(NavigationView):

    def get_msg(self):
        return self.ctx.get_bot_data().get('contacts_info') or 'Чтобы узнать подробности свяжитесь с @' + self.ctx.get_bot_data().get('admin')


class HistoryItem(object):
    def __init__(self, order):
        self.order = order

    def __str__(self):
        res = str(self.order.get('date')).split('.')[0] + '\n\n'
        res += '\n'.join(i['name'].encode('utf-8') + ' x ' + str(i['count']) for i in self.order['items'])
        res += '\n-----\n Итого: ' + str(self.order['total']) + ' руб.'
        res += '\n-----\n Детали доставки: \n-----\n'
        try:
            res += '\n'.join(k.encode('utf-8') + ': ' + v.encode('utf-8') for k, v in self.order['delivery'].items())
        except:
            try:
                res += '\n'.join(k + ': ' + v for k, v in self.order['delivery'].items())
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


class SelectBotView(NavigationView):
    def __init__(self, ctx, links={}, msg="Выберите бота:", bot_view=None):
        self.ctx = ctx
        self.links = links
        self.msg = msg
        self.bot_view = bot_view
        super(NavigationView, self).__init__(ctx, False, msg)

    def get_subview(self, token):
        if token not in self.views:
            self.views[token] = self.bot_view['view'](self.ctx, token)
        return super(SelectBotView, self).get_subview(token)

    def activate(self):
        self.links = OrderedDict()
        self.views = {}
        for bot in self.ctx.db.bots.find({'chat_id': self.ctx.chat_id}):
            self.links['@' + bot['username']] = [self.bot_view['link'], bot['token']]
        self.links['Назад'] = ['main_view']
        super(SelectBotView, self).activate()


class OrdersView(NavigationView):
    def __init__(self, ctx, bot_token):
        self.ctx = ctx
        self.token = bot_token
        self.editable = True
        self.msg = 'Выберите статус заказа'
        self.links = OrderedDict([
            ('В обработке', ['orders_view', self.token, 'in_processing']),
            ('Завершенные', ['orders_view', self.token, 'done']),
            ("Назад", ['orders_view'])
        ])
        self.message_id = None
        self.views = {
            'in_processing': AdminOrderView(self.ctx, self.token, status=u'В обработке'),
            'done': AdminOrderView(self.ctx, self.token, status=u'Завершен')
        }


class SettingsView(NavigationView):
    def __init__(self, ctx, bot_token):
        self.ctx = ctx
        self.token = bot_token
        self.editable = True
        self.msg = 'Настройки'
        self.links = OrderedDict([
            ('API token', ['settings_view', self.token, 'token_view']),
            ('E-mail', ['settings_view', self.token, 'email_view']),
            ('Загрузка товаров', ['settings_view', self.token, 'items_view']),
            ('Условия доставки', ['settings_view', self.token, 'delivery_info_view']),
            ('Минимальная сумма заказа', ['settings_view', self.token, 'total_threshold_view']),
            ('Контакты', ['settings_view', self.token, 'contacts_view']),
            ('Личный кабинет', ['settings_view', self.token, 'cabinet_view']),
            ('Назад', ['settings_view'])]
        )
        self.message_id = None
        # if self.token not in self.views:
        bot = self.ctx.db.bots.find_one({'chat_id': self.ctx.chat_id, 'token': self.token})
        self.views = {
            'token_view': UpdateBotView(self.ctx, self.token, [TokenDetail('shop.token', name='API token', ctx=self.ctx, value=bot['token'])]),
            'email_view': UpdateBotView(self.ctx, self.token, [EmailDetail('shop.email', name='email для приема заказов', ctx=self.ctx, value=bot['email'])]),
            'items_view': UpdateBotView(self.ctx, self.token, [FileDetail('shop.items', value=bot['items'], name='файл с описанием товаров или url магазина вконтакте и нажмите \'ОК\'', desc='<a href="https://github.com/0-1-0/marketbot/blob/master/sample.xlsx?raw=true">(Пример файла)</a>')]),
            'delivery_info_view': UpdateBotView(self.ctx, self.token, [TextDetail('shop.delivery_info', name='текст с условиями доставки', value=bot.get('delivery_info'))]),
            'contacts_view': UpdateBotView(self.ctx, self.token, [TextDetail('shop.contacts_info', name='текст с контактами для связи', value=bot.get('contacts_info'))]),
            'total_threshold_view': UpdateBotView(self.ctx, self.token, [NumberDetail('shop.total_threshold', name='минимальную сумму заказа', value=bot.get('total_threshold'))]),
            'cabinet_view': CabinetView(self.ctx, self.token)
        }

    def mk_markup(self, command_list):
        markup = types.ReplyKeyboardMarkup(row_width=2)
        btns = [self.BTN(cmd) for cmd in command_list]
        markup.add(*btns)
        return markup


class CabinetView(NavigationView):
    def __init__(self, ctx, bot_token):
        self.ctx = ctx
        self.token = bot_token
        self.editable = True
        self.msg = 'Ссылка действительна в течение часа'
        self.links = {'Назад': ['settings_view', self.token]}

    def get_markup(self):
        markup = types.ReplyKeyboardMarkup()
        markup.row(self.BTN('Получить ссылку'))
        markup.row(self.BTN('Назад'))
        return markup

    def process_message(self, cmd):
        if cmd == 'Получить ссылку':
            first_part = md5.new()
            second_part = md5.new()
            first_part.update(self.token + str(datetime.now().hour))
            second_part.update(self.token + self.token[::-1])
            link = '<a href="http://test.com/' + first_part.hexdigest() + second_part.hexdigest() + '">Личный кабинет</a>'
            self.ctx.send_message(link)
        elif cmd == 'Назад':
            self.ctx.route(['settings_view', self.token])
        else:
            pass


class HelpView(NavigationView):
    def get_msg(self):
        return "По всем вопросам обращайтесь к @NikolaII :)"


class MailingView(NavigationView):
    def __init__(self, ctx, bot_token):
        self.ctx = ctx
        self.token = bot_token
        self.editable = True
        self.msg = 'Введите текст, прикрепите фото или стикер рассылки'
        self.links = {"Назад": ['mailing_view']}

    def process_message(self, message):
        if message in self.links:
            self.ctx.route(self.links[message])
        else:
            for convo in self.ctx.db.convos.find({'bot_token': self.token}):
                gevent.spawn(apihelper.send_message, self.token, convo['chat_id'], message, reply_markup=None, parse_mode='HTML')

    def process_file(self, doc):
        fid = doc.document.file_id
        file_info = self.ctx.bot.bot.get_file(fid)
        content = self.ctx.bot.bot.download_file(file_info.file_path)
        file_format = file_info.file_path.split('.')[-1]
        if file_format in ['gif', 'mp4']:
            for convo in self.ctx.db.convos.find({'bot_token': self.token}):
                doc = BytesIO(content)
                doc.name = fid + '.' + file_format
                gevent.spawn(apihelper.send_data, self.token, convo['chat_id'], doc, 'document', reply_markup=None)
        else:
            pass

    def process_photo(self, photo):
        caption = photo.caption
        fid = photo.photo[-1].file_id
        file_info = self.ctx.bot.bot.get_file(fid)
        content = self.ctx.bot.bot.download_file(file_info.file_path)
        file_format = file_info.file_path.split('.')[-1]
        for convo in self.ctx.db.convos.find({'bot_token': self.token}):
            photo = BytesIO(content)
            photo.name = fid + '.' + file_format
            gevent.spawn(apihelper.send_photo, self.token, convo['chat_id'], photo, caption=caption, reply_markup=None)

    def process_sticker(self, sticker):
        fid = sticker.sticker.file_id
        file_info = self.ctx.bot.bot.get_file(fid)
        content = self.ctx.bot.bot.download_file(file_info.file_path)
        file_format = file_info.file_path.split('.')[-1]
        for convo in self.ctx.db.convos.find({'bot_token': self.token}):
            doc = BytesIO(content)
            doc.name = fid + '.' + file_format
            gevent.spawn(apihelper.send_data, self.token, convo['chat_id'], doc, 'sticker', reply_markup=None)

    def process_video(self, video):
        caption = video.caption
        duration = video.video.duration
        fid = video.video.file_id
        file_info = self.ctx.bot.bot.get_file(fid)
        content = self.ctx.bot.bot.download_file(file_info.file_path)
        file_format = file_info.file_path.split('.')[-1]
        for convo in self.ctx.db.convos.find({'bot_token': self.token}):
            video = BytesIO(content)
            video.name = fid + '.' + file_format
            gevent.spawn(apihelper.send_video, self.token, convo['chat_id'], video, caption=caption, duration=duration, reply_markup=None)


class Detail(object):
    def __init__(self, _id, default_options=[], name='', desc='', value=None, ctx=None):
        self._id = _id
        self.default_options = default_options
        self.name = name
        self.desc = desc
        self.value = value
        self.ctx = ctx

    def is_filled(self):
        return self.value is not None

    def validate(self, value):
        return True

    def txt(self):
        return str(self.value)


class TextDetail(Detail):
    pass


class NumberDetail(Detail):
    def validate(self, value):
        try:
            int(value)
            return True
        except ValueError:
            return False


class TokenDetail(TextDetail):
    def validate(self, value):
        if self.ctx.db.bots.find_one({'token': value}) is not None:
            return False
        try:
            b = telebot.TeleBot(value)
            b.get_me()
        except:
            return False

        return True


class EmailDetail(TextDetail):
    def validate(self, value):
        return validate_email(value)


class FileDetail(Detail):
    def validate(self, value):
        return value is not None

    def txt(self):
        if self.value:
            return 'Заполнено'
        else:
            return 'Не заполнено'
