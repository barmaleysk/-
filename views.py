# -*- coding: utf-8 -*-

from telebot import types
import telebot
from validate_email import validate_email
import pymongo


class MarkupMixin(object):
    def mk_markup(self, command_list):
        markup = types.ReplyKeyboardMarkup()
        for cmd in command_list:
            markup.row(self.BTN(cmd))
        return markup

    def BTN(self, txt, request_contact=None):
        return types.KeyboardButton(txt, request_contact=request_contact)

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

    def route(self, path):
        if path == []:
            return self
        elif hasattr(self, 'views') and path[0] in self.views:
            return self.views[path[0]].route(path[1:])

    def process_message(self, message):
        pass

    def process_callback(self, callback):
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
        if not self.editable:
            self.ctx.send_message(self.get_msg(), self.get_markup())
        elif not self.message_id:
            msg = self.ctx.send_message(self.get_msg(), self.get_markup())
            self.message_id = msg.message_id
        else:
            self.ctx.edit_message(self.message_id, self.get_msg(), self.get_markup())


class NavigationView(View):
    def __init__(self, ctx, links={}, msg=""):
        self.links = links
        super(NavigationView, self).__init__(ctx, False, msg)

    def get_markup(self):
        return self.mk_markup(list(reversed(self.links.keys())))

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
        self.process_message(cmd)


class HelpView(NavigationView):

    def get_msg(self):
        return "По всем вопросам обращайтесь к @NikolaII :)"


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

    def process_callback(self, action):
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
        self._orders[number].process_callback(action)


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
                markup.row(self.BTN('отправить номер', True))
            if len(self.current().default_options) > 0:
                markup.row(*[self.BTN(opt) for opt in self.current().default_options])
            if self.ptr > 0:
                markup.row(self.BTN('назад'))

            markup.row(self.BTN('главное меню'))

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

    def process_message(self, cmd):
        # print cmd
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
        elif cmd == 'назад':
            self.prev()
        elif cmd == 'главное меню':
            self.ctx.route(['main_view'])
        else:
            if isinstance(self.current(), TextDetail):
                if self.current().validate(cmd):
                    self.current().value = cmd
                    self.next()
                else:
                    self.ctx.send_message('Неверный формат')
            # elif isinstance(self.current(), FileDetail):
            #     if 'vk.com' in cmd:
            #         try:
            #             celf.ctx.tmpdata = Crawler(cmd).fetch()
            #             if self.current().validate(self.ctx.tmpdata):
            #                 self.current().value = self.ctx.tmpdata
            #                 self.ctx.tmpdata = None
            #                 self.next()
            #         except:
            #             self.ctx.send_message('Неверный формат магазина')


class BotCreatorView(DetailsView):
    def prefinalize(self):
        dd = {}   # TODO
        for d in self.details:
            dd[d._id] = d.value
        self.final_message += '\n Ссылка на бота: @' + telebot.TeleBot(dd['shop.token']).get_me().username.encode('utf-8')

    def finalize(self):
        dd = {}
        for d in self.details:
            dd[d._id] = d.value
        bot_data = {'admin': self.ctx.bot.bot.get_chat(self.ctx.chat_id).username,
                    'token': dd['shop.token'],
                    'items': dd['shop.items'],
                    'email': dd['shop.email'],
                    'chat_id': self.ctx.chat_id,
                    'delivery_info': dd['shop.delivery_info'],
                    'contacts_info': dd['shop.contacts_info'],
                    'total_threshold': dd['shop.total_threshold']}
        self.ctx.db.bots.save(bot_data)
        self.ctx.start_bot(bot_data)
