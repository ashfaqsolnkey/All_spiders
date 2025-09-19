import scrapy
from PIL import Image
import js2py
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


async def get_page(session, url, proxy_cycle,headers):
    retry = 0
    while retry <= 2:
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


class Hm(scrapy.Spider):
    name = "hm_men"
    all_target_urls = []
    sku_mapping = {}
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://www2.hm.com"
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    # spec_mapping = '[ {"countryCode": "gb", "url_countryCode": "en_gb"},{"countryCode": "pt", "url_countryCode": "pt_pt"},{"countryCode": "hk", "url_countryCode": "en_hk"},{"countryCode": "jp", "url_countryCode": "ja_jp"},{"countryCode": "sg", "url_countryCode": "en_sg"},{"countryCode": "kr", "url_countryCode": "ko_kr"},{"countryCode": "at", "url_countryCode": "de_at"},{"countryCode": "fr", "url_countryCode": "fr_fr"},{"countryCode": "dk", "url_countryCode": "da_dk"},{"countryCode": "de", "url_countryCode": "de_de"},{"countryCode": "gr", "url_countryCode": "el_gr"},{"countryCode": "ie", "url_countryCode": "en_ie"}, {"countryCode": "it", "url_countryCode": "it_it"}, {"countryCode": "nl", "url_countryCode": "nl_nl"}, {"countryCode": "pl", "url_countryCode": "pl_pl"},{"countryCode": "ro", "url_countryCode": "ro_ro"},{"countryCode": "es", "url_countryCode": "es_es"},{"countryCode": "se", "url_countryCode": "sv_se"},{"countryCode": "tr", "url_countryCode": "tr_tr"},{"countryCode": "ca", "url_countryCode": "en_ca"},{"countryCode": "mx", "url_countryCode": "es_mx"},{"countryCode": "us", "url_countryCode": "en_us"},{"countryCode": "au", "url_countryCode": "en_au"}]'

    spec_mapping = '[ {"countryCode": "gb", "url_countryCode": "en_gb"},{"countryCode": "es", "url_countryCode": "es_es"}]'
    start_urls = "https://www2.hm.com/en_gb/index.html"

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

    @inline_requests
    def main_page(self, response):
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            try:
                url_countryCode = item.get('url_countryCode').lower()
                url = f'https://www2.hm.com/{url_countryCode}/index.html'
                country_request = scrapy.Request(url, headers=self.headers, dont_filter=True)
                target_response = yield country_request
                if target_response.status == 200:
                    self.get_target_urls(target_response, url)
                else:
                    self.log(f"Received Response for URL: {target_response.status}")

                # url = f'https://www2.hm.com/{url_countryCode}/index.html'
                # ladies = f'https://www2.hm.com/{url_countryCode}/ladies/shop-by-product/view-all.html'
                # men = f'https://www2.hm.com/{url_countryCode}/men/shop-by-product/view-all.html'
                # self.all_target_urls.append(ladies)
                # self.all_target_urls.append(men)
            except Exception as e:
                logging.error(f"Error scraping URL: {url}. Error: {e}")

        target_urls_list = list(set(self.all_target_urls))
        params = {'page-size': 99999}
        for link in target_urls_list:
            url = link + '?' + urlencode(params)
            request = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield request
            if resp.status == 200:
                self.parse(resp, url)
            elif resp.status in [301, 302]:
                redirect_url = resp.headers.get(b'Location').decode('utf-8')
                url = resp.urljoin(redirect_url)
                redirect_req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                redirect_resp = yield redirect_req
                if redirect_resp.status == 200:
                    self.parse(redirect_resp, url)
            else:
                self.log(f"Received Response for URL: {resp.status}")

        logging.info(f'Total Sku of hm ===========>>>> : {len(self.sku_mapping)}')
        for sku_id, product_info in self.sku_mapping.items():
            product_badge = product_info.get('badge')
            product_url = product_info.get('product_url')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_badge': product_badge,'product_url': product_url}
            )

    def get_target_urls(self, response, base_url):
        script_tag = response.css('script#__NEXT_DATA__::text').get()
        if script_tag:
            try:
                json_data = json.loads(script_tag)
                menu_items = json_data['props']['pageProps']['headerData']['menuItems']
                for menu_item in menu_items:
                    if 'children' in menu_item:
                        childrens = menu_item['children']
                        for children in childrens:
                            if 'children' in children:
                                target_urls = children['children']
                                for target_url in target_urls:
                                    link = target_url['href']
                                    absolute_url = urljoin(base_url, link)
                                    if ("view-all" in absolute_url or "ver-todo" in absolute_url) and (
                                            "men" in absolute_url or "hombre" in absolute_url):
                                        self.all_target_urls.append(absolute_url)
            except Exception as e:
                print(e)

    def parse(self, response , base_url):
        sku_id = ''
        material = ''
        absolute_url = ''
        product_elements = response.css('li.product-item')
        if product_elements:
            for product_element in product_elements:
                product_url = product_element.css('a.item-link::attr(href)').get()
                if product_url:
                    absolute_url = urljoin(base_url, product_url)

                badge = product_element.css('div.percentage-marker::text').get()
                sku_id = product_element.css('.hm-product-item::attr(data-articlecode)').get()
                self.get_all_sku_mapping(absolute_url, sku_id, badge)
        else:
            product_elements = response.css('article.db650c')
            for product_element in product_elements:
                product_url = product_element.css('.e74e8f>a.e759aa::attr(href)').get()
                if product_url:
                    absolute_url = urljoin(base_url, product_url)
                badge = product_element.css('div.eed2a5.a1c5d0.d5728c>div>span::text').get()
                sku_id = product_element.css('article.db650c::attr(data-articlecode)').get()
                self.get_all_sku_mapping(absolute_url, sku_id, badge)
            script_tag = response.css('script#__NEXT_DATA__::text').get()
            if script_tag:
                try:
                    json_data = json.loads(script_tag)
                    totalPages = json_data['props']['pageProps']['plpProps']['productListingProps']['pagination'].get('totalPages')
                    current_page = json_data['props']['pageProps']['plpProps']['productListingProps']['pagination'].get('currentPage')
                    self.log(f'Current page: {current_page}, Total pages: {totalPages}')

                    try:
                        if current_page < totalPages:
                            counter = int(current_page) + 1
                            next_page_url = f'{base_url.split("?")[0]}?page={counter}'
                            loop = asyncio.get_event_loop()
                            results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))
                            for result in results:
                                if result:
                                    next_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                                    self.parse(next_response, base_url)
                    except Exception as e:
                        self.log(f"Error next_page: {e}")
                except Exception as e:
                    print(e)

    def get_all_sku_mapping(self, product_url, sku_id, badge):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}

    @inline_requests
    def parse_product(self, response, product_badge, product_url):
        content = {}
        specification = {}
        sku_id = ''
        brand = ''
        color = ''
        url_parts = product_url.split("/")
        url_without_language = "/".join(url_parts[4:])
        script_content = response.css('script#product-schema::text').get()
        try:
            if script_content:
                json_data = json.loads(script_content)
                color = json_data.get('color')
                sku_id = json_data.get('sku')
                brand = json_data['brand'].get('name')
        except json.JSONDecodeError:
            self.log('Error decoding JSON data')
        list_img = []
        size_dimensions = []
        collection_value = ''
        materials = ''
        sizes = response.css('.content.pdp-text.pdp-content div div')
        dimensions = sizes.css('dd ul li::text').getall()
        if dimensions is not None:
            size_dimensions = dimensions
        script_tags = response.css('div.product.parbase>script::text').getall()
        if script_tags:
            for script_tag in script_tags:
                if "var productArticleDetails = {" in script_tag:
                    try:
                        script_content = script_tag.split("var productArticleDetails =")[1].split('};')[0] + '}'
                        script_content = script_content.replace("isDesktop", "true")  # Assuming isDesktop is a boolean variable
                        context = js2py.EvalJs()
                        context.execute("var productArticleDetails = " + script_content)
                        json_script_data = context.productArticleDetails.to_dict()
                        images = json_script_data[sku_id]['images']
                        for image in images:
                            img = image.get('fullscreen')
                            list_img.append(img)

                        if 'compositions' in json_script_data[sku_id]:
                            materials = json_script_data[sku_id]['compositions'][0]
                        if 'collection' in json_script_data:
                            collection_value = json_script_data['collection']
                        if 'productAttributes' in json_script_data.get(sku_id, {}):
                            if size_dimensions is None:
                                size_dimensions = json_script_data[sku_id]['productAttributes']['values'].get('measurement')
                        break
                    except (json.JSONDecodeError, KeyError) as e:
                        self.log(f'Error processing product details script: {e}')
        else:
            size_dimensions = []
            script_tag = response.css('script#__NEXT_DATA__::text').get()
            if script_tag:
                try:
                    json_details = json.loads(script_tag)
                    productArticleDetails = json_details['props']['pageProps']['productPageProps']['aemData'][
                        'productArticleDetails']
                    variations = productArticleDetails['variations'][sku_id]
                    if 'compositions' in variations:
                        materials = variations['compositions'][0]
                    productAttributes = variations.get('productAttributes')
                    if 'description' in productAttributes:
                        descriptions = productAttributes['description']
                        for description in descriptions:
                            title = description.get('title')
                            if title and 'measurement' in title.lower():
                                values = description.get('values', [])
                                for value in values:
                                    size_dimensions.append(value)

                    images = variations.get('images')
                    for image in images:
                        img = image.get('image')
                        list_img.append(img)

                except (json.JSONDecodeError, KeyError) as e:
                    self.log(f'Error processing product details script: {e}')

        content_info = self.collect_content_information(response, sku_id)
        if content_info:
            content["en"] = {
                "sku_link": response.url,
                "sku_title": content_info["sku_title"],
                "sku_short_description": content_info["sku_short_description"],
                "sku_long_description": content_info["sku_long_description"]
            }
        languages = ["es_es"]
        for language in languages:
            logging.info(f'Processing: {language}')
            url = f'https://www2.hm.com/{language}/{url_without_language}'
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(resp, sku_id)
                if content_info:
                    content[language.split("_")[0]] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    content_info = self.collect_content_information(resp, sku_id)
                    if content_info:
                        content[language.split("_")[0]] = {
                            "sku_link": url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["sku_short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
            else:
                self.log(f"RECEIVED 404 Response for URL: {resp.url}")

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode')
            url_countryCode = item.get('url_countryCode')
            url = f'{self.base_url}/{url_countryCode}/{url_without_language}'
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                specification_info = self.collect_specification_info(resp, sku_id, country_code)
                if specification_info:
                    specification[country_code.lower()] = specification_info
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                country_resp = yield req
                if country_resp.status == 200:
                    specification_info = self.collect_specification_info(country_resp, sku_id, country_code)
                    if specification_info:
                        specification[country_code.lower()] = specification_info
            else:
                self.log(f"RECEIVED 404 Response for URL: {resp.url}")

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
                    base_url = 'https://'
                    url_img = urljoin(base_url, url_pic)
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            req = scrapy.Request(url_img, headers=self.headers, dont_filter=True)
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
        item['brand'] = brand
        item['product_badge'] = product_badge
        item['gender'] = 'men'
        item['collection_name'] = collection_value
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = color
        item['main_material'] = materials
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response, sku_id):
        try:
            size_dimensions_content = self.get_size_dimensions(response, sku_id)
            description = ','.join([dimensions.strip() for dimensions in size_dimensions_content])
            sku_title = ''
            sku_long_description = ''
            script_content = response.css('script#product-schema::text').get()
            try:
                if script_content:
                    json_data = json.loads(script_content)
                    sku_title = json_data.get('name')
                    sku_long_description = json_data.get('description')
            except json.JSONDecodeError:
                self.log('Error decoding JSON data')
            if not sku_title:
                return

            return {
                "sku_title": sku_title,
                "sku_short_description": sku_long_description,
                "sku_long_description": sku_long_description + description
            }
        except json.JSONDecodeError:
            self.log('Error content_information data not correct')

    def collect_specification_info(self, response, sku_id, country_code):
        currency_code = ''
        base_price = ''
        in_store = ''
        shipping_expenses = ''
        active_price = ''
        size_available = []
        script_content = response.css('script#product-schema::text').get()
        try:
            if script_content:
                json_data = json.loads(script_content)
                currency_code = json_data['offers'][0].get('priceCurrency')
        except json.JSONDecodeError:
            self.log('Error decoding JSON data')
        script_tags = response.css('div.product.parbase>script::text').getall()
        if script_tags:
            for script_tag in script_tags:
                if "var productArticleDetails = {" in script_tag:
                    try:
                        script_content = script_tag.split("var productArticleDetails =")[1].split('};')[0] + '}'
                        script_content = script_content.replace("isDesktop", "true")
                        context = js2py.EvalJs()
                        context.execute(f"var productArticleDetails = {script_content};")
                        json_data = context.productArticleDetails.to_dict()

                        # Extract sizes
                        sizes = json_data[sku_id]['sizes']
                        size_available = [size.get('name') for size in sizes]

                        base_price = json_data[sku_id]['whitePriceValue']
                        price = json_data[sku_id]
                        if "redPriceValue" in price:
                            active_price = price['redPriceValue']
                        else:
                            active_price = base_price
                        in_store = json_data[sku_id]['inStore']
                        shipping_expenses = json_data[sku_id]['deliveryDetails'].get('recommendedDelivery')
                        break
                    except (json.JSONDecodeError, KeyError) as e:
                        self.log(f'Error processing product details script: {e}')
        else:
            size_available = []
            script_tag = response.css('script#__NEXT_DATA__::text').get()
            if script_tag:
                try:
                    json_details = json.loads(script_tag)
                    productArticleDetails = json_details['props']['pageProps']['productPageProps']['aemData']['productArticleDetails']
                    variations = productArticleDetails['variations'][sku_id]
                    in_store = variations.get('productTransparencyEnabled')
                    shipping_expenses = variations['deliveryDetails'].get('recommendedDelivery')
                    active_price = variations.get('whitePriceValue')
                    if active_price:
                        base_price = active_price
                    sizes = variations.get('sizes')
                    for size in sizes:
                        size_available.append(size.get('name'))
                except (json.JSONDecodeError, KeyError) as e:
                    self.log(f'Error processing product details script: {e}')

        if base_price == "":
            return
        product_availability = self.check_product_availability(in_store)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": active_price if active_price else 0.0,
            "active_price": active_price if active_price else 0.0,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_expenses if shipping_expenses else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            # Use a default value, adjust as needed
            "marketplace_retailer_name": 'hm',
            "condition": "NEW",
            "reviews_rating_value": 0.0,  # Use a default value, adjust as needed
            "reviews_number": 0,  # Use a default value, adjust as needed
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

    def get_size_dimensions(self, response, sku_id):
        sizes = response.css('.content.pdp-text.pdp-content div div')
        size_dimensions = sizes.css('dd ul li::text').getall()
        if size_dimensions is not None:
            return size_dimensions
        else:
            script_tags = response.css('div.product.parbase>script::text').getall()
            for script_tag in script_tags:
                if "var productArticleDetails = {" in script_tag:
                    script_content = script_tag.split("var productArticleDetails =")[1].split('};')[0] + '}'
                    script_content = script_content.replace("isDesktop", "true")
                    context = js2py.EvalJs()
                    context.execute("var productArticleDetails = " + script_content)
                    json_script_data = context.productArticleDetails.to_dict()

                    if 'productAttributes' in json_script_data.get(sku_id, {}):
                        size_dimensions = json_script_data[sku_id]['productAttributes']['values'].get('measurement')
                        return size_dimensions
