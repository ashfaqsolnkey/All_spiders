import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from itertools import cycle
import aiohttp
import asyncio
from scrapy.http import Request, TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

async def get_page(session, url, proxy_cycle, brandy_headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=brandy_headers) as response:

                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1
    return None


async def get_all(session, urls, proxy_cycle, brandy_headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle, brandy_headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, brandy_headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=brandy_headers, timeout=timeout) as session:
                data = await get_all(session, urls, proxy_cycle, brandy_headers)
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

class Brandymelville(scrapy.Spider):
    name = "brandymelville"
    all_target_urls = []
    sku_mapping = {}
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://us.brandymelville.com/"
    handle_httpstatus_list = [430, 403, 404, 302, 301]
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
    brandy_headers = headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
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
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }

    spec_mapping = '[ {"countryName": "united states", "url_countryCode": "us"},{"countryName": "australia", "url_countryCode": "au"}, {"countryName": "europe", "url_countryCode": "eu"},{"countryName": "japan", "url_countryCode": "jp"},{"countryCode": "united kingdom", "url_countryCode": "uk"}]'
    start_urls = "https://us.brandymelville.com/"

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

    @inline_requests
    def main_page(self, response):
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            try:
                url_countryCode = item.get('url_countryCode')
                url = f'https://{url_countryCode}.brandymelville.com'
                req = yield scrapy.Request(url, headers=self.headers, dont_filter=True)
                if req.status == 200:
                    self.get_target_urls(req)
                else:
                    self.log(f"Error response code {req.status} for url in main_page : {url}")
            except Exception as e:
                logging.error(f"Error scraping in main_page : {e}")

        for link in self.all_target_urls:
            if link:
                try:
                    req = scrapy.Request(link, headers=rotate_headers(), dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        self.parse(resp, link)
                    else:
                        self.log(f"Received Response for URL: {resp.status}")
                except Exception as e:
                    logging.error(f"Error scraping in link : {e}")

        logging.info(f'Total Sku of brandymelville : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url, "sku_id": sku_id}
            )

    def get_target_urls(self, response):
        heading_urls = response.css('ul.list-menu>li>a::attr(href)').extract()
        targeturls = response.css('ul>li>ul.main-navigation-childlinks-list>li>a::attr(href)').extract()
        nested_targeturls = response.css('ul.main-navigation-childlinks-list>li>ul>li>a::attr(href)').extract()
        target_urls = heading_urls + targeturls + nested_targeturls
        for link in target_urls:
            if link not in self.all_target_urls:
                url = response.urljoin(link)
                self.all_target_urls.append(url)

    def parse(self, response, base_url):
        script_tag = response.css('#web-pixels-manager-setup').get()
        if script_tag:
            S_data = script_tag.split('"collection_viewed",')[1]
            data = S_data.split(');},')[0]
            json_data = json.loads(data)
            if json_data:
                try:
                    products = json_data['collection']['productVariants']
                    for product in products:
                        product_url = product['product']['url']
                        sku_id = product['sku']
                        self.get_all_sku_mapping(product_url, sku_id)
                except Exception as e:
                    print(f'Error while extracting Sku and url : {e}')

            next_page = response.css('link[rel="next"]::attr(href)').get()
            if next_page:
                try:
                    loop = asyncio.get_event_loop()
                    next_page_url = urljoin(base_url, next_page)
                    results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.brandy_headers))
                    for result in results:
                        if result:
                            next_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                            self.parse(next_response, next_page_url)
                except Exception as e:
                    self.log(e)

    def get_all_sku_mapping(self, product_url, sku_id):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = product_url
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url

    @inline_requests
    def parse_product(self, response, product_url, sku_id):
        if response.status == 200:
            content = {}
            specification = {}
            description = ''
            main_material = ''
            url_without_lang = ''
            secondary_material = ''
            color = response.css('div.color-option.color-option--visible::attr(data-value)').get()
            if product_url:
                url_without_lang = product_url
            collection_value = ''
            try:
                content_info = self.collect_content_information(response)
                content["en"] = {
                    "sku_link": response.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            except Exception as e:
                self.log(f"Exception occured at content {e}")

            script_content = response.css('script[type="application/ld+json"]::text').getall()
            for script in script_content:
                try:
                    if script:
                        json_data = json.loads(script)
                        if "description" in json_data:
                            description = json_data['description']
                            break
                except json.JSONDecodeError:
                    self.log('Error decoding JSON data in Parse product for description ')
            size_dimensions = []
            if description:
                try:
                    split_description = re.split(r'[.\n]|(?<=[a-z])(?=[A-Z])', description)
                    for item in split_description:
                        mat_delimiter = "Materials:" if "Materials:" in item else "Fabrics:"
                        if mat_delimiter in item:
                            mats = item.replace(mat_delimiter, '').strip()
                            if "Measurements" in mats:
                                parts = mats.split("Measurements:")
                                main_material = parts[0].strip()
                                measurement_part = parts[1].strip()
                                size_dimensions.append("Measurements: " + measurement_part)
                            else:
                                main_material = mats
                        elif "Measurement" in item or "Measurements" in item:
                            measure = item.replace('Measurement:', '')
                            measurement = measure.split('Made')[0]
                            sizes = measurement.split(',')
                            for size in sizes:
                                size_dimensions.append(size.strip())
                except Exception as e:
                    print(e)
            try:
                json_data = json.loads(self.spec_mapping)
                for item in json_data:
                    url_countryCode = item.get('url_countryCode')
                    url = f'https://{url_countryCode}.brandymelville.com{url_without_lang}'
                    country_req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                    country_resp = yield country_req
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, url_countryCode)
                        specification[url_countryCode] = specification_info
                    elif country_resp.status in [301, 302]:
                        try:
                            redirected_url = country_resp.headers.get(b'Location').decode('utf-8')
                            url = response.urljoin(redirected_url)
                            req = Request(url, headers=self.headers, dont_filter=True)
                            resp = yield req
                            if resp.status == 200:
                                specification_info = self.collect_specification_info(resp, url_countryCode)
                                specification[url_countryCode] = specification_info
                        except Exception as e:
                            logging.error(f"Error scraping URL: {url}. Error: {e}")

                    else:
                        self.log(f"Received {country_resp.status} for: {country_resp}")

            except Exception as e:
                print(e)
                return

            list_img = []
            images_data = []
            img_data = response.css('ul.product-gallery__nav li')
            if img_data:
                for list_data in img_data:
                    data_media_alt = list_data.css('::attr(data-media-alt)').get()
                    if color in data_media_alt:
                        image_data = list_data.css('img::attr(src)').get()
                        images_data.append(image_data)
                    elif color is None:
                        image_data = list_data.css('img::attr(src)').get()
                        images_data.append(image_data)
            if images_data:
                for img in images_data:
                    if img:
                        img = img.strip()
                    image_parts = img.split('//')
                    image = image_parts[-1]
                    f_image = image.split(' ')[0]
                    list_img.append(f'https://{f_image}')
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
                                req = scrapy.Request(url_pic, headers=rotate_headers(), dont_filter=True)
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
                            image_info = os.path.join(directory, filename)
                            product_images_info.append(image_info)

                        except Exception as e:
                            logging.error(f"Error processing image: {e}")

            time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            domain, domain_url = self.extract_domain_domain_url(response.url)

            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['brand'] = 'brandymelville'
            item['product_badge'] = ''
            item['collection_name'] = collection_value
            item['manufacturer'] = self.name
            item['sku'] = sku_id
            item['sku_color'] = color
            item['main_material'] = main_material
            item['secondary_material'] = ''
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimensions
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response):
        sku_title = ''
        sku_long_description = ''
        sku_short_description = ''
        description = ''
        script_content = response.css('script[type="application/ld+json"]::text').getall()
        for script in script_content:
            try:
                if script:
                    json_data = json.loads(script)
                    if "description" in json_data:
                        sku_title = json_data['name']
                        describe = json_data['description']
                        if describe:
                            description = describe.strip()
                        break
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON data : {e} ')
        if "Fabrics" in description:
            sku_short_description = description.split('Fabrics')[0].strip()
        else:
            sku_short_description = description.strip()
        if description:
            sku_long_description = description.strip()
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description.replace('\n', '')
        }

    def collect_specification_info(self, response, country_code):
        currency_code = ''
        sale_price = ''
        availability = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        base_price = ''
        size_available = []
        size_set = set()
        script_content = response.css('script[type="application/ld+json"]::text').extract()
        for script in script_content:
            try:
                if script:
                    json_string = script.replace(' ', '')
                    json_string = json_string.replace('\n', '').replace(':\n', ':')
                    json_string = re.sub(r'(\w+):\s*\n\s*(true|false)', r'\1:\2', json_string)
                    json_string = re.sub(r',\s*\n\s*}', r'},', json_string)
                    json_string = script.replace('\n', '').replace("     ", '')
                    json_string = json_string.strip()
                    if json_string.startswith('{'):
                        json_string = json_string
                    else:
                        json_string = "{" + json_string

                    json_data = json.loads(json_string)

                    if "offers" in json_data:
                        sale_price = json_data['offers'][0]["price"]
                        currency_code = json_data['offers'][0]["priceCurrency"]
                        availability = json_data['offers'][0]["availability"]

                    elif "variants" in json_data:
                        variants = json_data['variants']
                        for variant in variants:
                            if variant['available']:
                                title = variant['title']
                                size = title.split('/ ')
                                if len(size) > 1:
                                    size = ''.join(size[1:])
                                    if size not in size_set:
                                        size_set.add(size)
                                        size_available.append(size)
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON data : {e}')

        if sale_price:
            sale_price = self.extract_price_info(str(sale_price))

        if not base_price:
            base_price = sale_price
        else:
            base_price = base_price

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": sale_price if sale_price else 0.0,
            "active_price": sale_price if sale_price else 0.0,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            "marketplace_retailer_name": 'brandymelville',
            "condition": "NEW",
            "reviews_rating_value": 0.0,
            "reviews_number": 0,
            "size_available": size_available if size_available else [],
            "sku_link": response.url if response.url else 'NA',
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
            return None,

    def check_product_availability(self, availability):
        try:
            if availability:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "NOT AVAILABLE IN STORES"
                return "No", out_of_stock_text
        except Exception as e:
            return "No" "NOT AVAILABLE IN STORES"
