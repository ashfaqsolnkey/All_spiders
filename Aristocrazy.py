import scrapy
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from scrapy.http import Request
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from PIL import Image
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

class Aristocrazy(scrapy.Spider):
    name = "aristocrazy"
    all_target_urls = []
    sku_mapping = {}
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    base_url = "https://www.aristocrazy.com/"
    start_url = "https://www.aristocrazy.com/es/en/home"
    handle_httpstatus_list = [430, 404, 403,301,302]
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
        yield Request(
            self.start_url,
            callback=self.country_base_url,
            headers=rotate_headers(),
            dont_filter=True
        )

    spec_mapping = '[{"countryCode": "us", "url_countryCode": "es/en","locale": "en/en_US","currencyCode": "EUR"}, {"countryCode": "es", "url_countryCode": "es/en","locale": "es/en","currencyCode": "EUR"}, { "countryCode": "fr","url_countryCode": "fr","locale": "fr","currencyCode": "EUR"}, { "countryCode": "pt","url_countryCode": "es/en","locale": "es/en","currencyCode": "EUR"}, { "countryCode": "at","url_countryCode": "es/en","locale": "en/en_AT","currencyCode": "EUR"},{ "countryCode": "be","url_countryCode": "es/en","locale": "en/en_BE","currencyCode": "EUR"},{ "countryCode": "ca","url_countryCode": "es/en","locale": "en/en_CA","currencyCode": "EUR"}, { "countryCode": "cl","url_countryCode": "es/en","locale": "en/en_CL","currencyCode": "EUR"}, { "countryCode": "cz","url_countryCode": "es/en","locale": "en/en_CZ","currencyCode": "EUR"}, { "countryCode": "DE","url_countryCode": "es/en","locale": "en/en_DE","currencyCode": "EUR"}, { "countryCode": "DK","url_countryCode": "es/en","locale": "en/en_DK","currencyCode": "EUR"}, { "countryCode": "gr","url_countryCode": "es/en","locale": "en/en_GR","currencyCode": "EUR"}, { "countryCode": "lu","url_countryCode": "es/en","locale": "en/en_LU","currencyCode": "EUR"}, { "countryCode": "mc","url_countryCode": "es/en","locale": "en/en_MC","currencyCode": "EUR"}, { "countryCode": "nl","url_countryCode": "es/en","locale": "en/en_NL","currencyCode": "EUR"}, { "countryCode": "ch","url_countryCode": "es/en","locale": "en/en_CH","currencyCode": "EUR"}, { "countryCode": "sr","url_countryCode": "sau","locale": "sau","currencyCode": "EUR"}]'

    @inline_requests
    def country_base_url(self, response):
        filtered_urls = []
        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                url_countryCode = item.get('url_countryCode')
                if url_countryCode == "fr":
                    url = f'{self.base_url}{url_countryCode}/accueil'
                else:
                    url = f'{self.base_url}{url_countryCode}/home'
                filtered_urls.append(url)
        except Exception as e:
            print(e)
        country_urls_list = list(set(filtered_urls))
        for url in country_urls_list:
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            resp = yield req
            if resp.status == 200:
                self.get_target_urls(resp)
            elif resp.status == 301:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                country_req = Request(url, headers=rotate_headers(), dont_filter=True)
                country_resp = yield country_req
                self.get_target_urls(country_resp)

        params = {'sz': 99999}
        for link in self.all_target_urls:
            product_url = link
            if product_url:
                url = product_url + '?' + urlencode(params)
                request = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
                resp = yield request
                if resp.status == 200:
                    self.parse(resp)
                elif resp.status in [301, 302]:
                    redirected_url = resp.headers.get('Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    country_req = Request(url, headers=rotate_headers(), dont_filter=True)
                    country_resp = yield country_req
                    if country_resp.status == 200:
                        self.parse(country_resp)
                else:
                    self.log(f"Received {resp.status} Response for URL: {resp.status}")

        logging.info(f'Total Sku of Aristocrazy : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url}
            )

    def get_target_urls(self, response):
        if response:
            target_urls = response.css('.navbar-nav li a::attr(href)').getall()
            filter_target_urls = set(target_urls)
            for link in filter_target_urls:
                if any(keyword in link for keyword in ['Login', 'cliente', 'Wishlist']):
                    continue
                elif link.startswith('javascript'):
                    continue
                else:
                    new_link = response.urljoin(link)
                    if new_link not in self.all_target_urls:
                        self.all_target_urls.append(new_link)

    def parse(self, response):
        sku_id = ''
        product_elements = response.css("div.product-content-tiles")
        for product_ele in product_elements:
            product_url = product_ele.css('.pdp-link>.link::attr(href)').get()
            product_element = product_ele.css('div.product[data-pid]')
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
    def parse_product(self, response, product_url):
        if response.status == 200:
            content = {}
            specification = {}
            url_parts = product_url.split("/")
            if 'fr/' in product_url:
                url_without_language = "/".join(url_parts[2:])
            elif 'int/' in product_url:
                url_without_language = "/".join(url_parts[4:])
            else:
                url_without_language = "/".join(url_parts[3:])

            languages = ["es/en", "fr", "es"]
            for language in languages:
                if language == "es/en":
                    split_language = language.split("/")[1]
                else:
                    split_language = language
                new_url = f'{self.base_url}{language}/{url_without_language}'
                req = Request(new_url, headers=rotate_headers(), dont_filter=True)
                language_resp = yield req
                if language_resp.status == 200:
                    content_info = self.collect_content_information(response)
                    content[split_language] = {
                        "sku_link": new_url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
                elif language_resp.status in [301, 302]:
                    redirected_url = language_resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = Request(url, headers=rotate_headers(), dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        content_info = self.collect_content_information(resp)
                        content[split_language] = {
                            "sku_link": url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
                else:
                    self.log(f"RECEIVED 404 Response for URL: {language_resp.url}")

            try:
                json_data = json.loads(self.spec_mapping)
                for item in json_data:
                    country_code = item.get('countryCode').lower()
                    locale = item.get('locale')
                    currency_code = item.get('currencyCode')
                    if country_code in ['fr', 'es', 'pt', 'ad', 'sau']:
                        url = f'{self.base_url}{locale}/{url_without_language}'
                    else:
                        url = f'{self.base_url}int/{locale}/{url_without_language}'
                    req = Request(url, headers=rotate_headers(), dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        specification_info = self.collect_specification_info(resp, country_code, currency_code, url)
                        specification[country_code.lower()] = specification_info

                    elif resp.status in [301, 302]:
                        redirected_url = resp.headers.get('Location').decode('utf-8')
                        url = response.urljoin(redirected_url)
                        country_req = Request(url, headers=rotate_headers(), dont_filter=True)
                        country_resp = yield country_req
                        if country_resp.status == 200:
                            specification_info = self.collect_specification_info(country_resp, country_code, currency_code, url)
                            specification[country_code] = specification_info

                    else:
                        self.log(f"Received 404 response for URL: {resp.url}")
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

            list_img = []
            mpn = ''
            sku_id = ''
            script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
            if script_tag_content:
                for script_content in script_tag_content:
                    try:
                        json_data = json.loads(script_content)
                        if json_data:
                            sku_id = json_data.get("sku")
                            image = json_data.get("image")
                            mpn = json_data.get("mpn")
                            if image:
                                for img in image:
                                    if '?' in img:
                                        img = img.split("?")[0]
                                    list_img.append(img)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")

            domain, domain_url = self.extract_domain_domain_url(response.url)
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

            time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            product_color = response.css('.color-piedra.principal strong::text').get() or ''
            secondary_material = response.css('span.attribute-values.piedra-principal strong::text').get() or ''
            main_material = response.css('.attribute-values.metal-baño strong::text').get()

            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['collection_name'] = ""
            item['brand'] = 'Aristocrazy'
            item['product_badge'] = ""
            item['manufacturer'] = self.name
            item['sku'] = sku_id
            item['mpn'] = mpn
            item['sku_color'] = product_color
            item['main_material'] = main_material
            item['secondary_material'] = secondary_material
            item['image_url'] = product_images_info
            item['size_dimensions'] = []
            item['content'] = content
            item['specification'] = specification
            yield item

    def handle_error(self, failure):
        if failure.check(HttpError):
            response = failure.value.response
            status = response.status
            if status == 404:
                if 'sau' in response.url:
                    self.log(f'404 error for sau: {response.url}')
                    return None
                else:
                    self.log(f'404 error: {response.url}')
            else:
                self.log(f'HTTP error {status} on {response.url}')
        elif failure.check(DNSLookupError):
            request = failure.request
            self.log(f'DNS lookup failed: {request.url}')
        else:
            self.log(f'Error processing request: {repr(failure)}')

    def collect_content_information(self, resp):
        short_description = resp.css('.long-description::text').get(default="").strip()
        description_text = resp.css('.arisua-attributes span.label::text, .arisua-attributes strong::text').getall()
        descriptions_text = ' '.join(text.strip() for text in description_text)
        sku_long_description = short_description + descriptions_text
        sku_title = resp.css('h1.product-name::text').get().strip()
        return {
            "sku_title": sku_title,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, currency_code, url):
        if resp.status == 200:
            availability = ""
            base_price = ""
            sales_price = ""
            availability_status = ""
            out_of_stock_text = ""
            shipping_expenses = ""
            script_tag_content = resp.css('script[type="application/ld+json"]::text').get()
            if script_tag_content:
                json_data = json.loads(script_tag_content)
                offers = json_data.get("offers", {})
                offer_type = offers.get("@type")
                if offer_type == "Offer":
                    sales_price = offers.get("price")
                    base_price = sales_price
                elif offer_type == "AggregateOffer":
                    sales_info = offers.get("lowprice", {}).get("sales", {})
                    sales_price = sales_info.get("decimalPrice")
                    base_info = offers.get("highprice", {}).get("sales", {})
                    base_price = base_info.get("decimalPrice")
                availability = json_data["offers"].get("availability")

            peninsula_shipping = resp.css('.shiping-and-returns ul li:contains("Peninsula")::text').getall()
            if not peninsula_shipping:
                peninsula_shipping = resp.css('.shiping-and-returns ul li:contains("Péninsule")::text').getall()

            ceuta_and_others_shipping = resp.css('.shiping-and-returns ul li:contains("Ceuta")::text').getall()
            if not ceuta_and_others_shipping:
                ceuta_and_others_shipping = resp.css('.shiping-and-returns ul li:contains("Envío")::text').getall()

            shipping_text = ' '.join(resp.css('span.ml-3 a:contains("Free shipping for")::text').getall())
            if not shipping_text:
                shipping_text = ' '.join(resp.css('span.ml-3 a:contains("Livraison gratuite pour les")::text').getall())
                if not shipping_text:
                    shipping_text = ' '.join(
                        resp.css('.shiping-and-returns p:contains("Delivery is free for purchases")::text').getall())

            if peninsula_shipping or ceuta_and_others_shipping:
                shipping_expenses = "\n".join(peninsula_shipping + ceuta_and_others_shipping)
            if availability:
                product_availability = self.check_product_availability(availability)
                availability_status = product_availability[0]
                out_of_stock_text = product_availability[1]

            sizes = [size.strip() for size in resp.css('.container-button button[data-attr-value]::text').extract()]
            return {
                "lang": country_code if country_code == 'fr' else "en",
                "domain_country_code": country_code,
                "currency": currency_code,
                "base_price": base_price,
                "sales_price": sales_price,
                "active_price": sales_price,
                "stock_quantity": "",
                "availability": availability_status,
                "availability_message": out_of_stock_text,
                "shipping_lead_time": shipping_expenses,
                "shipping_expenses": shipping_text,
                "marketplace_retailer_name": "Aristocrazy",
                "condition": "NEW",
                "reviews_rating_value": "",
                "reviews_number": "",
                "size_available": sizes,
                "sku_link": url
            }

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