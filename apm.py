from typing import Any
import scrapy
from urllib.parse import urlencode, urljoin
from inline_requests import inline_requests
from scrapy import Request
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
import aiohttp
import asyncio
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

async def get_page(session, url, proxy_cycle, apm_headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=apm_headers) as response:

                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1

    return None

async def get_all(session, urls,proxy_cycle, apm_headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle,apm_headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results

async def main(urls, proxy_cycle, apm_headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=apm_headers,timeout=timeout) as session:
                data = await get_all(session, urls,proxy_cycle,apm_headers)
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

class ApmSpider(scrapy.Spider):
    name = "apm"
    sku_mapping = {}
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    spec_mapping = '[{"countryName" : "United States" , "countryCode" :"US" , "currencyCode":"USD" ,"codeUrl": "/", "shipping_charge":"115"}, {"countryName" : "Spain" , "countryCode" :"es" , "currencyCode":"EUR" ,"codeUrl": "/","shipping_charge":"95"}, {"countryName" : "Australia" , "countryCode" :"AU" , "currencyCode":"AUD" ,"codeUrl": "/" ,"shipping_charge" :"142"},{"countryName" : "Canada" , "countryCode" :"CA" , "currencyCode":"CAD" ,"codeUrl": "/","shipping_charge":"142"}, {"countryName" : "Switzerland" , "countryCode" :"CH" , "currencyCode":"CHF" ,"codeUrl": "/", "shipping_charge":"110"} ,  {"countryName" : "United Kingdom" , "countryCode" :"GB" , "currencyCode":"GBP" ,"codeUrl": "/", "shipping_charge":"84"} ,  {"countryName" : "Japan" , "countryCode" :"JP" , "currencyCode":"JPY" ,"codeUrl": "/","shipping_charge":"11860"} ,  {"countryName" : "South Korea" , "countryCode" :"KR" , "currencyCode":"KRW" ,"codeUrl": "/","shipping_charge":"95"} ,  {"countryName" : "Mexico" , "countryCode" :"MX" , "currencyCode":"MXN" ,"codeUrl": "/","shipping_charge":"2190"} ,  {"countryName" : "Malaysia" , "countryCode" :"MY" , "currencyCode":"MYR" ,"codeUrl": "/","shipping_charge":"474"} ,  {"countryName" : "Newzealand" , "countryCode" :"NZ" , "currencyCode":"NZD" ,"codeUrl": "/","shipping_charge":"160"} ,  {"countryName" : "Philippines" , "countryCode" :"PH" , "currencyCode":"PHP" ,"codeUrl": "/","shipping_charge":"6300"} ,  {"countryName" : "Qatar" , "countryCode" :"QA" , "currencyCode":"QAR" ,"codeUrl": "/","shipping_charge":"420"} ,  {"countryName" : "Hong Kong" , "countryCode" :"HK" , "currencyCode":"HKD" ,"codeUrl": "/en-hk/","shipping_charge":"95"}, {"countryName" : "UAE" , "countryCode" :"AE" , "currencyCode":"AED" ,"codeUrl": "/" , "shipping_charge":"423"}, {"countryName" : "Singapore" , "countryCode" :"SG" , "currencyCode":"SGD" ,"codeUrl": "/","shipping_charge":"153"} ,  {"countryName" : "Thailand" , "countryCode" :"TH" , "currencyCode":"THB" ,"codeUrl": "/","shipping_charge":"95"} ,  {"countryName" : "Taiwan" , "countryCode" :"TW" , "currencyCode":"TWD" ,"codeUrl": "/en-tw/","shipping_charge":"3290"}]'
    base_url = "https://www.apm.mc"
    start_urls = "https://www.apm.mc"
    handle_httpstatus_list = [404, 403, 500, 430]
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
    @inline_requests
    def country_base_url(self, response):
        filtered_urls = []
        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                url_country_code = item.get('codeUrl')
                url = f'{self.base_url}{url_country_code}'
                filtered_urls.append(url)
        except Exception as e:
            print(e)

        country_urls_list = list(set(filtered_urls))
        for url in country_urls_list:
            try:
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([url], self.proxy_cycle, rotate_headers()))
                for result in results:
                    if result:
                        country_response = TextResponse(url=url, body=result, encoding='utf-8')
                        self.get_target_urls(country_response, url)
            except Exception as e:
                self.log(f" country url  : {e}")

        for link in self.all_target_urls:
            if link:
                try:
                    loop = asyncio.get_event_loop()
                    results = loop.run_until_complete(main([link], self.proxy_cycle, rotate_headers()))
                    for result in results:
                        if result:
                            list_product_response = TextResponse(url=link, body=result, encoding='utf-8')
                            self.parse(list_product_response, link)
                except Exception as e:
                    self.log(f" Target url  : {e}")

        for sku_id, product_url in self.sku_mapping.items():
            product_badge = self.sku_mapping[sku_id].get('product_badge')
            product_url = self.sku_mapping[sku_id].get('product_url')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                dont_filter=True,
                cb_kwargs={'product_badge': product_badge, 'product_url': product_url, 'sku_id': sku_id},
            )

    def get_target_urls(self, response, base_url):
        if response:
            target_urls = response.css('li.header__primary-nav-item>a::attr(href)').getall()
            mega_menu_urls = response.css('div.mega-menu>ul>li>ul>li>a::attr(href)').getall()
            target_urls_list = list(set(target_urls + mega_menu_urls))
            for link in target_urls_list:
                if link not in self.all_target_urls:
                    if link and 'about-us' not in link and 'store-locator-1' not in link:
                        absolute_url = urljoin(base_url, link)
                        self.all_target_urls.append(absolute_url)

    def parse(self, response, base_url, **kwargs: Any):
        products_ele = response.css('div.product-card__figure')
        for products in products_ele:
            product_url = products.css("a.product-card__media::attr(href)").get()
            sku_id = products.css('div.product-card__wish>span::attr(data-product-id)').get()
            badge = products.css('.badge-list>span::text').get(default='')
            if badge:
                badge = badge.strip()
            absolute_url = urljoin(base_url, product_url)
            self.get_all_sku_mapping(absolute_url, sku_id, badge)

        next_page_link = response.css('nav.pagination>a[rel="next"]::attr(href)').get()
        if next_page_link:
            next_page_link = urljoin(self.base_url, next_page_link)
            try:
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_link], self.proxy_cycle, rotate_headers()))
                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_link, body=result, encoding='utf-8')
                        self.parse(product_response, next_page_link)
            except Exception as e:
                self.log(f" next page  : {e}")

    def get_all_sku_mapping(self, product_url, sku_id, product_badge):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'product_badge': product_badge}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'product_badge': product_badge}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'product_badge': product_badge}

    @inline_requests
    def parse_product(self, response, product_badge, product_url, sku_id):
        content = {}
        specification = {}
        if response.url.startswith('/products'):
            url_without_language = product_url.split('/', 1)[1]
        else:
            url_parts = response.url.split("/products")[1]
            url_without_language = 'products'+url_parts

        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": f'{self.base_url}/{url_without_language}',
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        languages = ["fr", "de", "es", "ja", "zh", "it"]
        for language in languages:
            url = f"{self.base_url}/{language}/{url_without_language}"
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            else:
                content_info = self.collect_content_information(resp)
                content[language] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }

        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode').lower()
                currency_code = item.get('currencyCode')
                url_country_code = item.get('codeUrl')
                shipping_charge = item.get('shipping_charge')
                if country_code in ['hk', 'cn', 'tw']:
                    url = f'{self.base_url}{url_country_code}{url_without_language}?country={country_code.upper()}'
                else:
                    url = f'{self.base_url}/{url_without_language}?country={country_code.upper()}'
                country_resp = yield Request(url, headers=rotate_headers(), dont_filter=True)
                if country_resp.status == 404:
                    self.log(f"RECEIVED 404 Response for URL: {country_resp.url}")
                else:
                    specification_info = self.collect_specification_info(country_resp, country_code, currency_code, shipping_charge)
                    specification[country_code] = specification_info

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return
        list_img = []
        imageSource = response.css('div.product-gallery__media > img::attr(src)').getall()
        for images in imageSource:
            images = response.urljoin(images)
            if images not in list_img:
                list_img.append(images)

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
                            req = Request(url_pic, headers=rotate_headers(), dont_filter=True)
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

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        main_material = ''
        secondary_material = ''
        product_color = ''
        size_dimension = []

        main_data_second = response.css('.product-info__block-item .prose p::text').getall()
        main_data = response.css('div.product-info__block-item>div>ul>li::text').getall()
        if main_data:
            for item in main_data:
                if item.startswith(("Material", "Materiale", "素材", "Matériau")):
                    material = item.split(":")[1]
                    if material:
                        main_material = material.strip()
                elif item.startswith(("Stones", "Pietre")):
                    secondary = item.split(":")[1]
                    if secondary:
                        secondary_material = secondary.strip()
                elif item.startswith(("Size", "Total chain length", "Größe", "サイズ", "Taglia",  "Taille", "Misura", "Lunghezza totale", 'Longueur totale')):
                    size_dimension.append(item)
                elif item.startswith(("Color", "Couleur", "Colore", "カラー", "Farbe")):
                    color = item.split(":")[1]
                    if color:
                        product_color = color.strip()
        elif main_data_second:
            for item in main_data_second:
                if item.startswith(("Material", "Materiale", "素材", "Matériau")):
                    material = item.split(":")[1]
                    if material:
                        main_material = material.strip()
                elif item.startswith(("Stones", "Pietre")):
                    secondary = item.split(":")[1]
                    if secondary:
                        secondary_material = secondary.strip()
                elif item.startswith(("Size", "Total length", "Größe", "サイズ", "Taglia",  "Taille", "Misura", "Lunghezza totale", 'Longueur totale')):
                    size_dimension.append(item)
                elif item.startswith(("Color", "Couleur", "Colore", "カラー", "Farbe")):
                    color = item.split(":")[1]
                    if color:
                        product_color = color.strip()
        else:
            self.log(f"Main Data Not Found")




        collection_name = response.css('.product-info__block-item>a::text').get()
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_name
        item['brand'] = "apm"
        item['manufacturer'] = self.name
        item['product_badge'] = product_badge
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        sku_long_description = ''
        sku_title = ''
        sku_short_description = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            if "offers" in json_data:
                sku_title = json_data.get('name')
                sku_long_description = json_data.get('description')
                break
        short_p_desc = response.css('div.product-info__block-item>div>ul>li::text').getall()
        if short_p_desc is not None:
            sku_short_description = ' '.join(short_p_desc)
        sku_short_description = sku_short_description if sku_short_description else ''

        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, currency_code, shipping_charge):
        availability = ''
        price = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            json_data = json.loads(script_tag)
            if "offers" in json_data:
                offers = json_data["offers"][0]
                price = offers.get('price')
                currency_code = offers.get('priceCurrency')
                availability = offers.get("availability")
                break

        sale_price = str(price)
        size_available = []
        shipping_lead_time = resp.css('details.accordion.group>div>ul>li::text').get()
        sizes = resp.css("div.variant-picker__option-values >input::attr(value)").getall()
        if sizes:
            for size in sizes:
                if size not in size_available:
                    size_available.append(size)

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": country_code,
            "domain_country_code": country_code,
            "currency": currency_code,
            "base_price": sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_charge,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": "",
            "reviews_number": "",
            "size_available": size_available,
            "sku_link": resp.url
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
            logging.error(f"Error processing image: {e}")