import scrapy
from urllib.parse import urlencode
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
from scrapy.linkextractors import LinkExtractor
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

class Sansarushop(scrapy.Spider):
    name = "sansarushop"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://sansarushop.com"
    handle_httpstatus_list = [404, 403, 500, 430]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    directory = get_project_settings().get("FILE_PATH")
    if not os.path.exists(directory):
        os.makedirs(directory)
    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    start_urls = "https://sansarushop.com/"
    languages = ["en", "de", "it", "fr", "es"]
    spec_mapping = '[{"countryName" : "United States" , "codeUrl":"en", "countryCode" :"US", "currencyCode":"USD", "shipping_charge":"24,99 €","shipping_time":"48/72h"}, {"countryName" : "Spain" ,"codeUrl": "", "countryCode" :"ES", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"24/48h"}, {"countryName" : "France" , "codeUrl":"fr", "countryCode" :"FR", "currencyCode":"EUR", "shipping_charge":"5,99 €","shipping_time":"2/4 DAYS" },{"countryName" : "Austria" , "codeUrl":"en-AT" , "countryCode" :"AT", "currencyCode":"EUR" ,"shipping_charge":"6,99 €","shipping_time":"2/4 days"},{"countryName" : "Finland" , "codeUrl":"en-FI" , "countryCode" :"FI", "currencyCode":"EUR","shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "Hungary"  , "codeUrl":"en-HU", "countryCode" :"HU", "currencyCode":"HUF", "shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "Netherlands" , "codeUrl":"en-NL", "countryCode" :"NL", "currencyCode":"EUR", "shipping_charge":"5,99 €","shipping_time":"2/4 days"}, {"countryName" : "Slovenia" , "codeUrl":"en-SI" , "countryCode" :"SI", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "United Kingdom" , "codeUrl":"en_GB-GB", "countryCode" :"GB", "currencyCode":"GBP", "shipping_charge":"7,99 €","shipping_time":"4/6 days"}, {"countryName" : "Belgium" , "codeUrl":"en-BE", "countryCode" :"BE", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"2/4 days"}, {"countryName" : "Ireland" , "codeUrl":"en_GB-IE", "countryCode" :"IE", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"4/6 days"}, {"countryName" : "Poland" , "codeUrl":"en-PL", "countryCode" :"PL", "currencyCode":"PLN", "shipping_charge":"6,99 €","shipping_time":"2/4 days"}, {"countryName" : "Czech Republic" , "codeUrl":"en-CZ", "countryCode" :"CZ", "currencyCode":"CZK", "shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "Germany" , "codeUrl":"en-DE" , "countryCode" :"DE", "currencyCode":"EUR", "shipping_charge":"5,99 €","shipping_time":"2/4 days"},{"countryName" : "Italy" , "codeUrl":"en-IT" , "countryCode" :"IT", "currencyCode":"EUR", "shipping_charge":"5,99 €","shipping_time":"2/4 days"},{"countryName" : "Portugal" , "codeUrl":"en-PT", "countryCode" :"PT", "currencyCode":"EUR" ,"shipping_charge":"3,99 €","shipping_time":"2/3 days"},{"countryName" : "Sweden" , "codeUrl":"en-SE", "countryCode" :"SE", "currencyCode":"SEK", "shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "Denmark" , "codeUrl":"en-DK" , "countryCode" :"DK", "currencyCode":"DKK", "shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "Greece" , "codeUrl":"en-GR" , "countryCode" :"GR", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"4/6 days"}, {"countryName" : "Luxembourg"  , "codeUrl":"en-LU" , "countryCode" :"LU", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"4/6 days"}, {"countryName" : "Romania" , "codeUrl":"en-RO", "countryCode" :"RO", "currencyCode":"RON", "shipping_charge":"6,99 €","shipping_time":"4/6 days"},{"countryName" : "Switzerland" , "codeUrl":"en-CH" , "countryCode" :"CH", "currencyCode":"CHF", "shipping_charge":"15,99 €","shipping_time":"4/6 days"}, {"countryName" : "Australia" , "codeUrl":"en_GB-AU", "countryCode" :"AU", "currencyCode":"AUD", "shipping_charge":"10,99 €","shipping_time":"10/15 days"}, {"countryName" : "New Zealand" , "codeUrl":"en_GB-NZ" , "countryCode" :"NZ", "currencyCode":"NZD", "shipping_charge":"10,99 €","shipping_time":"10/15 days"}, {"countryName" : "India"  , "codeUrl":"en-IN", "countryCode" :"IN", "currencyCode":"INR", "shipping_charge":"14,99 €","shipping_time":"10/15 DAYS"}, {"countryName" : "Hong Kong" , "codeUrl":"en-HK", "countryCode" :"HK", "currencyCode":"HKD", "shipping_charge":"14,99 €","shipping_time":"10/15 days"},{"countryName" : "Japan" , "codeUrl":"en-JP", "countryCode" :"JP", "currencyCode":"JPY", "shipping_charge":"10,99 €","shipping_time":"10/15 days"},{"countryName" : "Thailand" , "codeUrl":"en-TH", "countryCode" :"TH", "currencyCode":"THB", "shipping_charge":"14,99 €","shipping_time":"10/15 days"},{"countryName" : "Korea Republic of" , "codeUrl":"en-KR", "countryCode" :"KR", "currencyCode":"KRW", "shipping_charge":"14,99 €","shipping_time":"10/15 days"},{"countryName" : "Malaysia" , "codeUrl":"en-MY" , "countryCode" :"MY", "currencyCode":"MYR", "shipping_charge":"14,99 €","shipping_time":"10/15 days"},{"countryName" : "Taiwan Region" , "codeUrl":"en-TW" , "countryCode" :"TW", "currencyCode":"TWD", "shipping_charge":"14,99 €","shipping_time":"10/15 days"},{"countryName" : "South Africa" , "codeUrl":"en_GB-ZA" , "countryCode" :"ZA", "currencyCode":"EUR", "shipping_charge":"14,99 €","shipping_time":"10/15 days"}]'
    # spec_mapping = '[{"countryName" : "United States" , "codeUrl":"en", "countryCode" :"US", "currencyCode":"USD", "shipping_charge":"24,99 €","shipping_time":"48/72h"}, {"countryName" : "Spain" ,"codeUrl": "", "countryCode" :"ES", "currencyCode":"EUR", "shipping_charge":"6,99 €","shipping_time":"24/48h"}, {"countryName" : "France" , "codeUrl":"fr", "countryCode" :"FR", "currencyCode":"EUR", "shipping_charge":"5,99 €","shipping_time":"2/4 DAYS" }]'

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
            headers=rotate_headers(),
        )

    @inline_requests
    def country_base_url(self, response):
        for language in self.languages:
            if language == "es":
                url = f'https://sansarushop.com'
            else:
                url = f'https://sansarushop.com/{language}'
            req = yield Request(url, headers=rotate_headers(), dont_filter=True)
            self.get_target_urls(req)

        filtered_urls = list(set(self.all_target_urls))
        for url in filtered_urls:
            request = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
            link_resp = yield request
            if link_resp.status == 200:
                self.parse(link_resp)
            else:
                self.log(f"Received Response for URL: {link_resp.status}")

        for sku_id, product_data in self.sku_mapping.items():
            product_url = product_data.get('product_url')
            badge = product_data.get('badge', '')
            barcode = product_data.get('barcode')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url, 'sku': sku_id, "badge": badge, "barcode": barcode}
            )
    def get_target_urls(self, response):
        try:
            link_extractor = LinkExtractor()
            links = link_extractor.extract_links(response)
            for link in links:
                if link.url:
                    try:
                        if 'sansarushop' in link.url:
                            if link.url not in self.all_target_urls:
                                url = urljoin(response.url, link.url)
                                self.all_target_urls.append(url)
                    except Exception as e:
                        print(f"Error processing URL {link.url}: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def parse(self, response):
        try:
            products = response.css("li > div.card-wrapper")
            if products:
                for item in products:
                    product = item.css("div.card-wrapper>div>div>div>p>a::attr(href)").get()
                    badge = item.css("div.card__badge>span>b>font>font::text").get()
                    proxy = next(self.proxy_cycle)
                    url = f"{self.base_url}{product}/products.json"
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(url, headers=rotate_headers())
                    if resp.status_code == 200:
                        products_data = json.loads(resp.text)
                        json_product = products_data.get('product')
                        variants = json_product.get('variants')
                        for variant in variants:
                            id = variant.get('id')
                            sku_id = variant.get('sku')
                            barcode = variant.get('barcode')
                            product_url = f'{product}?variant={id}'
                            self.get_all_sku_mapping(product_url, sku_id, badge, barcode)
            else:
                print(f"parse {response} ")
        except Exception as e:
            self.log(f"Error occured parse fn{e}")
        try:
            next_page_link = response.css('div#AjaxinatePagination>link::attr(href)').get()
            if next_page_link:
                next_page_link = f'https://sansarushop.com{next_page_link}'
                proxy = next(self.proxy_cycle)
                next_page_resp = requests.get(next_page_link, headers=rotate_headers())
                if next_page_resp.status_code == 200:
                    product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                    self.parse(product_response)
        except Exception as e:
            self.log(f"Pagingation {e}")

    def get_all_sku_mapping(self, product_url, sku_id, badge, barcode):
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge, 'barcode': barcode}
            else:
                if isinstance(self.sku_mapping[sku_id], str):
                    self.sku_mapping[sku_id] = self.sku_mapping[sku_id]
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge, 'barcode': barcode}

    @inline_requests
    def parse_product(self, response, product_url, sku, badge, barcode):
        content = {}
        specification = {}
        s_product_url = product_url.split('/products')[1]
        pro_url = s_product_url.split('?variant=')[0]
        for language in self.languages:
            logging.info(f'Processing: {language}')
            if language == "es":
                url = f"{self.base_url}/products{pro_url}"
            else:
                url = f"{self.base_url}/{language}/products{pro_url}"
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            language_resp = yield req
            if language_resp.status == 200:
                content_info = self.collect_content_information(language_resp)
                content[language] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            elif language_resp.status in [301, 302]:
                redirected_url = language_resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=rotate_headers(), dont_filter=True)
                redirected_url_resp = yield req
                if redirected_url_resp.status == 200:
                    content_info = self.collect_content_information(redirected_url_resp)
                    content[language] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            else:
               self.log(f"Received 404 Response for URL: {req.url}")

        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode')
                currency_code = item.get('currencyCode')
                url_country_code = item.get('codeUrl')
                shipping_charge = item.get('shipping_charge')
                shipping_time = item.get('shipping_time')
                cookies = {
                    'secure_customer_sig': '',
                    'receive-cookie-deprecation': '1',
                    '_hjSession_893119': 'eyJpZCI6IjRiZDU5OTZiLTYxYTUtNDBkZS04ODFlLTk1ODQ0Y2JkY2Y3YSIsImMiOjE3MTU4MzE0NDIzMDMsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjoxLCJzcCI6MH0=',
                    'yotpo_pixel': '1088ef6f-1797-4038-a59f-a8bd607724e4',
                    'shopify_pay_redirect': 'pending',
                    'aph_location_517743_351822': 'true',
                    'aph_location_201264_367375': 'false',
                    'aph_location_586877_931586': 'false',
                    'aph_location_649955_222997': 'false',
                    'aph_location_442327_126652': 'false',
                    'aph_location_70691_968270': 'false',
                    '_tracking_consent': '%7B%22con%22%3A%7B%22CMP%22%3A%7B%22s%22%3A%22%22%2C%22p%22%3A%220%22%2C%22m%22%3A%220%22%2C%22a%22%3A%220%22%7D%7D%2C%22region%22%3A%22INRJ%22%2C%22v%22%3A%222.1%22%2C%22reg%22%3A%22%22%7D',
                    '_ga_DGLG1GRKPX': 'GS1.1.1715831443.1.1.1715831446.58.0.0',
                    '_ga_NPMP5SM2BX': 'GS1.1.1715831445.1.1.1715831447.0.0.0',
                    '_pin_unauth': 'dWlkPU56TTRaREV5WW1JdE5HWTJaaTAwTjJWa0xXRXhORFF0WldZeU9EUXpNRE0xWm1abA',
                    '_hjSessionUser_893119': 'eyJpZCI6IjZiYjFiOGI3LTEwM2QtNTAyNi1hNmQ1LTZhYWExYzhkNzczOCIsImNyZWF0ZWQiOjE3MTU4MzE0NDIyOTksImV4aXN0aW5nIjp0cnVlfQ==',
                    '_cmp_a': '%7B%22purposes%22%3A%7B%22a%22%3Afalse%2C%22p%22%3Afalse%2C%22m%22%3Afalse%2C%22t%22%3Atrue%7D%2C%22display_banner%22%3Afalse%2C%22sale_of_data_region%22%3Afalse%7D',
                    'tinycookie': '1',
                    'tinycookie_acc': 'req',
                    'locale_bar_accepted': '1',
                    'snize-recommendation': 'qhjndi6rcvd',
                    '__kla_id': 'eyJjaWQiOiJZVFF4TkRGaU16SXRORGhtWmkwMFl6ZGxMVGd4WldRdFlXVmpZV0l5WWpOaU9XVXgiLCIkcmVmZXJyZXIiOnsidHMiOjE3MTU4MzE0NDUsInZhbHVlIjoiIiwiZmlyc3RfcGFnZSI6Imh0dHBzOi8vc2Fuc2FydXNob3AuY29tL2NvbGxlY3Rpb25zLyJ9LCIkbGFzdF9yZWZlcnJlciI6eyJ0cyI6MTcxNTgzMjM2MywidmFsdWUiOiIiLCJmaXJzdF9wYWdlIjoiaHR0cHM6Ly9zYW5zYXJ1c2hvcC5jb20vY29sbGVjdGlvbnMvIn19',
                    'localization': f'{country_code}',
                    'cart_currency': f'{currency_code}',
                    'keep_alive': '258aaaf9-33df-4203-b755-0e0212090b6e'
                }

                country_url = f'{self.base_url}{product_url}'
                proxy = next(self.proxy_cycle)
                country_req = requests.get(country_url, headers=rotate_headers(), cookies=cookies)
                country_resp = TextResponse(url='', body=country_req.text, encoding='utf-8')
                if country_resp.status == 404:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
                elif country_resp.status in [301, 302]:
                    try:
                        redirected_url = country_resp.headers.get('Location').decode('utf-8')
                        url = response.urljoin(redirected_url)
                        proxy = next(self.proxy_cycle)
                        country_response = requests.get(url)
                        redirected_resp = TextResponse(url='', body=country_response.text, encoding='utf-8')
                        if redirected_resp.status == 200:
                            specification_info = self.collect_specification_info(redirected_resp, country_code, shipping_time, shipping_charge,sku)
                            specification[country_code.lower()] = specification_info
                    except Exception as e:
                        print(e)
                else:
                    specification_info = self.collect_specification_info(country_resp, country_code, shipping_time, shipping_charge,sku)
                    specification[country_code.lower()] = specification_info

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return

        list_img = []
        picture_sources = response.css('div.product__media.media.media--transparent>img::attr(src)').getall()
        for pictures in picture_sources:
             list_img.append(f"https:{pictures}")

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku
                for url_pic in list_img:
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            proxy = next(self.proxy_cycle)
                            res = requests.get(url_pic)
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
        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        product_details = response.css('div.accordion__content.rte>ul>li>span')
        keys_to_match = ["Length", "Width", "Size", "Diameters", "Diameter", "Thickness", "Weight", "Height", "Color:", "Material", "Gemstone:", "Stone:"]
        size_dimension = []
        product_color = ''
        main_material = ''
        secondary_material = ''
        for key in keys_to_match:
            for li in product_details:
                text = li.css('::text').get()
                if key.lower() in text.lower():
                    if key == "Material":
                        main_material = text.split(":")[1]
                    elif key == "Color:":
                        product_color = text.split('Color:')[1]
                    elif key in ["Gemstone:", "Stone:"]:
                        secondary_material = text.split(key)[1]
                    else:
                        size_dimension.append(text)

        collection_name = ''
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_name
        item['brand'] = 'SanSaru'
        item['manufacturer'] = self.name
        item['product_badge'] = badge
        item['sku'] = sku
        item['sku_color'] = product_color
        item['gtin13'] = barcode
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        title = ''
        description = ''
        script_tags = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tags:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    title = json_data['name']
                    description = json_data['description']
            except Exception as e:
                self.log(f"error occured {e}")
        product_features = response.css('div.accordion__content.rte>ul>li>span::text').extract()
        sku_short_description = response.css("div.product-single__skills > div> span::text").getall()
        sku_long_description = f"{description} {' '.join(product_features)} {' '.join(sku_short_description)}"
        return {
            "sku_title": title,
            "sku_short_description": ' '.join(sku_short_description),
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, shipping_time, shipping_charge,sku):
        availability = ''
        sale_price = ''
        item_url = ''
        currency_code = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    for offer in json_data['offers']:
                        sku_id = offer.get('sku')
                        if sku_id == sku:
                            sale_price = offer.get('price')
                            currency_code = offer.get('priceCurrency')
                            availability = offer.get('availability')
                            item_url = offer.get('url')
                            break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON Offers: {e}")
        price_string = str(sale_price)
        sale_price = self.extract_price_info(price_string)
        base_price = ' '
        b_price = resp.css("div#price-template--14296394235947__main> div> div> div.price__regular> span.price-item--regular::text").get()
        if b_price is not None:
            base_price = self.extract_price_info(b_price)
        else:
            base_price = sale_price
        size_available = []
        inventory_quantity = 0
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]
        if out_of_stock_text == 'AVAILABLE':
            script_tag = resp.css('#variant-selects-template--24025480003930__main > script::text').get()
            if script_tag:
                try:
                    products = json.loads(script_tag)
                    for product in products:
                        sizes = product.get('title')
                        available = product.get('available')
                        quantity = product.get('inventory_quantity')
                        if sizes == "Default Title":
                            break
                        else:
                            if available == True:
                                size_available.append(sizes)
                                inventory_quantity += quantity

                except json.JSONDecodeError as e:
                    self.log(f"Error decoding JSON: {e}")



        return {
            "lang": country_code.lower(),
            "domain_country_code": country_code.lower(),
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": inventory_quantity,
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_time,
            "shipping_expenses":  shipping_charge,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": ' ',
            "reviews_number": ' ',
            "size_available": size_available,
            "sku_link": item_url
        }

    def extract_price_info(self, price_string):
        match = re.search(r"([^\d]*)([\d.,]+)", price_string)
        if match:
            currency_symbol, numerical_value = match.groups()
            pattern = r'\,\d{3}(?![\d,])'
            match = re.search(pattern, numerical_value)
            if match:
                numerical_value = numerical_value.replace(",", "")
            pattern = r'\.\d{3}(?![\d.])'
            match = re.search(pattern, numerical_value)
            if match:
                numerical_value = numerical_value.replace(".", "")
            numerical_value = numerical_value.replace(",", ".")
            if '.' not in numerical_value:
                numerical_value = numerical_value + ".00"
            return numerical_value
        else:
            return None

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "LimitedAvailability" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Temporarily out of stock"
                return "No", out_of_stock_text
        except Exception as e:
            return "No"


