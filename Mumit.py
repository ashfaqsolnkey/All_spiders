import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from scrapy.http import Request, TextResponse
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, asyncio, aiohttp
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


class Mumit(scrapy.Spider):
    name = "mumit"
    target_urls = []
    sku_mapping = {}
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    base_url = "https://mumit.com"
    handle_httpstatus_list = [430]
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
    start_urls = "https://mumit.com/en/"

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls,
            callback=self.main_page,
            headers=rotate_headers())

    def get_target_urls(self, response, link, page_counter):
        collections_data = response.json()
        all_collections = collections_data.get('collections')
        for collection in collections_data.get('collections'):
            collection_title = collection['title']
            collection_handle = collection['handle']
            self.log(f"Processing collection: {collection_title} (Handle: {collection_handle})")
            products_url = f'https://www.mumit.com/collections/{collection_handle}'
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

    @inline_requests
    def main_page(self, response):
        url = f'https://www.mumit.com/collections.json?limit=250'
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

        for sku_id, product_url in self.sku_mapping.items():
            first_url = ''
            material = self.sku_mapping[sku_id].get('material')
            if isinstance(self.sku_mapping[sku_id]['product_urls'], list) and len(self.sku_mapping[sku_id]['product_urls']) > 0:
                first_url = self.sku_mapping[sku_id]['product_urls'][0]
            url = urljoin(self.base_url, first_url)

            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'material': material, 'sku_id': sku_id}
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
            product_url = f'en/products/{product_handle}'
            material = ''
            self.get_all_sku_mapping(product_url, sku_id, material)

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

    def get_all_sku_mapping(self, product_url, sku_id, material_type):
        if sku_id not in self.sku_mapping:
            self.sku_mapping[sku_id] = {'product_urls': [product_url], 'material': material_type}
        else:
            if isinstance(self.sku_mapping[sku_id]['product_urls'], str):
                self.sku_mapping[sku_id]['product_urls'] = [self.sku_mapping[sku_id]['product_urls']]
            if product_url not in self.sku_mapping[sku_id]['product_urls']:
                self.sku_mapping[sku_id]['product_urls'].append(product_url)

    @inline_requests
    def parse_product(self, response, material, sku_id):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'material': material, 'sku_id': sku_id}
            )
            return

        content = {}
        specification = {}
        material = response.css('.product-item__title>span.product-item__subtitle > a::text').get()
        product_color = response.css('span.radio__legend__label::text').get()
        if product_color:
            product_color = product_color.strip()
        country_code = 'en'
        specification_info = self.collect_specification_info(response)
        specification['es'] = specification_info
        self.collect_content_information(response, country_code, content)

        link_url = response.css('link[rel="alternate"][hreflang="es-ES"]::attr(href)').get()
        req = Request(link_url, headers=self.headers, dont_filter=True)
        resp = yield req
        if resp.status == 404:
            self.log(f"Received 404 while collecting es content: {resp}")
        else:
            self.collect_content_information(resp, 'es', content)
        list_img = []
        list_imgs = response.css('.image-wrapper.image-wrapper--cover.lazy-image.lazy-image--backfill>img::attr(src)').getall()
        for url_pic in list_imgs:
            absolute_url = urljoin(self.base_url, url_pic)
            list_img.append(absolute_url)

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

        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        domain, domain_url = self.extract_domain_domain_url(response.url)

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = 'Mumit'
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = material
        item['image_url'] = product_images_info
        item['size_dimensions'] = []
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response, language_code, content):
        descriptions = response.css('p.richtext-full ::text').getall()
        short_description = ' '.join(descriptions).strip()
        descriptions = response.css('.metafield-rich_text_field>ul>li ::text').getall()
        full_description = ' '.join(map(str.strip, descriptions))
        sku_long_description = short_description + full_description
        sku_title = response.css('h1.product__title.heading-size-6>span::text').get().strip()
        content[language_code] = {
            "sku_link": response.url,
            "sku_title": sku_title,
            "sku_short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response):
        currency_code = ''
        base_price = ''
        availability = ''
        shipping_lead_time = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data:
                    price = json_data["offers"][0].get("price")
                    currency_code = json_data["offers"][0].get("priceCurrency")
                    availability = json_data["offers"][0].get("availability")
                    base_price = "{:.2f}".format(float(price))
            except Exception as e:
                print("Error in collect_specification_info:", e)
        sizes = [size.strip() for size in response.css('a.select-popout__option>span::text').getall()]
        shipping_expenses = ''
        shipping_text = response.css(
            '.block__icon__text.body-size-1>p::text').get()
        if shipping_text:
            shipping_expenses = shipping_text.strip()
        shipping_lead_time = response.css('.radio__button::attr(data-shipping-label)').get()

        if shipping_lead_time:
            shipping_lead_time = shipping_lead_time.strip()

        print(shipping_lead_time)

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
                "lang": "en",
                "domain_country_code": 'es',
                "currency": currency_code if currency_code else 'default_currency_code',
                "base_price": base_price if base_price else 0.0,
                "sales_price": base_price if base_price else 0.0,
                "active_price": base_price if base_price else 0.0,
                "stock_quantity": None,
                "availability": availability_status if availability_status else 'NA',
                "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
                "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
                "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,  # Use a default value, adjust as needed
                "marketplace_retailer_name": 'mumit',
                "condition": "NEW",
                "reviews_rating_value": 0.0,  # Use a default value, adjust as needed
                "reviews_number": 0,  # Use a default value, adjust as needed
                "size_available": sizes if sizes else [],
                "sku_link": response.url if response.url else 'NA',
            }

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
            logging.error(f"Error processing image: {e}")
