from datetime import datetime
from grab.spider import Spider, Task
import json
import logging
import re
from selenium import webdriver

# data = {}


class Crawler(Spider):

    def __init__(self, url):
        self.initial_urls = [url]
        self.data = []
        self.d = webdriver.PhantomJS()
        super(Crawler, self).__init__()

    def task_initial(self, grab, task):
        shop_offset = 0
        print("Try to parse: " + task.url)
        shop_url_selector = grab.doc.select('//*[@id="ui_market_items_load_more"]').attr('onclick')
        re_shop_url = re.compile('market-(\d{1,12})+')
        shop_url = re_shop_url.search(shop_url_selector).group(0)   # 'market-NNNNNN'
        shop_number = re_shop_url.search(shop_url_selector).group(1)  # 'NNNNNN'
        shop_full_url = ("https://vk.com/" + shop_url)
        print(shop_url)
        shop_itemscount = grab.doc.select('//*[@class="module clear market_module _module"]//*[@class="header_count fl_l"]').text()
        while shop_offset < int(shop_itemscount):
            yield Task('showcase', url=shop_full_url + '?offset=' + str(shop_offset), shop_key=shop_url, shop_num=shop_number, offset=shop_offset)
            shop_offset += 24

    def task_showcase(self, grab, task):
        print("Go: " + task.url)
        re_price = re.compile('>(\d+)\D(\d*)')
        item_id = 0 + task.offset
        for item_node in grab.doc.select('//div[@class="market_list"]/div'):
            item_id += 1
            item_attributes = {}
            item_native_id = item_node.attr('data-id')
            item_img = item_node.select('div/div/a/img').attr('src')
            item_price_raw = item_node.select('*/div[@class="market_row_price"]').html()
            item_price = int(re_price.search(item_price_raw).group(1))
            item_price_2 = re_price.search(item_price_raw).group(2)
            if item_price_2:    # remove digit delimiter if price > 1000 (dumb, but working)
                item_price = item_price * 1000 + int(item_price_2)
            item_attributes = {"id": item_id,
                               "native_id": item_native_id,
                               "img_url": item_img,
                               "price": item_price,
                               "name": "",
                               "cat": ""}
            self.item_details(item_attributes=item_attributes, shop=task.shop_num, item_native_id=item_native_id, item_key=item_id)

    def item_details(self, item_attributes, shop, item_native_id, item_key):
            d = self.d
            url = 'http://vk.com/market-' + str(shop) + '?w=product-' + str(shop) + '_' + str(item_native_id)
            d.get(url)
            d.implicitly_wait(.9)
            item_desc = d.find_element_by_id("market_item_description").text
            item_cat = d.find_element_by_class_name("market_item_category").text
            item_attributes['desc'] = item_desc
            item_attributes['cat'] = item_cat
            self.data.append(item_attributes)

    def fetch(self):
        self.run()
        return self.data


# def export_file(data,filename):
#     filename = filename
#     with open(filename, 'w') as f:
#         json.dump(data, f)
#     return json.dumps(data)

# def main():
#     print Crawler('https://vk.com/spark.design').fetch()

# if __name__ == '__main__':
#     main()
