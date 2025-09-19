from itertools import cycle
from urllib.parse import urlparse
import scrapy
from inline_requests import inline_requests
from scrapy import Request
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
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
            async with session.get(url, proxy=f"http://{proxy}", headers=headers, timeout=320) as response:
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
            timeout = aiohttp.ClientTimeout(total=160)
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


class ShopifySpider(scrapy.Spider):
    name = "Shopify"
    sku_mapping = {}
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    handle_httpstatus_list = [430, 403, 443, 404]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    directory = get_project_settings().get("FILE_PATH")

    if not os.path.exists(directory):
        os.makedirs(directory)

    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    start_urls = "https://scalperscompany.com/"

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
            dont_filter=True
        )

    @inline_requests
    def country_base_url(self, response):
        collection_url = f'{self.start_urls}collections.json?limit=250'
        page = 1
        try:
            country_request = scrapy.Request(collection_url, headers=headers, dont_filter=True)
            target_response = yield country_request
            if target_response.status == 200:
                self.get_target_urls(target_response, collection_url, page)
            else:
                self.log(f"Received Response for URL: {target_response.status_code}")
        except Exception as e:
            self.log(f"Received all_target_urls Response: {e}")

        filter_target_urls = set(self.all_target_urls)
        for link in filter_target_urls:
            if link:
                try:
                    page_counter = 1
                    req = scrapy.Request(link, headers=headers, dont_filter=True)
                    product_response = yield req
                    if product_response.status == 200:
                        self.parse(product_response, link, page_counter)
                    else:
                        self.log(f"Received Response for URL: {product_response.status}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {link}: {e}")

        print("all sku in Shopify:",self.sku_mapping)
        for sku_id, product_info in self.sku_mapping.items():
            product_url = product_info.get('product_url')
            size_list = product_info.get('size_list')
            available = product_info.get('available')
            gender = product_info.get('gender')
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id, "gender": gender, "size_list": size_list, "available":available}
            )

    def get_target_urls(self, response, link, page_counter):
        collections_data = response.json()
        all_collections = collections_data.get('collections')
        for collection in all_collections:
            collection_title = collection['title']
            collection_handle = collection['handle']
            products_count = collection['products_count']
            if "scalperscompany.com" in link and products_count > 40:
                self.log(f"Processing collection: {collection_title} (Handle: {collection_handle})")
                products_url = f'{self.start_urls}collections/{collection_handle}/products.json?limit=250'
                self.all_target_urls.append(products_url)
            elif products_count > 7 and "scalperscompany.com" not in link:
                self.log(f"Processing collection: {collection_title} (Handle: {collection_handle})")
                products_url = f'{self.start_urls}collections/{collection_handle}/products.json?limit=250'
                self.all_target_urls.append(products_url)

        if all_collections is not None and len(all_collections) > 0:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}&page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, headers))
                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.get_target_urls(product_response, link, counter)
            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")
        else:
            print("No more products found. Stopping pagination.")
            self.logger.info("No more products found. Stopping pagination.")

    def parse(self, response, link, page_counter):
        products_data = json.loads(response.text)
        all_products = products_data.get('products')
        for product in products_data.get('products', []):
            sku_id = ''
            size_list = []
            product_handle = product['handle']
            variants = product.get('variants')
            tags = product.get("tags")
            if any("m_" in tag.lower() for tag in tags) and any("w_" in tag.lower() for tag in tags):
                gender = "unisex"
            elif any("hombre" in tag.lower() for tag in tags) and any("mujer" in tag.lower() for tag in tags):
                gender = "unisex"
            elif any("m_" in tag.lower() for tag in tags):
                gender = "men"
            elif any("hombre" in tag.lower() for tag in tags):
                gender = "men"
            elif any("w_" in tag.lower() for tag in tags):
                gender = "women"
            elif any("mujer" in tag.lower() for tag in tags):
                gender = "women"
            elif any("girls" in tag.lower() for tag in tags):
                gender = "girls"
            else:
                gender = ""
            gender = gender
            size_position = None
            options = product.get('options')
            size_key = ''
            size_keywords = ['Size', 'Tamaño', 'Tallas', 'Talla', 'SIZE']
            for index, option in enumerate(options, start=1):
                if option["name"] in size_keywords:
                    size_position = index
                    break
            if size_position:
                size_key = f"option{size_position}"
                for variant in variants:
                    Isavailable = variant['available']
                    if Isavailable:
                        size = variant.get(size_key)
                        size_list.append(size)
            if variants:
                sku_str = variants[0].get('sku')
                if sku_str:
                    if size_key and "-" in sku_str:
                        sku_id = sku_str.rsplit("-", 1)[0]
                    elif len(size_list) > 0 and "-" in sku_str:
                        sku_id = sku_str.rsplit("-", 1)[0]
                    else:
                        sku_id = sku_str

            product_available = any(variant['available'] for variant in variants)
            product_url = f'{self.start_urls}products/{product_handle}/products.json'
            self.get_all_sku_mapping(product_url, sku_id, gender, size_list, product_available)

        if all_products is not None and len(all_products) > 35:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}&page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, headers))
                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.parse(product_response, link, counter)
            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")
        else:
            print("No more products found. Stopping pagination.")
            self.logger.info("No more products found. Stopping pagination.")

    def get_all_sku_mapping(self, product_url, sku_id, gender, size_list, available):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, "gender": gender, "size_list": size_list, "available":available}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, "gender": gender, "size_list": size_list,"available":available}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, "gender": gender, "size_list": size_list, "available":available}

    @inline_requests
    def parse_product(self, response, product_url, sku_id, gender, size_list, available):
        colors = ''
        content = {}
        added_languages = set()
        brand = ''
        pro_url = product_url.split('/products.json')[0]
        req = scrapy.Request(pro_url, headers=headers, dont_filter=True)
        pro_response = yield req
        if pro_response.status == 200:
            script_tag_content = pro_response.css('script[type="application/ld+json"]::text').getall()
            for script_tag in script_tag_content:
                try:
                    json_data = json.loads(script_tag)
                    if "brand" in json_data:
                        brand = json_data["brand"].get("name")
                        break
                except Exception as e:
                    print("Exception in parse_product :", e)
            try:
                lang_links = pro_response.css('link[rel="alternate"]::attr(hreflang)').getall()
                if lang_links:
                    valid_hreflangs = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ca']
                    for hreflang in lang_links:
                        if any(hreflang.startswith(lang) for lang in valid_hreflangs):
                            href = pro_response.css(f'link[hreflang="{hreflang}"]::attr(href)').get()
                            base_lang = hreflang.split('-')[0]
                            if base_lang not in added_languages:
                                added_languages.add(base_lang)
                                language_url = f"{href}/products.json"
                                req = scrapy.Request(language_url, headers=headers, dont_filter=True)
                                content_response = yield req
                                if content_response.status == 200:
                                    content_info = self.collect_content_information(content_response)
                                    content[base_lang] = {
                                        "sku_link": href,
                                        "sku_title": content_info["sku_title"],
                                        "sku_short_description": content_info["short_description"],
                                        "sku_long_description": content_info["sku_long_description"]
                                    }
                else:
                    lang = pro_response.css("html::attr(lang)").get()
                    content_info = self.collect_content_information(response)
                    content[lang] = {
                        "sku_link": pro_url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            except Exception as e:
                print("Exception in lang", e)
        collection_name = ''
        if response.status == 200:
            product_data = response.json()
            product = product_data.get('product', {})
            collection_name = product.get("template_suffix")
            description = product.get('body_html', '')
            size_dimensions = []
            main_material = ''
            pattern = r"Modelo:\s*(.*?)(?:\s*Size:\s*(.*?))?(?:\s*Composición:\s*(.*?))?(?:<p><strong>Medidas modelo</strong>.*?<ul>(.*?)</ul>)?.*?La modelo lleva la talla\s*(\w+)"
            match = re.search(pattern, description)
            if match:
                modelo_value = match.group(1) if match.group(1) else ""
                size_dimensions.append(modelo_value)
                size_value = match.group(2) if match.group(2) else ""
                size_dimensions.append(size_value)
                composicion_value = match.group(3) if match.group(3) else ""
                size_dimensions.append(composicion_value)
                medidas_modelo_value = match.group(4) if match.group(4) else ""
                size_dimensions.append(medidas_modelo_value)
            material_match = re.search(r"Material:\s*(.*)", description)
            if material_match:
                raw_material = material_match.group(1)
                cleaned_material = re.sub(r'<[^>]+>', '', raw_material)
                main_material = cleaned_material.replace('\xa0', ' ')
            for color_option in product['options']:
                if color_option.get('name') in ['Color', 'Finishing', 'Colour', 'COLOUR']:
                    colors = color_option.get('values', [])[0]

            variants = product.get('variants', [])
            if variants:
                variant = variants[0]
                barcode = variant.get('barcode')
            else:
                barcode = "N/A"
            specification = {}
            try:
                spec_mapping = '[{"countryCode": "DE", "countryName": "Albania"},{"countryCode": "IT", "countryName": "Italy"},{"countryCode": "ES", "countryName": "Spain"},{"countryCode": "US", "countryName": "United States"},{"countryCode": "PT", "countryName": "Portugal"},{"countryCode": "GB", "countryName": "United Kingdom"},{"countryCode": "FR", "countryName": "France"},{"countryCode" :"AU"},{"countryCode" :"HK"},{"countryCode" :"CN"}]'
                json_data = json.loads(spec_mapping)
                for item in json_data:
                    country_code = item.get('countryCode').lower()
                    url = f'{product_url}?country={country_code}'
                    req = scrapy.Request(url, headers=headers,  dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        specification_info = self.collect_specification_info(resp, country_code, size_list, available)
                        specification[country_code] = specification_info
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')

            list_img = []
            for image in product['images']:
                list_img.append(image.get('src', ''))

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
                                req = Request(url_pic, headers=headers, dont_filter=True)
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

            time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            domain, domain_url = self.extract_domain_domain_url(response.url)
            if brand:
                brand_name = brand.strip()
            else:
                brand_name = domain

            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['brand'] = brand_name
            item['gtin13'] = barcode
            item['manufacturer'] = domain
            item['product_badge'] = ''
            item['collection_name'] = collection_name
            item['gender'] = gender
            item['sku'] = sku_id
            item['sku_color'] = colors
            item['main_material'] = main_material
            item['secondary_material'] = ''
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimensions
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response):
        sku_url = response.url.split('/products.json')[0]
        product_data = response.json()
        product = product_data.get('product', {})
        sku_title = product.get('title', '')
        sku_long_description_text = product.get('body_html', '')
        sku_long_description_text = re.sub(r'<[^>]+>', '', sku_long_description_text)
        sku_long_description = re.sub(r'\s+', ' ', sku_long_description_text).strip()

        return {
            "sku_title": sku_title,
            "sku_link": sku_url,
            "short_description": sku_long_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, country_code, size_list, availability):
        sale_price = ''
        base_price = ''
        priceCurrency = ''
        domain_url = response.url.split('/products.json')[0]
        country_url = response.url.split('/products.json')[1]
        final_url = f'{domain_url}{country_url}'
        product_data = response.json()
        product = product_data.get('product', {})
        variants = product.get('variants', [])
        if variants:
            variant = variants[0]
            sale_price = variant.get('price')
            base_price = variant.get('compare_at_price')
            if not base_price or base_price in ['0.00', '']:
                base_price = sale_price
            priceCurrency = variant.get('price_currency')
        else:
            barcode = "N/A"

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": 'en',
            "domain_country_code": country_code,
            "currency": priceCurrency if priceCurrency else 'default_currency_code',
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "NA",
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": '',
            "shipping_expenses": '',
            "condition": "NEW",
            "reviews_rating_value": 'NA',  # Use a default value, adjust as needed
            "reviews_number": 'NA',  # Use a default value, adjust as needed
            "size_available": size_list if size_list else [],
            "sku_link": final_url,
        }

    def check_product_availability(self, availability):
        try:
            availability_value = availability
            if availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Product Out of Stock"
                return "No", out_of_stock_text
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return

    def check_product_availability(self, availability):
        try:
            if availability:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Product Out of Stock"
                return "No", out_of_stock_text
        except Exception as e:
            self.log(f'Error: {e}')
            return "No", "Product Out of Stock"
