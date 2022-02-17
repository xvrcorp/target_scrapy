import scrapy
import re
import json

def remove_html_tags(text):
    re_tags = re.compile('<.*?>')
    return re.sub(re_tags, '', text)

def clean_text(text):
    return re.sub(r"[\t]+", " ", remove_html_tags(text))


PRODUCT_URL = 'https://www.target.com/p/apple-iphone-13-pro-max/-/A-84616123?preselect=84240109#lnk=sametab'
API_PRODUCT_URL = 'https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=%s&tcin=84616123&store_id=981&pricing_store_id=981'
API_QUESTION_URL = 'https://r2d2.target.com/ggc/Q&A/v1/question-answer?type=product&questionedId=84616123&page=0&size=10&sortBy=MOST_ANSWERS&key=%s&errorTag=drax_domain_questions_api_error'

class TargetSpider(scrapy.Spider):
    name = 'target'
    allowed_domains = ['target.com']
    start_urls = [PRODUCT_URL]
    base_url = 'http://www.target.com'

    def start_request(self):
        yield scrapy.Request(url=PRODUCT_URL, 
            callback=self.parse,
            errback=self.errback,
            meta={'dont_redirect': True})

    def parse(self, response):

        re_key = re.compile(r'.*apiKey\":\"([^\"]+)\".*')
        keys = re_key.findall(response.body.decode("utf-8"))

        if(len(keys) > 0):
            apikey = keys[0]
            url = API_PRODUCT_URL % apikey

            yield scrapy.Request(url=url, 
                callback=self.get_product_data,
                errback=self.errback,
                meta={'dont_redirect': True, 'apikey': apikey})
        else:
            self.logger.error('API key not found')

    def get_product_data(self, response):
        product_response = json.loads(response.text)
        children = product_response['data']['product']['children']
        preselect_data = next(p for p in children if p["tcin"] == '84240109')

        product_info = {
            'title' : product_response['data']['product']['item']['product_description']['title'],
            'price' :  preselect_data['price']['current_retail'],
            'description' :  clean_text(preselect_data['item']['product_description']['downstream_description']),
            'specifications' :  map(clean_text, preselect_data['item']['product_description']['bullet_descriptions']),
            'highlights' :  preselect_data['item']['product_description']['soft_bullets']['bullets'],
            'images' :  preselect_data['item']['enrichment']['images']['alternate_image_urls'],
        }
        questions_url = API_QUESTION_URL % response.meta['apikey']

        yield scrapy.Request(url=questions_url, 
            callback=self.get_questions, 
            errback=self.errback,
            meta={'dont_redirect': True, 'product_info': product_info})

    def get_questions(self, response):
        questions_data = json.loads(response.text)
        questions = questions_data['results']

        #Adding Questions to the product info
        product_info = response.meta['product_info']
        product_info['questions'] = questions
        self.print_product_info(product_info)


    def print_product_info(self, product_info):
        #Print Product info
        print('[ Title ]', product_info['title'])
        print('[ Price ]', product_info['price'])
        print('[ Description ]', product_info['description'])
        print('[ Specifications ]')
        for specification in product_info['specifications']:
            print(' - ', specification)
        print('[ Highlights ]')
        for highlight in product_info['highlights']:
            print(' - ', highlight)
        print('[ Questions ]')
        for question in product_info['questions']:
            print(' - ', question['text'])
        print('[ Images ]')
        for image_url in product_info['images']:
            print(' - ', image_url)

    def errback(self, failure):
        self.logger.error(repr(failure))