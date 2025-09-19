import asyncio
import aiohttp
import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from scrapy.http import Request, TextResponse
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, html
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


async def get_page(session, url, proxy_cycle,headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=headers) as response:
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
        task = asyncio.create_task(get_page(session, url, proxy_cycle, headers))
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
            time.sleep(5)
            continue
        except aiohttp.client.ClientConnectionError:
            error_msg = 'ClientConnectionError'
            print(error_msg)
            time.sleep(5)
            continue

class Cartier(scrapy.Spider):
    name = "cartier"
    all_target_urls = []
    sku_mapping = {}
    spec_mapping = '[{"countryCode": "es", "url_countryCode": "es-es"}, {"countryCode": "gb", "url_countryCode": "en-gb"},{"countryCode": "be", "url_countryCode": "en-be"},{"countryCode": "gr", "url_countryCode": "en-gr"},{"countryCode": "ie", "url_countryCode": "en-ie"},{"countryCode": "nl", "url_countryCode": "en-nl"},{"countryCode": "at", "url_countryCode": "en-at"},{"countryCode": "pl", "url_countryCode": "en-pl"},{"countryCode": "ch", "url_countryCode": "en-ch"},{"countryCode": "se", "url_countryCode": "en-se"},{"countryCode": "pt", "url_countryCode": "en-pt"},{"countryCode": "dk", "url_countryCode": "en-dk"},{"countryCode": "fr", "url_countryCode": "en-fr"},{"countryCode": "it", "url_countryCode": "en-it"}]'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://www.cartier.com/"
    handle_httpstatus_list = [430, 403, 301, 302, 307]
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
        'accept': '*/*',
        'accept-language': 'en-GB,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://www.cartier.com/en-es/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'x-dtpc': '17$111435199_542h5vDOVPRNOCMCRFPEIPVVANANNWDRGUTSWF-0e0',
        'x-requested-with': 'XMLHttpRequest'
    }
    start_urls = "https://www.cartier.com/en-es/"

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
            headers=self.headers)

    def get_target_urls(self, response, base_url):
        category_urls = response.css('.left.menuItem.swiper-slide>a::attr(href)').getall()
        for link in category_urls:
            absolute_url = urljoin(base_url, link)
            if "/faq/shipping-delivery" not in absolute_url and "/faq/exchanges-returns" not in absolute_url and "/contact-us" not in absolute_url and "faq/orders-payment" not in absolute_url and "/set-for-you" not in absolute_url and "maison/savoir-faire" not in absolute_url and "maison/the-story/" not in absolute_url:
                self.all_target_urls.append(absolute_url)

    @inline_requests
    def main_page(self, response):
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            try:
                country_code = item.get('countryCode').lower()
                url = f'https://www.cartier.com/Navigation/CustomizableSubMenuAsync?device=desktop&siteCode=CARTIER_{country_code.upper()}&langId=4'
                country_req = Request(url, headers=self.headers, dont_filter=True)
                country_response = yield country_req
                self.get_target_urls(country_response, url)
            except Exception as e:
                logging.error(f"Error scraping URL: {url}. Error: {e}")
        split_target_urls = []

        target_urls_list = list(set(self.all_target_urls))
        for target in target_urls_list:
            split_url = target.split("/")
            url_without_lang = "/".join(split_url[4:])
            split_target_urls.append(url_without_lang)

        filter_urls_list = list(set(split_target_urls))
        for link in filter_urls_list:
            if link:
                try:
                    url = response.urljoin(link)
                    req = Request(url, headers=self.headers, dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        self.parse(resp)
                    else:
                        self.log(f"Received Response for URL: {resp.status_code}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {link}: {e}")

        logging.info(f'Total Sku of cartier : {len(self.sku_mapping)}')
        for sku_id, product_info in self.sku_mapping.items():
            product_badge = product_info.get('badge')
            product_url = product_info.get('product_url')
            material_type = product_info.get('material_type')
            collections = product_info.get('collections')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'material': material_type, 'product_badge': product_badge,'sku_id': sku_id,'collections': collections}
            )

    def parse(self, response):
        product_url = response.css('a.image-link::attr(href)').get()
        if not product_url:
            button_links = response.css('div.shelf-element__btn>a::attr(href)').getall()
            for url in button_links:
                try:
                    loop = asyncio.get_event_loop()
                    results = loop.run_until_complete(main([url], self.proxy_cycle, self.headers))
                    for result in results:
                        if result:
                            next_response = TextResponse(url=url, body=result, encoding='utf-8')
                            self.product_parser(next_response)
                            next_page = next_response.css('div.loadMoreProductsButton>a::attr(href)').get()
                            if next_page:
                                url = response.urljoin(next_page)  # Update the URL for the next iteration
                            else:
                                break  # No next page, exit the loop
                        else:
                            self.log(f"Error fetching URL: {url}")
                        break
                except Exception as e:
                    self.log(f"Error occurred while processing product url {url}: {e}")

        else:
            self.product_parser(response)
            next_page = response.css('div.loadMoreProductsButton>a::attr(href)').get()
            try:
                if next_page:
                    next_page_link = response.urljoin(next_page)
                    loop = asyncio.get_event_loop()
                    results = loop.run_until_complete(main([next_page_link], self.proxy_cycle, self.headers))
                    for result in results:
                        if result:
                            next_response = TextResponse(url=next_page_link, body=result, encoding='utf-8')
                            self.parse(next_response)
                        else:
                            break

            except Exception as e:
                self.log(f"Pagingation {e}")

    def product_parser(self, response):
        material_str = ''
        badge = ''
        sku_id = ''
        collections = response.css('h2.slot-element__title.heading-1::attr(data-tracking-label)').get()
        product_elements = response.css('li.search__product-item')
        for product_element in product_elements:
            product_url = product_element.css('a.image-link::attr(href)').get()
            material = product_element.css('div.product-slot__short-description::text').get()
            if material:
                material_str = material.strip()
            badge_elements = product_element.css(
                'product-slot.product-slot.slot-element.js-carousel-item::attr(data-badges)').get()
            if badge_elements:
                try:
                    badge_jsons = json.loads(badge_elements)
                    for badge_json in badge_jsons:
                        badge = badge_json.get('Label')
                        break
                except Exception as e:
                    print(e)
            sku = product_element.css('product-slot.product-slot.slot-element.js-carousel-item::attr(data-refnumber)').get()
            if sku.strip() != '':
                sku_id = sku
            self.get_all_sku_mapping(product_url, sku_id, material_str, badge, collections)

    def get_all_sku_mapping(self, product_url, sku_id, material_type, badge, collections):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge, 'material_type': material_type,'collections':collections}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge,'material_type': material_type,'collections':collections}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge, 'material_type': material_type,'collections':collections}

    @inline_requests
    def parse_product(self, response, material, product_badge, sku_id, collections):
        url_parts = response.url.split("/")
        url_without_language = "/".join(url_parts[4:])

        content = {}
        specification = {}
        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        languages = ["es-es", "it-it", "fr-fr", "pt-pt", "nl-nl"]
        for language in languages:
            logging.info(f'Processing: {language}')
            url = f'https://www.cartier.com/{language}/{url_without_language}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=self.headers, dont_filter=True)
                redirected_response = yield req
                content_info = self.collect_content_information(redirected_response)
                content[language.split("-")[0]] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            else:
                content_info = self.collect_content_information(resp)
                content[language.split("-")[0]] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode')
            url_countryCode = item.get('url_countryCode')
            url = f'{self.base_url}{url_countryCode}/{url_without_language}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=self.headers, dont_filter=True)
                redirected_response = yield req
                specification_info = self.collect_specification_info(redirected_response, country_code)
                specification[country_code.lower()] = specification_info

            else:
                specification_info = self.collect_specification_info(resp, country_code)
                specification[country_code.lower()] = specification_info

        list_img = response.css('li.image-wrapper>img.lazy.lazy::attr(data-src)').getall()
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
                    img_url = url_pic.replace('w260', 'w1242')
                    while trial_image < 10:
                        try:
                            req = Request(img_url, headers=self.headers, dont_filter=True)
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

                    filename = str(uuid.uuid4()) + ".png"
                    if not os.path.exists(directory):
                        os.makedirs(directory)

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

        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        domain, domain_url = self.extract_domain_domain_url(response.url)

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = 'cartier'
        item['product_badge'] = product_badge
        item['manufacturer'] = self.name
        item['collection_name'] = collections
        item['sku'] = sku_id
        item['sku_color'] = ''
        item['main_material'] = material
        item['image_url'] = product_images_info
        item['size_dimensions'] = []
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        sku_title = ''
        long_description = ''
        short_description = response.css('.description-wrapper>p>.value::text').get()
        title = response.css('h1.item-info__name.heading-1::text').get()
        if title:
            sku_title = title.strip()
        description = response.css('p.item-info__disclaimer-alert::text').get()
        if description:
            long_description = description.strip()
        sku_long_description = short_description + long_description
        return {
            "sku_title": sku_title,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, country_code):
        currency_code = ''
        out_of_stock_text = ''
        product_quantity = ''
        availability_status = ''
        shipping_standard_lead_time = ''
        shipping_express_lead_time = ''
        price_json = response.css('.item-info__price>.product-price::attr(data-model)').get()
        json_price = json.loads(price_json)
        currency_code = json_price['priceCurrency'].get('label')
        price = json_price.get('fullPrice')
        base_price = str(price)
        sizes = [s.strip() for s in response.css('option.is-lastItem::text').getall()]
        shipping_response = self.get_shipping(response)
        if shipping_response.status == 200:
            try:
                shipping_info_container = shipping_response.css('div.html-block__body.cms-generic-copy.font-family--serif')
                paragraphs = shipping_info_container.css('p::text').getall()
                if paragraphs:
                    shipping_text = paragraphs[2]
                    if shipping_text:
                        shipping_standard_lead_time = 'Standard Delivery:' + shipping_text
                    shipping_expenses_text = paragraphs[4]
                    if shipping_expenses_text:
                        shipping_express_lead_time = 'Express Delivery :' + shipping_expenses_text
            except Exception as e:
                print(e)

        shipping_expenses = shipping_standard_lead_time + shipping_express_lead_time
        json_encoded_str = response.css('add-to-bag.add-to-bag::attr(data-main-product-trackdata)').get()
        try:
            decoded_str = html.unescape(json_encoded_str)
            stock_json = json.loads(decoded_str)
            product_is_in_stock = stock_json.get('product_is_in_stock')
            product_quantity = stock_json.get('product_quantity')
            product_availability = self.check_product_availability(product_is_in_stock)
            availability_status = product_availability[0]
            out_of_stock_text = product_availability[1]
        except Exception as e:
            print(e)

        return {
                "lang": "en",
                "domain_country_code": country_code,
                "currency": currency_code if currency_code else 'default_currency_code',
                "base_price": base_price if base_price else 0.0,
                "sales_price": base_price if base_price else 0.0,
                "active_price": base_price if base_price else 0.0,
                "stock_quantity": product_quantity,
                "availability": availability_status if availability_status else 'NA',
                "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
                "shipping_lead_time": shipping_expenses if shipping_expenses else 'NA',
                "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,  # Use a default value, adjust as needed
                "marketplace_retailer_name": 'cartier',
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
            if availability:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "NOT AVAILABLE IN STORES"
                return "No", out_of_stock_text
        except Exception as e:
            return e

    def get_shipping(self, response):
        next_response = ''
        shipping_api = f'https://www.cartier.com/en-us/global-shipping-information-modal.html'
        try:
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(main([shipping_api], self.proxy_cycle, self.headers))
            for result in results:
                if result:
                    next_response = TextResponse(url=shipping_api, body=result, encoding='utf-8')
        except Exception as e:
            self.log(f"Error next_page: {e}")
        return next_response

