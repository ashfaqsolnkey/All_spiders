import scrapy
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper, asyncio, aiohttp
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin, urlencode
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class coach(scrapy.Spider):
    name = "desigual"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.desigual.com/"
    handle_httpstatus_list = [404, 429, 403, 500, 430]
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
    start_urls = "https://www.desigual.com/"
    spec_mapping = '[{"countryName": "us", "lang" : "en", "codeUrl" : "en_US"},{"countryName": "gb", "lang" : "en", "codeUrl" : "en_GB"}, {"countryName": "au", "lang" : "en", "codeUrl" : "en_AU"},{"countryName": "fr", "lang" : "fr", "codeUrl" : "fr_FR"},{"countryName": "de", "lang" : "de", "codeUrl" : "en_DE"},{"countryName": "es", "lang" : "es", "codeUrl" : "es_ES"}]'

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url

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

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls,
            callback=self.country_base_url,
            headers=self.headers,
        )

    @inline_requests
    def country_base_url(self, response):
        url = 'https://www.desigual.com/en_US/'
        req = yield Request(url, headers=self.headers, dont_filter=True)
        self.get_target_urls(req, url)
        filtered_urls = list(set(self.all_target_urls))
        params = {'sz': 9999}
        for product_url in filtered_urls:
            if product_url:
                try:
                    url = product_url + '?' + urlencode(params)
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                    }
                    request = scrapy.Request(url, headers=headers, dont_filter=True)
                    resp = yield request
                    if resp.status == 200:
                        self.parse(resp, url)
                    else:
                        self.log(f"Received Response for URL: {resp.status}")
                except Exception as e:
                    print("Error in country_base_url: ", e)

        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'sku': sku_id}
            )

    def get_target_urls(self, response, base_url):
        if response:
            target_urls = response.css('a[role="button"]::attr(href)').getall()
            filter_target_urls = set(target_urls)
            for link in filter_target_urls:
                new_link = response.urljoin(link)
                if new_link not in self.all_target_urls:
                    self.all_target_urls.append(new_link)

    def parse(self, response, link):
        sku_id = ''
        print(f"response url {response.url}")
        try:
            product_elements = response.css('div.product-grid-tile')
            for product_ele in product_elements:
                product_url = product_ele.css(".pdp-link>a::attr(href)").get()
                sku_id = product_ele.css("div.product::attr(data-pid)").get()
                if product_url:
                    self.get_all_sku_mapping(product_url, sku_id)
        except Exception as e:
            print("Error in parse: ", e)

    def get_all_sku_mapping(self, product_url, sku_id):
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
    def parse_product(self, response, product_url, sku):
        url_parts = product_url.split("/")
        url_without_language = "/".join(url_parts[2:])
        color = response.css('meta[itemprop="color"]::attr(content)').get()
        list_img = list(set(response.css('img.embed-responsive-item::attr(src)').getall()))
        outer_fabric = response.css(".outside-composition span::text").get()
        inner_fabric = response.css(".inside-composition span::text").get()
        outer_fabric = "Outer fabric composition:" + outer_fabric.strip() if outer_fabric else ""
        inner_fabric = "Inner fabric composition:" + inner_fabric.strip() if inner_fabric else ""
        main_material = outer_fabric + " " + inner_fabric if outer_fabric or inner_fabric else "No Material Found"
        gender = response.css(".nav-link.dropdown-toggle.text-uppercase>span::text").get()
        # img_selectors = response.css('img.embed-responsive-item::attr(src)').getall()
        # for img_url in img_selectors:
        #     list_img.append(img_url)

        size_dimension = []
        content = {}
        specification = {}
        lang = '[{"countryName": "es_ES", "lang" : "es"}, {"countryName": "en_US", "lang" : "en"}, {"countryName": "fr_FR", "lang" : "fr"},{"countryName": "de_DE", "lang" : "de"}]'
        json_data = json.loads(lang)
        for item in json_data:
            language = item.get('lang')
            countryName = item.get('countryName')
            try:
                country_url = f"https://www.desigual.com/{countryName}/{url_without_language}"
                req = Request(country_url, headers=self.headers, dont_filter=True)
                content_response = yield req
                if content_response.status == 200:
                    content_info = self.collect_content_information(content_response)
                    content[language] = {
                        "sku_link": country_url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }

                elif content_response.status in [301, 302]:
                    try:
                        redirected_url = content_response.headers.get('Location').decode('utf-8')
                        url = response.urljoin(redirected_url)
                        content_retry_req = scrapy.Request(url, headers=self.headers,dont_filter=True)
                        content_retry_resp = yield content_retry_req
                        content_info = self.collect_content_information(content_retry_resp)
                        content[language] = {
                            "sku_link": url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
                    except Exception as e:
                        print("Error in content: ", e)
                elif content_response.status == 404:
                    self.log(f"Received 404 Response for URL: {content_response.url}")

            except Exception as e:
                print("Error in content: ", e)

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            table_rows = ''
            countryName = item.get('countryName')
            language = item.get('lang')
            codeUrl = item.get("codeUrl")
            try:
                country_url = f"https://www.desigual.com/{codeUrl}/{url_without_language}"
                req = scrapy.Request(country_url, headers=self.headers, dont_filter=True)
                country_resp = yield req
                if country_resp.status == 200:
                    specification_info = self.collect_specification_info(country_resp, table_rows, language, country_url, countryName)
                    if specification_info:
                        specification[countryName.lower()] = specification_info
                elif country_resp.status in [301, 302]:
                    redirected_url = country_resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                    country_resp = yield req
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, table_rows, language, country_url, countryName)
                        if specification_info:
                            specification[countryName.lower()] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku + "/"
                if not os.path.exists(directory):
                    os.makedirs(directory)
                for url_pic in list_img:
                    filename = str(uuid.uuid4()) + ".png"
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            req = Request(url_pic, headers=self.headers, dont_filter=True)
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
                        image_path = os.path.join(directory, filename)
                        with open(
                                os.path.join(directory, filename), "wb"
                        ) as img_file:
                            img_file.write(res.body)
                        product_images_info.append(image_path)
                    except Exception as e:
                        logging.error(f"Error processing image: {e}")

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = 'Desigual'
        item['manufacturer'] = self.name
        item['product_badge'] = ''
        item['sku'] = sku
        item['gender'] = gender
        item['sku_color'] = color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        title = ''
        sku_long_description_text = ''
        sku_short_description = ''
        try:
            sku_short_description = response.css("div.long-description p::text").get()
            all_text = response.xpath("//div[@class='collapse']//text()").getall()
            sku_long_description_text = " ".join([text.strip() for text in all_text if text.strip()])
            title = response.css('h1.product-name.page-title.text-lg-left.text-uppercase.mb-0>span::text').get()
        except Exception as e:
            print(e)

        return {
            "sku_title": title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description_text
        }

    def collect_specification_info(self, country_resp, table_rows, language, country_url, countryName):
        sizes = []
        availability = ''
        sale_price = ""
        currency_code = ''
        base_price = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        base_price = country_resp.css('span.strike-through.list.d-flex.align-items-center.value>span>meta[itemprop="price"]::attr(content)').get() or ""
        currency_code = country_resp.css('span.d-flex.flex-wrap.font-price>span::attr(data-currency)').get()
        sale_price = country_resp.css('span.d-flex.flex-wrap.font-price>span>meta::attr(content)').get() or ""
        if sale_price == "":
            return

        try:
            delivery_time = country_resp.css("p span.font-bold::text").get()
            full_text = country_resp.css("p::text").getall()
            clean_delivery_time = [text.strip() for text in full_text if any(kw in text.lower() for kw in ["day", "jour", "día"])]
            shipping_lead_time = (delivery_time + ' ' + clean_delivery_time[0]) if clean_delivery_time and clean_delivery_time[0] else None
            clean_shipping_expenses = [text.strip() for text in full_text if any(kw.lower() in text.lower() for kw in ["shipping", "envíos", "livraison"])]
            shipping_expenses = clean_shipping_expenses[0] if clean_shipping_expenses else None
        except Exception as e:
            print("Error in shipping: ", e)
        sizes = country_resp.css("p.model-size.mb-2::text").getall()
        availability_status = ''
        out_of_stock_text = ''
        availability = country_resp.css("link[itemprop='availability']::attr(href)").get()
        if availability:
            product_availability = self.check_product_availability(availability)
            availability_status = product_availability[0]
            out_of_stock_text = product_availability[1]

        return {
            "lang": language.lower(),
            "domain_country_code": countryName.lower(),
            "currency": currency_code,
            "base_price": base_price if base_price else sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": '',
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": '',
            "reviews_number": '',
            "size_available": sizes,
            "sku_link": country_url
        }

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "available " in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "Ver disponibilidad" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "availability" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Product Out of Stock"
                return "No", out_of_stock_text
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return