import scrapy
from PIL.Image import Image
from scrapy.selector import Selector
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from itertools import cycle
import json, cloudscraper
from scrapy import Request
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers
from urllib.parse import urlencode


class Michaelkors(scrapy.Spider):
    name = "Michaelkors"
    sku_mapping = {}
    target_urls = []
    all_target_urls = []
    base_url = 'https://www.michaelkors.'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    handle_httpstatus_list = [430, 401, 500, 403, 302, 404, 301, 502]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    directory = get_project_settings().get("FILE_PATH")
    if not os.path.exists(directory):
        os.makedirs(directory)
    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    start_urls = "https://www.michaelkors.com"

    spec_mapping = '[{"countryCode": "us", "url_countryCode": "com", "local":"", "currencyCode": "USD"}, {"countryCode": "es", "url_countryCode": "es", "local":"en_ES", "currencyCode": "EUR"}, {"countryCode":"de","url_countryCode":"de","local":"en_DE","currencyCode":"EUR"}, {"countryCode": "mx", "url_countryCode": "global", "local":"mx/es/", "currencyCode": "MXN"}]'
    custom_settings = {
        'REDIRECT_ENABLED': False,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls,
            callback=self.country_base_url,
            headers=self.headers,
            dont_filter=True
        )

    @inline_requests
    def country_base_url(self, response):
        json_data = json.loads(self.spec_mapping)
        country_list = []
        country_url_lists = []
        for item in json_data:
            country_code = item.get('countryCode')
            url_country_code = item.get('url_countryCode')
            local = item.get('local')
            if country_code in ['de', 'fr', 'es', 'it', 'uk']:
                country_url = f'{self.base_url}{url_country_code}'
            elif 'ca' == country_code:
                country_url = f'{self.base_url}{url_country_code}/{local}'
            elif 'us' == country_code:
                country_url = f'{self.base_url}{url_country_code}'
            else:
                country_url = f'{self.base_url}{url_country_code}/{local}'
            country_list.append(country_url)
            country_url_lists = list(set(country_list))

        for url in country_url_lists:
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                self.get_target_urls(resp)
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    self.get_target_urls(resp)
                else:
                    self.log(f"Received unexpected response for URL: {resp.status}")
            else:
                self.log(f"Received Response for URL: {resp.status}")

        params = {'sz': 9999}
        for link in self.all_target_urls:
            # link_url = response.urljoin(link)
            url = link + '?' + urlencode(params)
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                self.parse(resp)
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    self.parse(resp)

        for sku_id, product_url in self.sku_mapping.items():
            # url = response.urljoin(product_url)
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id}
            )

    def get_target_urls(self, response):
        base_url = ''
        category_url = response.css('li.dropdown.level-1.sub-category::attr(data-action)').get()
        if category_url and '?pid=' in category_url:
            base_url = category_url.split('?pid=')[0] + '?pid='
        response_url = response.urljoin(base_url)
        category_links = ['sale', 'new', 'women', 'travel', 'michael-kors-collection', 'men', 'pre-loved']
        for category in category_links:
            api_target = f'{response_url}{category}'
            try:
                proxy = next(self.proxy_cycle)
                scraper = cloudscraper.create_scraper()
                resp = scraper.get(api_target, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                if resp.status_code == 200:
                    data = resp.text
                    category_links = Selector(text=data).css('.dropdown-item a::attr(href)').getall()
                    all_links = list(set(category_links))
                    for link in all_links:
                        link_url = response.urljoin(link)
                        if link_url not in self.all_target_urls:
                            self.all_target_urls.append(link_url)

            except Exception as e:
                print(e)

    def parse(self, response):
        sku_id = ''
        product_elements = response.css(".product-tile-wrapper")
        if product_elements:
            for product_ele in product_elements:
                p_url = product_ele.css('.tile-body>a::attr(href)').get()
                product_url = response.urljoin(p_url)
                product_element = product_ele.css('.product-tile-container>div[data-pid]')
                if product_element:
                    sku_id = product_element.attrib['data-pid']
                    self.get_all_sku_mapping(product_url, sku_id)

    def get_all_sku_mapping(self, product_url, sku_id):
        if product_url:
            if "en/" in product_url:
                existing_url = self.sku_mapping.get(sku_id)
                if existing_url and "en/" not in existing_url:
                    self.sku_mapping[sku_id] = product_url
                elif sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = product_url
            elif "en/" not in product_url:
                if sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = product_url

    @inline_requests
    def parse_product(self, response, product_url, sku_id):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get(b'Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': url, 'sku_id': sku_id}
            )
            return
        url_without_html = response.url.replace(".html", '')
        product_url = response.url.split('/')
        selected_url = product_url[3:]
        productUrls = '/'.join(selected_url)
        content = {}
        specification = {}
        product_color = ''
        product_data = response.css('#analytics-productDetails-event::attr(data-tracking-event)').get()
        if product_data is not None:
            data = json.loads(product_data)
            for item in data:
                product_color = item.get('colorCode')

        languages = ['es', 'com']
        for item in languages:
            url = f'{self.base_url}{item}/{productUrls}'
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(resp)
                if content_info:
                    content[item] = {
                        "sku_link": f'{url}',
                        "sku_title": content_info["sku_title"],
                        "sku_long_description": content_info["sku_long_description"],
                        "sku_short_description": content_info['sku_short_description']
                    }
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    content_info = self.collect_content_information(resp)
                    if content_info:
                        content[item] = {
                            "sku_link": f'{url}',
                            "sku_title": content_info["sku_title"],
                            "sku_long_description": content_info["sku_long_description"],
                            "sku_short_description": content_info['sku_short_description']
                        }
            else:
                self.log(f"Received 404 Response for URL: {resp.url}")

        # spec_mapping = '[{"countryCode": "us", "url_countryCode": "com", "local":"", "currencyCode": "USD"}, {"countryCode": "ca", "url_countryCode": "com", "local":"ca/en", "currencyCode": "CAD"}, {"countryCode": "de", "url_countryCode": "de", "local":"en_DE", "currencyCode": "EUR"}, {"countryCode": "fr", "url_countryCode": "fr", "local":"en_FR", "currencyCode": "EUR"}, {"countryCode": "es", "url_countryCode": "es", "local":"en_ES", "currencyCode": "EUR"}, {"countryCode": "it", "url_countryCode": "it", "local":"en_IT", "currencyCode": "EUR"}, {"countryCode": "in", "url_countryCode": "global", "local":"en_IN", "currencyCode": "INR"}, {"countryCode": "ro", "url_countryCode": "eu", "local":"en_RO", "currencyCode": "RON"}, {"countryCode": "gr", "url_countryCode": "global", "local":"en_GR", "currencyCode": "EUR"}, {"countryCode": "au", "url_countryCode": "global", "local":"en_AU", "currencyCode": "AUD"}, {"countryCode": "fi", "url_countryCode": "eu", "local":"en_FI", "currencyCode": "EUR"}, {"countryCode": "it", "url_countryCode": "eu", "local":"en_IT", "currencyCode": "EUR"}, {"countryCode": "se", "url_countryCode": "eu", "local":"en_SE", "currencyCode": "SEK"}, {"countryCode": "za", "url_countryCode": "global", "local":"en_ZA", "currencyCode": "ZAR"}, {"countryCode": "id", "url_countryCode": "global", "local":"en_ID", "currencyCode": "IDR"}, {"countryCode": "my", "url_countryCode": "global", "local":"en_MY", "currencyCode": "MYR"}, {"countryCode": "nz", "url_countryCode": "global", "local":"en_NZ", "currencyCode": "NZD"}, {"countryCode": "pk", "url_countryCode": "global", "local":"en_PK", "currencyCode": "PKR"}, {"countryCode": "ph", "url_countryCode": "global", "local":"en_PH", "currencyCode": "PHP"}, {"countryCode": "sg", "url_countryCode": "global", "local":"en_SG", "currencyCode": "SGD"}, {"countryCode": "th", "url_countryCode": "global", "local":"en_TH", "currencyCode": "THB"}, {"countryCode": "bh", "url_countryCode": "global", "local":"en_BH", "currencyCode": "BHD"}, {"countryCode": "il", "url_countryCode": "global", "local":"en_IL", "currencyCode": "ILS"}, {"countryCode": "ng", "url_countryCode": "global", "local":"en_NG", "currencyCode": "NGN"}, {"countryCode": "sk", "url_countryCode": "global", "local":"en_SK", "currencyCode": "EUR"}, {"countryCode": "uk", "url_countryCode": "co.uk", "local":"uk", "currencyCode": "GBP"}, {"countryCode": "lv", "url_countryCode": "eu", "local":"en_LV", "currencyCode": "EUR"}, {"countryCode": "lt", "url_countryCode": "eu", "local":"en_LT", "currencyCode": "EUR"}, {"countryCode": "lu", "url_countryCode": "eu", "local":"en_LU", "currencyCode": "EUR"}, {"countryCode": "nl", "url_countryCode": "eu", "local":"en_NL", "currencyCode": "EUR"}, {"countryCode": "no", "url_countryCode": "eu", "local":"en_NO", "currencyCode": "NOK"}, {"countryCode": "pl", "url_countryCode": "eu", "local":"en_PL", "currencyCode": "PLN"}, {"countryCode": "pt", "url_countryCode": "eu", "local":"en_PT", "currencyCode": "EUR"}, {"countryCode": "ie", "url_countryCode": "eu", "local":"en_IE", "currencyCode": "EUR"},{"countryCode": "dk", "url_countryCode": "eu", "local":"en_DK", "currencyCode": "DKK"}]'
        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode')
                currency_code = item.get('currencyCode')
                url_country_code = item.get('url_countryCode')
                local = item.get('local')
                if country_code in ['de', 'fr', 'es', 'it', 'uk']:
                    country_Url = f'{self.base_url}{url_country_code}/{productUrls}'
                elif 'ca' == country_code:
                    country_Url = f'{self.base_url}{url_country_code}/{local}{productUrls}'
                elif 'us' == country_code:
                    country_Url = f'{self.base_url}{url_country_code}/{productUrls}'
                else:
                    country_Url = f'{self.base_url}{url_country_code}/{local}{productUrls}'
                req = scrapy.Request(country_Url, headers=self.headers, dont_filter=True)
                country_resp = yield req
                if country_resp.status == 404:
                    self.log(f"Received 404 Response for URL: {req.url}")
                elif country_resp.status in [301, 302]:
                    redirected_url = country_resp.headers.get('Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = Request(url, headers=self.headers, dont_filter=True)
                    country_resp = yield req
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, country_code,
                                                                             currency_code)
                        if specification_info:
                            specification[country_code] = specification_info
                else:
                    specification_info = self.collect_specification_info(country_resp, country_code, currency_code)
                    if specification_info:
                        specification[country_code] = specification_info

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')

        domain, domain_url = self.extract_domain_domain_url(response.url)
        main_material = ''
        secondary_material = ''
        collection_name = ''
        list_img = []
        image = []
        img_list_1 = response.css('.zoom>img::attr(src)').getall()
        img_list_2 = response.css('.zoom>img::attr(data-src)').getall()
        image.extend(img_list_1)
        image.extend(img_list_2)
        for img in image:
            list_img.append(img)

        long_description = response.css('.product-details-tab-pane--js p::text').getall()
        keys_to_match = ["Length", "Width", "cm", "Size", "chaîne", "Height", "W X"]
        size_dimensions = []
        for pair in long_description[1:]:
            parts = pair.strip().split('•')
            for part in parts:
                for key in keys_to_match:
                    if key.lower() in part.lower():
                        cleaned = part.strip('•').strip()
                        if cleaned:
                            size_dimensions.append(cleaned)
                        break

        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(self, list_img)
        else:
            if list_img:
                directory = self.directory + sku_id
                for url_pic in list_img:
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            proxy = next(self.proxy_cycle)
                            res = requests.get(url_pic, proxies={'http': proxy, 'https': proxy})
                            res.raise_for_status()
                            break
                        except requests.exceptions.RequestException as e:
                            logging.error(f"Error downloading image: {e}")
                            time.sleep(1)
                            trial_image += 1
                            continue
                    else:
                        logging.info(
                            f"Failed to download image after {trial_image} attempts."
                        )
                        continue

                    filename = str(uuid.uuid4()) + ".png"
                    if not os.path.exists(directory):
                        os.makedirs(directory)

                    try:
                        with open(
                                os.path.join(directory, filename), "wb"
                        ) as img_file:
                            img_file.write(res.content)

                        image = Image.open(os.path.join(directory, filename))
                        image.save(os.path.join(directory, filename))
                        image_info = directory + "/" + filename
                        product_images_info.append(image_info)
                    except Exception as e:
                        logging.error(f"Error processing image: {e}")

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = self.name
        item['collection_name'] = collection_name
        item['product_badge'] = ''
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        sku_title = ''
        sku_short_description = ''
        sku_lo_description = []
        sku_long_description = ''
        selector = scrapy.Selector(text=response.text)
        script_tag = selector.css('script:contains("sl:translate_json")')
        script_content = script_tag.extract_first()
        if script_content is None:
            sku_title = response.css('.product-name.overflow-hidden::text').get()
            sku_short_description = response.css('.product-details-tabs__item>p::text').get()
            if sku_short_description:
                sku_short_description = sku_short_description.strip()
            sku_description = response.css('.product-details-tabs__item>p::text').getall()
            for item in sku_description:
                if '\n<br />' in item:
                    sku_lo_description.extend(item.split('\n<br />'))
                else:
                    sku_lo_description.extend(item.split('<br />'))
            sku_lo_description = [part.strip() for part in sku_lo_description if part.strip()]
            sku_long = ''.join(sku_lo_description)
            sku_long_description = f"{sku_short_description} {sku_long}"

        elif script_content:
            start_index = script_content.find('{')
            end_index = script_content.rfind('}') + 1
            json_content = script_content[start_index:end_index]
            json_data = json.loads(json_content)
            sku_short_description = json_data['pdp']['rawJson']['description']
            sku_title = json_data['pdp']['rawJson']['displayName']
            sku_description = json_data['pdp']['rawJson']['richTextDescription']
            text_description = sku_description.split('•')
            for item in text_description:
                if '\n<br />' in item:
                    sku_lo_description.extend(item.split('\n<br />'))
                else:
                    sku_lo_description.extend(item.split('<br />'))

            sku_lo_description = [part.strip() for part in sku_lo_description if part.strip()]
            sku_long = ''.join(sku_lo_description)
            sku_long_description = f"{sku_short_description} {sku_long}"
        if not sku_title:
            return

        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, country_code, currency_code):
        sales_price = ''
        base_price = ''
        availability_status = ''
        out_of_stock_text = ''
        sizes = ''
        shipping_lead_time = ''
        shipping_expenses = ''
        reviews_rating_value = ''
        reviews_numbers = ''
        selector = scrapy.Selector(text=response.text)
        script_tag = selector.css('script:contains("sl:translate_json")')
        script_content = script_tag.extract_first()
        if script_content is None:
            shipping = response.css('.free-shipping>ul>li>span::text').getall()
            delivery_shipping = [detail for detail in shipping if 'delivery' in detail.lower()]
            shipping_expenses = ''.join(delivery_shipping)
            reviews_numbers = response.css('.bvseo-reviewCount::text').get()
            reviews_rating_value = response.css('.bvseo-ratingValue::text').get()
            size = response.css('#size-1>div>label.text-uppercase::text').getall()
            sizes = list(set(size))
            product_data = response.css('#analytics-productDetails-event::attr(data-tracking-event)').get()
            if product_data:
                data = json.loads(product_data)
                for item in data:
                    sales_price = item.get('pricePer')
                    base_price = item.get('basePrice')
                    product_availability = item.get('availability')
                    if product_availability == 'N':
                        availability_status = "No"
                        out_of_stock_text = "Sold out"
                    else:
                        availability_status = "Yes"
                        out_of_stock_text = "AVAILABLE"
            else:
                self.log('Product data None')

        if not base_price:
            return
        elif script_content:
            start_index = script_content.find('{')
            end_index = script_content.rfind('}') + 1
            json_content = script_content[start_index:end_index]
            json_data = json.loads(json_content)
            sales_price = json_data['pdp']['rawJson']['prices']['lowSalePrice']
            base_price = json_data['pdp']['rawJson']['prices']['lowListPrice']
            skus = json_data['pdp']['rawJson']['SKUs']
            sizes = set(sku['variant_values']['size']['sizeCode'] for sku in skus)
            product_availability = json_data['pdp']['rawJson']['soldOut']
            if product_availability is None:
                availability_status = "No"
                out_of_stock_text = "Sold out"
            else:
                availability_status = "Yes"
                out_of_stock_text = "AVAILABLE"

        return {
            "lang": 'en',
            "domain_country_code": country_code,
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sales_price,
            "active_price": sales_price,
            "stock_quantity": '',
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": reviews_rating_value,
            "reviews_number": reviews_numbers,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "size_availability": sizes,
            "sku_link": response.url
        }
