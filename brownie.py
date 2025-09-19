import scrapy
from bs4 import BeautifulSoup
from inline_requests import inline_requests
from scrapy.http import Request, TextResponse
from scrapy.utils.project import get_project_settings
import json
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class BrownieSpider(scrapy.Spider):
    name = "brownie"
    base_url = "https://www.browniespain.com"
    all_target_urls = []
    sku_mapping = {}

    spec_mapping = '[{"country_code": "us", "url_countryCode": "en", "country_language": "en"  }, {"country_code": "es", "url_countryCode": "es/es", "country_language": "es"}, {"country_code": "fr", "url_countryCode": "FR", "country_language": "fr"}, {"country_code": "be", "url_countryCode": "be/fr", "country_language": "fr"}, {"country_code": "ar", "url_countryCode": "en", "country_language": "en"}, {"country_code": "it", "url_countryCode": "it", "country_language": "it"}, {"country_code": "ca", "url_countryCode": "en", "country_language": "en"}, {"country_code": "cl", "url_countryCode": "en", "country_language": "en"}, {"country_code": "co", "url_countryCode": "en", "country_language": "en"}, {"country_code": "cz", "url_countryCode": "en", "country_language": "en"}, {"country_code": "dk", "url_countryCode": "en", "country_language": "en"}, {"country_code": "nl", "url_countryCode": "nl", "country_language": "nl"}, {"country_code": "no", "url_countryCode": "en", "country_language": "en"}, {"country_code": "pe", "url_countryCode": "en", "country_language": "en"}, {"country_code": "ph", "url_countryCode": "en", "country_language": "en"}, {"country_code": "pt", "url_countryCode": "PT", "country_language": "pt"}, {"country_code": "ir", "url_countryCode": "en", "country_language": "en"}, {"country_code": "se", "url_countryCode": "en", "country_language": "en"}, {"country_code": "ch", "url_countryCode": "en", "country_language": "en"}, {"country_code": "gr", "url_countryCode": "en", "country_language": "en"}, {"country_code": "ua", "url_countryCode": "en", "country_language": "en"}, {"country_code": "bu", "url_countryCode": "en", "country_language": "en"}, {"country_code": "de", "url_countryCode": "de", "country_language": "de"}, {"country_code": "ec", "url_countryCode": "en", "country_language": "en"}, {"country_code": "ee", "url_countryCode": "en", "country_language": "en"}, {"country_code": "fi", "url_countryCode": "en", "country_language": "en"}, {"country_code": "hu", "url_countryCode": "en", "country_language": "en"}, {"country_code": "li", "url_countryCode": "en", "country_language": "en"}, {"country_code": "lu", "url_countryCode": "en", "country_language": "en"}, {"country_code": "at", "url_countryCode": "en", "country_language": "en"}, {"country_code": "pa", "url_countryCode": "en", "country_language": "en"}, {"country_code": "pl", "url_countryCode": "en", "country_language": "en"}, {"country_code": "ro", "url_countryCode": "en", "country_language": "en"}, {"country_code": "rs", "url_countryCode": "en", "country_language": "en"}, {"country_code": "sk", "url_countryCode": "en", "country_language": "en"}, {"country_code": "sl", "url_countryCode": "en", "country_language": "en"}]'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    start_urls = "https://www.browniespain.com/en/"
    handle_httpstatus_list = [404, 403, 500, 430, 302, 301, 503]
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

    def country_base_url(self, response):
        fetched_urls = []
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            url_country_code = item.get('url_countryCode')
            country_url = f'{self.base_url}/{url_country_code}/'
            fetched_urls.append(country_url)

        country_urls_list = list(set(fetched_urls))
        for url in country_urls_list:
            try:
                proxy = next(self.proxy_cycle)
                country_response = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                target_response = TextResponse(url='', body=country_response.text, encoding='utf-8')
                self.get_target_urls(target_response)
            except Exception as e:
                self.log(f"Error occurred while processing URL {url}: {e}")

        for link in self.all_target_urls:
            try:
                if 'ajax' in link:
                    list_product_response = link
                else:
                    list_product_response = f"{link}?ajax=1"
                proxy = next(self.proxy_cycle)
                resp = requests.get(list_product_response, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                if resp.status_code == 200:
                    product_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                    self.parse(product_response)
            except Exception as e:
                self.log(f"Error occurred while processing all_target_urls {link}: {e}")

        for sku_id, data in self.sku_mapping.items():
            product_url = data['product_url']
            material = data['material']
            yield scrapy.Request(
                    url=product_url,
                    callback=self.parse_product,
                    headers=rotate_headers(),
                    cb_kwargs={'product_url': product_url, 'material': material, 'sku_id': sku_id}
            )

    def get_target_urls(self, response):
        if response:
            product_urls = response.css('.advtm_open_on_hover li a::attr(href)').getall()
            for urls in product_urls:
                if '#' in urls:
                    continue
                else:
                    if urls not in self.all_target_urls:
                        self.all_target_urls.append(urls)

    def parse(self, response):
        next_page_url = ''
        try:
            product_json = response.text
            data = json.loads(product_json)
            if data:
                parse_json = data['products']
                pagination = data['pagination']['pages']
                next_page_url = self.extract_next_url(pagination)

                for product in parse_json:
                    product_url = product['link']
                    sku_id = product['reference']
                    material = product['description_short']
                    if sku_id:
                        self.get_all_sku_mapping(product_url, sku_id, material)
                    else:
                        continue
        except Exception as e:
            self.log(f"Error occurred while Json processing in parse: {e}")

        if next_page_url:
            try:
                proxy = next(self.proxy_cycle)
                next_page_resp = requests.get(next_page_url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                if next_page_resp.status_code == 200:
                    product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                    self.parse(product_response)
            except Exception as e:
                self.log(f"Error next_page: {e}")

    def get_all_sku_mapping(self, product_url, sku_id, material):
        try:
            if product_url and "/en" in product_url:
                existing_url = self.sku_mapping.get(sku_id)
                if existing_url and "/en" not in existing_url:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'material': material}
                elif sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'material': material}
            elif product_url and "/en" not in product_url:
                if sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'material': material}
        except Exception as e:
            print(f"Exc {e}")

    @inline_requests
    def parse_product(self, response, product_url, sku_id, material):
        if response.status == 200:
            if "es/es" in product_url:
                split_url = product_url.split('/')
                url_without_lang = "/".join(split_url[-2:])
            else:
                split_url = product_url.split('/')
                url_without_lang = '/'.join(split_url[4:])
            content = {}
            specification = {}
            mpn = ''
            gtin13 = ''
            main_material = ''
            list_img = []
            size_dimension = []
            if material:
                soup = BeautifulSoup(material, "html.parser")
                main_material = soup.get_text()

            script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
            for script_tag in script_tag_content:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    mpn = json_data["mpn"]
                    offers = json_data["offers"]
                    gtin13 = offers.get('gtin13')
                    list_img = offers['image']
                    break

            languages_urls = ["en", "es/es", "es/ca", "FR", "PT", "nl", "de", "it"]
            # languages_urls = response.css('link[rel="alternate"]::attr(href)').getall()
            for language in languages_urls:
                if "/" in language:
                    specific_lang = language.split('/')[1]
                else:
                    specific_lang = language
                url = f'{self.base_url}/{language}/{url_without_lang}'
                req = Request(url, headers=rotate_headers(), dont_filter=True)
                language_resp = yield req
                if language_resp.status == 200:
                    content_info = self.collect_content_information(language_resp)
                    content[specific_lang.lower()] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
                elif language_resp.status in [301, 302]:
                    proxy = next(self.proxy_cycle)
                    try:
                        redirected_url = language_resp.headers.get(b'Location').decode('utf-8')
                        url = response.urljoin(redirected_url)
                        req = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                        resp = TextResponse(url='', body=req.text, encoding='utf-8')
                        if resp.status == 200:
                            content_info = self.collect_content_information(resp)
                            content[specific_lang.lower()] = {
                                "sku_link": url,
                                "sku_title": content_info["sku_title"],
                                "sku_short_description": content_info["sku_short_description"],
                                "sku_long_description": content_info["sku_long_description"]
                            }
                    except Exception as e:
                        print(e)
                else:
                    self.log(f"RECEIVED 404 Response for URL: {language_resp.url}")

            try:
                json_data = json.loads(self.spec_mapping)
                for item in json_data:
                    country_code = item.get('country_code')
                    url_country_code = item.get('url_countryCode')
                    country_language = item.get('country_language')

                    url = f'{self.base_url}/{url_country_code}/{url_without_lang}'
                    req = Request(url, headers=rotate_headers(), dont_filter=True)
                    specification_resp = yield req

                    if specification_resp.status == 200:
                        specification_info = self.collect_specification_info(specification_resp, country_code, country_language)
                        specification[country_code.lower()] = specification_info
                    elif specification_resp.status in [301, 302]:
                        try:
                            proxy = next(self.proxy_cycle)
                            redirected_url = specification_resp.headers.get(b'Location').decode('utf-8')
                            url = response.urljoin(redirected_url)
                            req = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                            country_resp = TextResponse(url='', body=req.text, encoding='utf-8')
                            if country_resp.status == 200:
                                specification_info = self.collect_specification_info(country_resp, country_code, country_language)
                                specification[country_code.lower()] = specification_info
                        except Exception as e:
                            print(e)
                    else:
                        self.log(f"RECEIVED 404 Response for URL: {specification_resp.url}")

            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')

            is_production = get_project_settings().get("IS_PRODUCTION")
            product_images_info = []
            if is_production:
                product_images_info = upload_images_to_azure_blob_storage(
                    self, list_img
                )
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

            domain, domain_url = self.extract_domain_domain_url(response.url)
            time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            sku_color = response.css(".group\_color.mobile span.text-color::text").get()
            gender = response.css('#naiz-application-recommend-input-gender::attr(value)').get()

            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['collection_name'] = ''
            item['brand'] = "Brownie"
            item['product_badge'] = ''
            item['gender'] = gender
            item['manufacturer'] = self.name
            item['sku'] = sku_id
            item['mpn'] = mpn
            item['gtin13'] = gtin13
            item['sku_color'] = sku_color
            item['main_material'] = main_material
            item['secondary_material'] = ''
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimension
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response):
        sku_short_description = response.css('.product_descr::text ').get()
        sku_title = response.css('.h1.product_title::text').get()
        sku_long_description = sku_short_description
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, country_language):
        availability = ''
        base_price = ''
        price = resp.css('.col_info_to_fixed.col_fixed div span.regular-price::text').get()
        if price:
            base_price = self.extract_price_info(price)
        active_price = ''
        currency_code = ''
        item_url = ''
        shipping_expenses = ''
        shipping_lead_time = ''

        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            if "offers" in json_data:
                offers = json_data["offers"]
                active_price = offers.get('price')
                currency_code = offers.get('priceCurrency')
                item_url = offers.get('url')
                availability = offers.get("availability")
                break

        shipping_text = resp.css(".col_info_to_fixed div.panel-info.shipping ul li::text").extract()
        if len(shipping_text) > 0 and country_code == "es":
            shipping_expenses = shipping_text[1]
            shipping_lead_time = shipping_text[2]
        elif len(shipping_text) > 0:
            shipping_expenses = shipping_text[0]
            shipping_lead_time = shipping_text[1]

        size_extract = resp.css(".group_tallas.oculto.mobile label::text").getall()
        size_available = [size.strip() for size in size_extract if size.strip()]

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": country_language.lower(),
            "domain_country_code": country_code.lower(),
            "currency": currency_code,
            "base_price": base_price if base_price else active_price,
            "sales_price": active_price,
            "active_price": active_price,
            "stock_quantity": "NA",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "Brownie Spain",
            "condition": "NEW",
            "reviews_rating_value": "NA",
            "reviews_number": "NA",
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
            else:
                out_of_stock_text = "Temporarily out of stock"
                return "No", out_of_stock_text
        except Exception as e:
            return "No"

    def extract_next_url(self, data):
        next_url = None
        if isinstance(data, dict):
            for key, item in data.items():
                if item.get('type') == 'next':
                    next_url = item.get('url')
                    break
        elif isinstance(data, list):
            for item in data:
                if item.get('type') == 'next':
                    next_url = item.get('url')
                    break
        return next_url
