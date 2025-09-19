import scrapy, webcolors
from inline_requests import inline_requests
from scrapy.utils.project import get_project_settings
from scrapy.http import Request, TextResponse
from webcolors import CSS3_NAMES_TO_HEX, HTML4_NAMES_TO_HEX, CSS21_NAMES_TO_HEX
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests, json, asyncio, aiohttp
from urllib.parse import urljoin
from itertools import cycle
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

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


async def get_page(session, url, proxy_cycle):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url,proxy=f"http://{proxy}", headers=headers, timeout=40) as response:
                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1

    return None


async def get_all(session, urls,proxy_cycle, headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                data = await get_all(session, urls, proxy_cycle,headers)
                return data
        except asyncio.TimeoutError:
            error_msg = 'Request timed out'
            print(error_msg)
            continue
        except aiohttp.client.ClientConnectionError:
            error_msg = 'ClientConnectionError'
            print(error_msg)
            continue


class Pdpaola(scrapy.Spider):
    name = "pdpaola"
    sku_mapping = {}
    base_url = "https://www.pdpaola.com"
    delivery_api = "https://assets.pdpaola.com/shipping-methods/shipping-methods-v2.json"
    # spec_mapping = '[{"countryCode":"DE","countryName":"Albania","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"IT","countryName":"Italy","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"ES","countryName":"Spain","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"US","countryName":"United States","currencyCode":"USD","currencySymbol":"$"},{"countryCode":"PT","countryName":"Portugal","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"GB","countryName":"United Kingdom","currencyCode":"GBP","currencySymbol":"£"},{"countryCode":"FR","countryName":"France","currencyCode":"EUR","currencySymbol":"€"}]'
    spec_mapping = '[{"countryCode":"US","countryName":"United States","currencyCode":"USD","currencySymbol":"$"}]'
    product_id_mapping = {}
    delivery_data = []
    target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 429, 408, 302, 404]

    download_delay = 1
    handle_httpstatus_list = [430, 404, 403]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    directory = get_project_settings().get("FILE_PATH")
    if not os.path.exists(directory):
        os.makedirs(directory)
    logs_path = os.path.join(directory,f"{today}_pdpaola.log")
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    start_urls = "https://www.pdpaola.com/",

    category_pages = (
        "https://www.pdpaola.com/collections/{category}?page={page}&1678818627494"
    )
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
        yield Request(
            self.delivery_api, callback=self.delivery_call, headers=self.headers
        )
        yield Request(
            self.base_url, callback=self.main_page, headers=self.headers, dont_filter=True
        )

    def get_target_urls(self, response, link, page_counter):
        collections_data = response.json()
        all_collections = collections_data.get('collections')
        for collection in collections_data.get('collections'):
            collection_title = collection['title']
            collection_handle = collection['handle']
            self.log(f"Processing collection: {collection_title} (Handle: {collection_handle})")
            products_url = f'https://www.pdpaola.com/collections/{collection_handle}'
            self.target_urls.append(products_url)
        if all_collections is not None and len(all_collections) > 0:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}&page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))
                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.get_target_urls(product_response, link, counter)


            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")
        else:
            print("No more products found. Stopping pagination.")
            self.logger.info("No more products found. Stopping pagination.")

    def delivery_call(self, response):
        try:
            self.delivery_data = json.loads(response.text)
        except:
            self.delivery_data = []

    @inline_requests
    def main_page(self, response):
        url = f'https://www.pdpaola.com/collections.json?limit=250'
        page = 1
        try:
            country_request = scrapy.Request(url, headers=self.headers, dont_filter=True)
            target_response = yield country_request
            if target_response.status == 200:
                self.get_target_urls(target_response, url, page)
            else:
                self.log(f"Received Response for URL: {target_response.status_code}")
        except Exception as e:
            self.log(f"Received all_target_urls Response: {e}")

        filtered_urls = list(set(self.target_urls))
        for link in filtered_urls:
            if link:
                try:
                    updated_link = f'{link}/products.json?limit=250'
                    page_counter = 1
                    req = scrapy.Request(updated_link, headers=rotate_headers(), dont_filter=True)
                    product_response = yield req
                    if product_response.status == 200:
                        self.parse(product_response, updated_link, page_counter)
                    else:
                        self.log(f"Received Response for URL: {product_response.status}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {updated_link}: {e}")

        logging.info(f'Total Sku of pdpaola : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            # product_badge = self.sku_mapping[sku_id].get('product_badge')
            url_update = self.sku_mapping[sku_id].get('product_url')
            url = urljoin(self.base_url, url_update)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': url_update, 'sku_id': sku_id}
            )

    def parse(self, response, link, page_counter):
        sku_id = ''
        products_data = json.loads(response.text)
        all_products = products_data.get('products')
        for product in products_data.get('products', []):
            product_handle = product['handle']
            variants = product.get('variants', [])
            if variants:
                variant = variants[0]
                sku_id = variant.get('sku')
            product_url = f'/products/{product_handle}'
            if "look" not in product_url and "grid" not in product_url:
                self.get_all_sku_mapping(product_url, sku_id)
            else:
                logging.info('looks url skipped: ' + product_url)

        if all_products is not None and len(all_products) > 30:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}&page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")

                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))

                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.parse(product_response, link, counter)

            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")
        else:
            print("No more products found. Stopping pagination.")
            self.logger.info("No more products found. Stopping pagination.")

    def get_all_sku_mapping(self, product_url, sku_id):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url}

    @inline_requests
    def parse_product(self, response, product_url, sku_id):
        content = {}
        if response.status in self.handle_httpstatus_list:
            yield Request(
                response.url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id},
            )
            return

        size_dimensions = self.get_size_dimensions(response)
        product_badge = ''
        product_color = []
        sku_colors = response.css('span.whole-color::attr(style)').getall()
        if sku_colors:
            try:
                sku_colors = list(set(sku_colors))
                for sku_color in sku_colors:
                    split_code = sku_color.split(':')[1]
                    color = self.find_color_name(split_code)
                    if color not in product_color and color is not None:
                        product_color.append(color)
            except Exception as e:
                print(e)
        colors = ','.join(product_color)
        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": f'{self.base_url}{product_url}',
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        languages = ["de", "es", "fr", "it"]
        for language in languages:
            logging.info(f'Processing: {language}')
            url = f'{self.base_url}/{language}{product_url}'
            req = scrapy.Request(url, headers=self.headers, dont_filter=True, meta={'dont_redirect': True })
            content_response = yield req
            if content_response.status == 200:
                content_info = self.collect_content_information(content_response)
                content[language] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            else:
                self.log(f"Unhandled status code {content_response.status} for URL: {content_response.url}")

        specification = {}
        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode').lower()
                currency_code = item.get('currencyCode')
                country_name = item.get('countryName')
                url = f'{self.base_url}{product_url}?lang=en&country={country_code}'
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    specification_info = self.collect_specification_info(resp, country_code, currency_code,
                                                                         country_name, url)
                    specification[country_code] = specification_info
                elif resp.status in [301, 302]:
                    specification_url = resp.urljoin(url)
                    req = scrapy.Request(specification_url, headers=self.headers, dont_filter=True)
                    specification_url_resp = yield req
                    if specification_url_resp.status == 200:
                        specification_info = self.collect_specification_info(specification_url_resp,
                                                                             country_code, currency_code,
                                                                             country_name, url)
                        specification[country_code] = specification_info

                elif resp.status == 404:
                    self.log(f"Received 404 response for URL: {resp.url}")

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return
        product_badge = response.css("a.collection-tweak.tweak__fine-jewelry.product-tweak::text").get()
        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        details = [
            detail.strip().replace(":", "")
            for detail in response.xpath('//div[@class="rte"]/ul//li//text()').extract()
            if detail.strip() != ""
        ]
        finish = self.get_detail_data("finishing", details)
        domain, domain_url = self.extract_domain_domain_url(response.url)

        list_img = []
        image_urls = response.css('.product-images > li > div > img.main-item-image')
        for img_tag in image_urls:
            src = img_tag.attrib.get('src')
            if src:
                if src not in list_img:
                    list_img.append(f'https:{src}')
            else:
                data_copy_srcset = img_tag.attrib.get('data-copy-srcset')
                if data_copy_srcset:
                    links = data_copy_srcset.split(',')
                    first_link = links[0].strip().split(' ')[0]
                    if first_link not in list_img:
                        list_img.append(f'https:{first_link}')

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku_id + "/"
                if not os.path.exists(directory):
                    os.makedirs(directory)
                for url_pic in list_img:
                    filename = str(uuid.uuid4()) + ".png"
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            req = scrapy.Request(url_pic, headers=self.headers, dont_filter=True)
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

        ele_material = response.css('div.product-description.f-12')
        main_material = ele_material.css('span.spec-class:contains("Material") + a u::text').get() or ""
        secondary_material = ele_material.css('span.spec-class:contains("Finishing") + a u::text').get() or ""
        collection_value = response.css('#collection::attr(collection-value)').get()

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_value
        item['brand'] = "PDPAOLA"
        item['product_badge'] = product_badge
        item['manufacturer'] = 'Pdpaola'
        item['sku'] = sku_id
        item['sku_color'] = colors
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def find_color_name(self, hex_code):
        color_match = {
            '#e4b972': "Gold",
            '#bfbfbf': 'Silver',
            '#2b3c95': 'Blue',
            '#91a382': 'Green',
            '#c6cc9b': 'Green-lily',
            '#477d58': 'Green-aventurine',
            '#ffffff': 'White-crystal'
        }

        return color_match.get(hex_code)

    def extract_price_info(self, price_string):
        match = re.search(r"([^\d]*)([\d.,]+)", price_string)
        if match:
            currency_symbol, numerical_value = match.groups()
            pattern = r'\,\d{3}(?![\d,])'
            match = re.search(pattern,  numerical_value)
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
            return None,

    def get_size_dimensions(self, response):
        dimensions_keywords = ["diameter", "width", "thickness", "measurement", "length", "weight"]
        size_dimensions_set = set()
        try:
            details = response.css("div.product-description ul li")
            for li_tag in details:
                text_content = " ".join(li_tag.css("::text").getall()).lower().strip()
                keyword_found = next((kw for kw in dimensions_keywords if kw in text_content), None)
                if keyword_found:
                    key = li_tag.css('span::text').get(default="").lower().strip()
                    dimension_info = text_content.split(":")[-1].strip()
                    size_dimensions_set.add(f'{key} {dimension_info}')
            return list(size_dimensions_set) if size_dimensions_set else []
        except Exception as e:
            self.log(f'size : {e}')

    def collect_content_information(self, resp):
        sku_title = resp.css('h1.product-title::text').get()
        short_description = resp.css(".product_seo_description>h2::text").get(default="").strip()
        product_description = resp.css("div.product-description *::text").getall()
        long_description = " ".join(set([text.strip() for text in product_description if text.strip()]))
        description = resp.css('.accordion-wrapper-display p::text').get() or ""
        sku_long_description = (short_description + "\n" + long_description + '\n' + description).strip()
        return {
            "sku_title": sku_title,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def get_detail_data(self, find_string, details):
        for itr, detail in enumerate(details):
            if find_string.lower() == detail.lower():
                return details[itr + 1]
        return ""

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
            logging.error(f"Error: {e}")
            return "No" "out-of-stock"

    def get_delivery_data_by_country(self, country):
        delivery_methods = [data for data in self.delivery_data if data.get("country") == country]
        if not delivery_methods:
            delivery_methods = [data for data in self.delivery_data if data.get("country") == "Spain"]

        if delivery_methods:
            best_us_method = min(delivery_methods, key=lambda x: x.get("EDD", float('inf')))
            # best_EDD = best_us_method.get("best_EDD")
            methods = best_us_method.get("methods")
            return methods

    def collect_specification_info(self, resp, country_code, currency_code, country_name, product_url):
        new_price = ''
        base_price = ''
        shipping_lead_time = ''
        shipping_expenses = ''
        shipping_lead_time_list = []
        shipping_expenses_list = []
        price_element = resp.css('div.product-price.product-item-price>span.money::text').get()
        if price_element:
            price = price_element.strip()
            base_price = self.extract_price_info(price)
        price_wrapper_div = resp.css('div.product-price')
        if price_wrapper_div:
            new_price_span = resp.css("span.new-price::text").get()
            if new_price_span:
                price = new_price_span.strip() if new_price_span else base_price
                new_price = self.extract_price_info(price)
            old_price_strike = resp.css("span.old-price::text").get()
            if old_price_strike:
                old_price = old_price_strike.strip() if old_price_strike else new_price
                base_price = self.extract_price_info(old_price)

        availability = resp.css('link[itemprop="availability"]::attr(href)').get(default="")
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        value_text = resp.css("span.value::text").get(default="").strip()
        next_text = resp.css("span.value + *::text").get(default="").strip()
        days_text = f"{value_text} {next_text}" if next_text else value_text
        free_from_text = " ".join(set(resp.css('div.rate span::text').getall())).strip()
        country_delivery_data = self.get_delivery_data_by_country(country_name)
        if country_delivery_data is not None:
            try:
                methods = country_delivery_data
                for method in methods:
                    sh_type = method.get("sh_type")
                    if sh_type:
                        sh_price_1 = method.get("sh_price", "")
                        sh_free = method.get("sh_free", "")
                        sh_time_min = method.get("sh_time_min", "")
                        sh_time_max = method.get("sh_time_max", "")

                        if "Standard Shipping" in sh_type:
                            shipping_lead_time_list.append(f"{sh_type} = {sh_time_min}-{sh_time_max} {days_text}")
                            shipping_expenses_list.append(f"{sh_type} = {sh_price_1}, {free_from_text}-{sh_free}")

                        elif "Express Shipping" in sh_type:
                            shipping_lead_time_list.append(f"{sh_type} = {sh_time_min}-{sh_time_max} {days_text}")
                            shipping_expenses_list.append(f"{sh_type} = {sh_price_1}, {free_from_text}-{sh_free}")
            except Exception as e:
                print("Exception in delivery", e)
        shipping_lead_time = "; ".join(shipping_lead_time_list)
        shipping_expenses = "; ".join(shipping_expenses_list)
        size_elements = resp.css('.custom-option:not(.disabled) button::text').getall()
        available_sizes = list(set(size.strip() for size in size_elements if size.strip()))

        return {
                    "lang": "en",
                    "domain_country_code": country_code,
                    "currency": currency_code,
                    "base_price": base_price if base_price else new_price,
                    "sales_price": new_price if new_price else base_price,
                    "active_price": new_price if new_price else base_price,
                    "stock_quantity": "",
                    "availability": availability_status,
                    "availability_message": out_of_stock_text,
                    "shipping_lead_time": shipping_lead_time,
                    "shipping_expenses": shipping_expenses,
                    "marketplace_retailer_name": "",
                    "condition": "NEW",
                    "reviews_rating_value": "",
                    "reviews_number": "",
                    "size_available": available_sizes,
                    "sku_link": product_url
                }

