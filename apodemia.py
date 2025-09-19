from urllib.parse import urljoin
import scrapy
from inline_requests import inline_requests
from scrapy.http import Request, TextResponse
from scrapy.utils.project import get_project_settings
import json
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests
from bclowd_spider.items import ProductItem
import aiohttp
import asyncio
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

async def get_page(session, url, proxy_cycle, apod_headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=apod_headers) as response:

                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1
    return None


async def get_all(session, urls, proxy_cycle, apod_headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle, apod_headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, apod_headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=apod_headers, timeout=timeout) as session:
                data = await get_all(session, urls, proxy_cycle, apod_headers)
                return data
        except asyncio.TimeoutError:
            error_msg = 'Request timed out'
            print(error_msg)
            time.sleep(5)
            continue
        except aiohttp.client.ClientConnectionError:
            error_msg = 'ClientConnectionError'
            print(error_msg)
            time.sleep(5)
            continue


class ApodemiaSpider(scrapy.Spider):
    name = "apodemia"
    all_target_urls = []
    sku_mapping = {}

    spec_mapping = '[{ "country_code": "ES","name": "Spain", "currencyCode": "EUR","url_country_code": "en", "shipping_charge":"€2.99", "shipping_time":"Delivery time 2 to 4 days" },{ "country_code": "US","name": "United States", "currencyCode": "EUR","url_country_code": "us", "shipping_charge":"€2.99", "shipping_time":"Delivery time 5 to 7 days" }, { "country_code": "MX","name": "Mexico", "currencyCode": "MXN", "url_country_code": "mx/en", "shipping_charge":"€2.99", "shipping_time":"Delivery time 5 to 7 days" },{ "country_code": "DE","name": "Germany", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":" Delivery time 3 to 5 days" }, { "country_code": "AT","name": "Austria", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 5 to 7 days" }, { "country_code": "FI","name": "Finland", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 5 to 7 days" }, { "country_code": "FR","name": "France", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" },{ "country_code": "GR","name": "Greece", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" }, { "country_code": "IT","name": "Italy", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" }, { "country_code": "LU","name": "Poland", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" }, { "country_code": "PT","name": "Portugal", "currencyCode": "EUR","url_country_code": "en-eu" , "shipping_charge":"€2.99", "shipping_time":"Delivery time 2 to 4 days"}, { "country_code": "SE","name": "Sweden", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" },{ "country_code": "NL","name": "Netherland", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" }, { "country_code": "BE","name": "Belgium", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" }, { "country_code": "CH","name": "Switzerland", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 3 to 5 days" }, { "country_code": "CZ","name": "Czechia", "currencyCode": "EUR","url_country_code": "en-eu", "shipping_charge":"€2.99", "shipping_time":"Delivery time 5 to 7 days" }]'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://apodemia.com"
    start_urls = "https://apodemia.com"
    apod_headers = headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }

    handle_httpstatus_list = [404, 403, 500, 430, 302, 301]
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
            headers=self.apod_headers,
        )

    @inline_requests
    def country_base_url(self, response):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield scrapy.Request(
                url,
                callback=self.country_base_url,
                headers=self.apod_headers,
                dont_filter=True,
            )
            return

        fetched_urls = response.css('link[rel="alternate"]::attr(href)').getall()
        en_urls = [url for url in fetched_urls if "/en" in url]
        country_urls_list = list(set(en_urls))
        for url in country_urls_list:
            try:
                req = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
                country_response = yield req
                if country_response.status == 200:
                    self.get_target_urls(country_response, url)
                elif country_response.status in [301, 302]:
                    redirected_url = country_response.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
                    target_response = yield req
                    self.get_target_urls(target_response, url)

            except Exception as e:
                self.log(f"Error occurred while processing URL {url}: {e}")

        for link in self.all_target_urls:
            try:
                req = scrapy.Request(link, headers=rotate_headers(), dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    self.parse(resp, link)
                else:
                    self.log(f"Received Response for URL: {resp.status}")
            except Exception as e:
                self.log(f"Error occurred while processing URL {link}: {e}")

        logging.info(f'Total Sku of Apodemia : {len(self.sku_mapping)}')
        for sku_id, data in self.sku_mapping.items():
            product_url = data['product_url']
            badge = data.get('badge', None)
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url, "badge": badge}
            )

    def get_target_urls(self, response, url):
        if response:
            product_urls = response.css('.mega-menu__list a::attr(href)').getall()
            product_urls_more = response.css('div.image-block__btn>a::attr(href)').getall()
            product_url = response.css(
                'a.drawer-menu__list-title-label.unstyled-link.link-parent-for-hover::attr(href)').getall()
            add_product_urls = product_urls_more + product_urls + product_url
            for urls in add_product_urls:
                if '#' in urls:
                    continue
                else:
                    if 'https' not in urls:
                        urls = urljoin(url, urls)
                        if urls not in self.all_target_urls:
                            self.all_target_urls.append(urls)
                    else:
                        if urls not in self.all_target_urls:
                            self.all_target_urls.append(urls)

    def parse(self, response, url):
        badge = ''
        product_urls = response.css("div.shop__grid-item")
        scr = response.xpath('/html/body/script').extract()
        scripts = response.css("script#web-pixels-manager-setup").get()
        skus = re.findall(r'"sku":"(\d+)"', scripts)
        for products, sku in zip(product_urls, skus):
            product_link = products.css('a::attr(href)').get()
            product_url = urljoin(url, product_link)
            badge = products.css(".product--labels-container>div.product--featured-tag::text").get(default='')
            if badge:
                badge = badge.strip()
            self.get_all_sku_mapping(product_url, sku, badge)

        next_page_link = response.css(".load-button-pagination__btn::attr(data-url)").get()
        if next_page_link:
            try:
                loop = asyncio.get_event_loop()
                next_page_url = urljoin(url, next_page_link)
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.apod_headers))
                for result in results:
                    if result:
                        next_response = TextResponse(url=next_page_link, body=result, encoding='utf-8')
                        self.parse(next_response, next_page_url)
            except Exception as e:
                self.log(e)

    def get_all_sku_mapping(self, product_url, sku_id, badge):
        try:
            if product_url and "/en" in product_url:
                existing_url = self.sku_mapping.get(sku_id)
                if existing_url and "/en" not in existing_url:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}
                elif sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}
            elif product_url and "/en" not in product_url:
                if sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}
        except Exception as e:
            print(f"Exc {e}")

    @inline_requests
    def parse_product(self, response, product_url, badge):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                headers=rotate_headers(),
                dont_filter=True,
                cb_kwargs={'product_url': product_url, "badge": badge}

            )
            return
        if product_url.startswith('/collections'):
            url_without_lang = product_url.replace("/", "", 1)
        elif '/en' in product_url:
            url_parts = product_url.split("/")
            url_without_lang = "/".join(url_parts[4:])
        else:
            url_parts = product_url.split("/")
            url_without_lang = "/".join(url_parts[3:])
        content = {}
        specification = {}
        sku_id = ''
        brand = ''
        gtin13 = ''
        list_img = []

        size_dimension = []
        size_dim_list = response.css(".product-information-tag__body p::text").getall()
        size_list = [size.lower() for size in size_dim_list]

        keywords = ['height', 'width', 'thickness', 'length', 'separation', 'diameter', 'ALTO', 'ANCHO', 'GROSOR']
        size_dimension = [item for item in size_list if any(keyword in item for keyword in keywords)]

        main_material = ''
        if size_list:
            keywords = ["material", "finish", "stone", "acabado"]
            for item in size_list:
                if any(keyword in item.lower() for keyword in keywords):
                    main_material = item.split(":")[1]
                    break

        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            if "offers" in json_data:
                brand = json_data['brand'].get("name")
                sku_id = json_data.get('sku')
                for offer in json_data['offers']:
                    sku13 = offer['sku']
                    if sku13 == sku_id:
                        if 'gtin13' in offer:
                            gtin = offer['gtin13']
                            gtin13 = str(gtin)
                    else:
                        continue
            break
        languages = ["en", "es-eu"]
        for language in languages:
            url = f"{self.base_url}/{language}/{url_without_lang}"
            req = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
            language_resp = yield req
            if language_resp.status == 404:
                self.log(f"RECEIVED 404 Response for URL: {language_resp.url}")
            elif language_resp.status in [301, 302]:
                redirected_url = language_resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
                resp = yield req
                content_info = self.collect_content_information(resp, size_list, main_material)
                content[language.split("-")[0]] = {
                    "sku_link": resp.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            else:
                content_info = self.collect_content_information(language_resp, size_list, main_material)
                content[language.split("-")[0]] = {
                    "sku_link": language_resp.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }

        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('country_code')
                currency_code = item.get('currencyCode')
                url_country_code = item.get('url_country_code')
                shipping_expenses = item.get('shipping_charge')
                shipping_lead_time = item.get('shipping_time')

                if country_code in ["MX", 'US']:
                    url = f'{"https://apodemia."}{url_country_code}/{url_without_lang}?country={country_code.upper()}'
                else:
                    url = f'{self.base_url}/{url_country_code}/{url_without_lang}?country={country_code.upper()}'

                req = scrapy.Request(url, headers=rotate_headers(), dont_filter=True)
                resp = yield req
                if resp.status == 404:
                    self.log(f"RECEIVED 404 Response for URL: {resp.url}")
                elif resp.status in [301, 302]:
                    redirected_url = resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = scrapy.Request(url, headers=rotate_headers())
                    req.meta['dont_redirect'] = True
                    resp = yield req
                    if resp.status == 200:
                        specification_info = self.collect_specification_info(resp, country_code,
                                                                             currency_code, shipping_lead_time,
                                                                             shipping_expenses)
                        specification[country_code.lower()] = specification_info
                else:
                    specification_info = self.collect_specification_info(resp, country_code, currency_code,
                                                                         shipping_lead_time, shipping_expenses)
                    specification[country_code.lower()] = specification_info


        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return
        list_img_without_http = response.css('.product-media-grid--two-column img::attr(src)').getall()
        if not list_img_without_http:
            list_img_without_http = response.css('.product-media-grid > div > div>product-modal-button > img::attr(src)').getall()
        for images in list_img_without_http:
            split_img = images.split("?")[0]
            if 'https:' not in split_img:
                img = 'https:' + split_img
                if img not in list_img:
                   list_img.append(img)

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku_id + '/'
                if not os.path.exists(directory):
                    os.makedirs(directory)
                for url_pic in list_img:
                    filename = str(uuid.uuid4()) + ".png"
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            req = Request(url_pic)
                            res = yield req
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
                    try:
                        with open(
                                os.path.join(directory, filename), "wb"
                        ) as img_file:
                            img_file.write(res.body)
                        image = Image.open(os.path.join(directory, filename))
                        image.save(os.path.join(directory, filename))
                        image_info = directory + "/" + filename
                        product_images_info.append(image_info)
                    except Exception as e:
                        logging.error(f"Error processing image: {e}")

        product_color = ''
        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        color = response.css("div.colors-selection__tooltip::text").get() or " "
        if color:
            product_color = color.strip()

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = brand
        item['product_badge'] = badge
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['gtin13'] = gtin13
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response, size_list, material):
        description_text = []
        short_description = ' '.join(size_list) if size_list else ""
        sku_short_description = material + short_description
        sku_title = response.css('.product-general-info-block h1::text').get()
        description_text = response.css(
            '.product-content-tab__text.body-font-weight-from-global-settings > p::text, p.ContentPasted0 span::text ').getall()
        if len(description_text) == 0:
            description_text = response.css(
                '.body3.body-color.body-font-weight-from-global-settings > p::text').extract()
            if len(description_text) == 0:
                script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
                for script_tag in script_tag_content:
                    json_data = json.loads(script_tag)
                    if "description" in json_data:
                        description = json_data["description"]
                        description_text.append(description)

        sku_long_desc = ' '.join(item for item in description_text)
        sku_long_description = sku_long_desc + sku_short_description
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, currency_code, shipping_lead_time, shipping_expenses):
        availability = ''
        sale_price = ''
        size = []
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            if "offers" in json_data:
                offers = json_data["offers"][0]
                sale_price = offers.get('price')
                currency_code = offers.get('priceCurrency')
                availability = offers.get("availability")
                break
        if sale_price:
            sale_price = str(sale_price)
        price_string = ''
        price_old = resp.css('div.product-price__old-price::text').get()
        if price_old:
            price_string = price_old.strip()
        if price_string is not None and len(price_string) > 0:
            base_price = self.extract_price_info(str(price_string))
        else:
            base_price = sale_price

        size_available = resp.css("div.product-variant-picker__pill-list label span.pill__label::text").getall()
        for item in size_available:
            if item not in size:
                size.append(item)
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": "en",
            "domain_country_code": country_code.lower(),
            "currency": currency_code,
            "base_price": base_price if base_price else sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": "",
            "reviews_number": "",
            "size_available": size,
            "sku_link": resp.url
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