from urllib.parse import urljoin
import cloudscraper
import scrapy
from inline_requests import inline_requests
from scrapy.http import Request, TextResponse
from scrapy.utils.project import get_project_settings
import json
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class NoonspainSpider(scrapy.Spider):
    name = "noonspain"
    base_url = "https://noonspain.com"
    all_target_urls = []
    sku_mapping = {}
    script_content = ""
    spec_mapping ='[{"country_code": "es", "url_countryCode": "en", "country_language": "en"}]'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    start_urls = "https://noonspain.com/en"

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en;q=0.9',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'referer': 'https://noonspain.com/en/pages/new-in',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }

    handle_httpstatus_list = [404, 403, 302]
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
                country_response = requests.get(url, headers=rotate_headers(), proxies = {'http': proxy, 'https': proxy})
                target_response = TextResponse(url='', body=country_response.text, encoding='utf-8')
                self.get_target_urls(target_response)
            except Exception as e:
                self.log(f"Error occurred while processing URL {url}: {e}")
        for link in self.all_target_urls:
            if link:
                try:
                    proxy = next(self.proxy_cycle)
                    url = urljoin(self.base_url, link)
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                    if resp.status_code == 200:
                        list_product_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                        self.parse(list_product_response)
                    else:
                        self.log(f"Received Response for URL: {resp.status_code}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {link}: {e}")


        logging.info(f'Total Sku of NoonSpain : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            product = product_url['product_url']
            sku_url = urljoin(self.base_url, product)
            yield scrapy.Request(
                url=sku_url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product, 'sku_id': sku_id}
            )

    def get_target_urls(self, response):
        if response:
            product_urls = response.css('.site-nav.site-navigation li a::attr(href)').getall()
            for urls in product_urls:
                if urls not in self.all_target_urls:
                    self.all_target_urls.append(urls)

    def find_sku_by_variant_id(self, response, variant_id):
        script_tags = response.css('script::text').getall()
        for script_tag in script_tags:
            if "var meta = {" in script_tag:
                script_content = script_tag.split("var meta =")[1].split('};')[0] + '}'
                json_data = json.loads(script_content)
                for variant in json_data['product']['variants']:
                    if str(variant['id']) == variant_id:
                        return variant['sku']

    def parse(self, response):
        productUrls = response.css('.grid-product__link::attr(href)').extract()
        for product in productUrls:
            if 'variant' in product:
                try:
                    product_url = product
                    variant_id = product_url.split('variant=')[1]
                    get_sku_url = urljoin(self.base_url, product_url)
                    proxy = next(self.proxy_cycle)
                    sku_resp = requests.get(get_sku_url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                    if sku_resp.status_code == 200:
                        sku_response = TextResponse(url='', body=sku_resp.text, encoding='utf-8')
                        sku_id = self.find_sku_by_variant_id(sku_response, variant_id)
                        self.get_all_sku_mapping(product_url, sku_id)
                except Exception as e:
                    self.log(f"Error occurred while processing URL {product}: {e}")

        next_page_link = response.css('link[rel="next"]::attr(href)').get()
        if next_page_link:
            next_page = f'{self.base_url}{next_page_link}'
            try:
                proxy = next(self.proxy_cycle)
                scraper = cloudscraper.create_scraper()
                next_page_resp = scraper.get(next_page, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                if next_page_resp.status_code == 200:
                    product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                    self.parse(product_response)
            except Exception as e:
                self.log(f"Error next_page: {e}")

    def get_all_sku_mapping(self, product_url, sku_id):
        try:
            if product_url and "/en" in product_url:
                existing_url = self.sku_mapping.get(sku_id)
                if existing_url and "/en" not in existing_url:
                    self.sku_mapping[sku_id] = {'product_url': product_url}
                elif sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url}
            elif product_url and "/en" not in product_url:
                if sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url}
        except Exception as e:
            self.log(f"Error in all_sku_mapping : {e}")

    @inline_requests
    def parse_product(self, response, product_url, sku_id):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = redirected_url
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id}
            )
            return

        split_url = product_url.split('/')
        url_without_lang = '/'.join(split_url[2:])
        content = {}
        specification = {}
        main_material = ''
        size_dimension = []
        dimension = response.css('.metafield-multi_line_text_field::text').extract()
        for style in dimension:
            if 'size' in style or 'talla' in style or ' cm ' in style or ' mm ' in style:
                if "model" not in style:
                    size_dimension.append(style)

        languages_lists = ["en-ES", "pt-ES", "es-ES"]
        for language in languages_lists:
            specific_lang = language.split('-')[0]
            if specific_lang == "es":
                url = f"{self.base_url}/{url_without_lang}"
            else:
                url = f"{self.base_url}/{specific_lang}/{url_without_lang}"
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            language_resp = yield req
            if language_resp.status == 200:
                content_info = self.collect_content_information(language_resp)
                content[specific_lang.lower()] = {
                    "sku_link": content_info["sku_link"],
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            elif language_resp.status in [301, 302]:
                proxy = next(self.proxy_cycle)
                redirected_url = language_resp.headers.get(b'Location').decode('utf-8')
                url = redirected_url
                req = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                resp = TextResponse(url='', body=req.text, encoding='utf-8')
                if resp.status == 200:
                    content_info = self.collect_content_information(resp)
                    content[specific_lang.lower()] = {
                        "sku_link": content_info["sku_link"],
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            else:
                self.log(f"RECEIVED {language_resp.status} Response for URL: {language_resp.url}")

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
                    specification_info = self.collect_specification_info(specification_resp, country_code, country_language, sku_id)
                    specification[country_code.lower()] = specification_info
                elif specification_resp.status in [301, 302]:
                    proxy = next(self.proxy_cycle)
                    redirected_url = specification_resp.headers.get(b'Location').decode('utf-8')
                    url = redirected_url
                    req = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                    country_resp = TextResponse(url='', body=req.text, encoding='utf-8')
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, country_code, country_language, sku_id)
                        specification[country_code.lower()] = specification_info
                else:
                    self.log(f"RECEIVED {specification_resp} Response for URL: {specification_resp.url}")

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
        list_img = []
        image_urls = response.css('.product__thumbs--scroller a::attr(href)').getall()
        for images in image_urls:
            list_img.append(f'https:{images}')

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
        color = response.css(".variant__label.hidden-label span span[data-variant-color-label]::text").get()
        sku_color = ''
        if color:
            sku_color = color.strip()
        material = response.css('.collapsible-content--all div p::text').getall()
        if len(material) > 4:
            main_material = material[5]


        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = "Noon"
        item['product_badge'] = ''
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = sku_color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        sku_title = ""
        sku_link = ""
        sku_short_description = ""
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            sku_short_description = json_data.get("description")
            sku_title = json_data.get("name")
            sku_link = json_data.get("url")

        sku_long_description = sku_short_description
        return {
            "sku_link": sku_link,
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, country_language, sku_id):
        availability = ''
        base_price = ''
        active_price = ''
        price = ''
        priceCurrency = ''
        sku_url = ''
        shipping_expenses = ''
        shipping_lead_time = ''

        shipping_text = resp.css('.collapsible-content--all div p::text').getall()
        if len(shipping_text) > 2:
            shipping_expenses = shipping_text[0] + shipping_text[2]
            shipping_lead_time = shipping_text[3]
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            if "offers" in json_data:
                for item in json_data["offers"]:
                    if sku_id == item.get("sku"):
                        price = item.get("price")
                        priceCurrency = item.get("priceCurrency")
                        sku_url = item.get("url")
                        availability = item.get("availability")
                        break
        if price:
            active_price = str(price)
        base_price_ele = resp.css('span.product__price.product__price--compare::text').get()
        if base_price_ele:
            base_price = self.extract_price_info(base_price_ele)
        else:
            base_price = active_price
        size_available = []
        available_sizes = resp.css('select.product-single__variants option:not([disabled])::text').getall()
        try:
            size_available = [size.split('/')[1].split('-')[0].strip() for size in available_sizes]
        except Exception as e:
            print(e)

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": country_language.lower(),
            "domain_country_code": country_code.lower(),
            "currency": priceCurrency,
            "base_price": base_price if base_price else active_price,
            "sales_price": active_price if active_price else base_price,
            "active_price": active_price if active_price else base_price,
            "stock_quantity": "NA",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "Noon Spain",
            "condition": "NEW",
            "reviews_rating_value": "NA",
            "reviews_number": "NA",
            "size_available": size_available,
            "sku_link": sku_url
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