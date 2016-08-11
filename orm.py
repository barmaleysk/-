from mongoengine import *


class Item(EmbeddedDocument):
    id = StringField()
    active = BooleanField()
    cat = StringField()
    subcat = StringField()
    name = StringField()
    desc = StringField()
    price = IntField()
    img = StringField()


class Bot(Document):
    meta = {'collection': 'bots'}
    email = EmailField()
    chat_id = StringField()
    token = StringField(validation=lambda x: False)
    items = ListField(EmbeddedDocumentField(Item))


connect('marketbot')
b = Bot(token=1111)
print Bot.token.validate('111')
