from itertools import cycle
from urllib.parse import urljoin
import scrapy
from inline_requests import inline_requests
from scrapy import Request
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class SingularuSpider(scrapy.Spider):
    name = "singularu"
    products = []
    sku_mapping = {}
    all_target_urls = []
    base_url = "https://eu.singularu.com/"
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

    start_urls = "https://eu.singularu.com/"

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://www.pdpaola.com/collections/earrings',
        'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

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
        fetched_urls = response.css('link[rel="alternate"]::attr(href)').getall()
        country_urls_list = list(set(fetched_urls))
        for url in country_urls_list:
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            target_response = yield req
            if target_response.status == 200:
                self.get_target_urls(target_response, url)

        for link in self.all_target_urls:
            try:
                req = scrapy.Request(link, headers=self.headers, dont_filter=True)
                product_response = yield req
                if product_response.status == 200:
                    self.parse(product_response,link)
                else:
                    self.log(f"Received Response for URL: {product_response.status}")
            except Exception as e:
                print(e)

        for sku_id, product_url in self.sku_mapping.items():
            product_badge = self.sku_mapping[sku_id].get('product_badge')
            product_url = self.sku_mapping[sku_id].get('product_url')
            material = self.sku_mapping[sku_id].get('material')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'badge': product_badge, 'product_url': product_url, 'material': material}
            )

    def get_target_urls(self, response, base_url):
        if response:
            product_urls = response.css('ul.s-header__nav>li>ul>li>a::attr(href)').getall()
            target_urls_list = list(set(product_urls))
            for link in target_urls_list:
                if link not in self.all_target_urls and "pages/" not in link:
                    absolute_url = urljoin(base_url, link)
                    self.all_target_urls.append(absolute_url)

    def parse(self, response, link):
        sku_id = ''
        product_elements = response.css('.product__container')
        for product_element in product_elements:
            product_url = product_element.css('a.product__image:nth-child(1)::attr(href)').get()
            material = product_elements.css('.product__materials span::text').get()
            badges_exists = response.css('.badges-product > div:nth-child(2)::text').get(default='')
            badges = badges_exists.strip().replace('\n', '') if badges_exists else ''
            product_badge = badges if badges else ''
            get_sku_url = urljoin(link, product_url)
            proxy = next(self.proxy_cycle)
            sku_resp = requests.get(get_sku_url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
            if sku_resp.status_code == 200:
                sku_response = TextResponse(url='', body=sku_resp.text, encoding='utf-8')
                sku_id = self.sku_get(sku_response)
            self.get_all_sku_mapping(get_sku_url, sku_id, product_badge, material)

        next_page_link = response.css('link[rel="next"]::attr(href)').get()
        if next_page_link:
            next_page_link = urljoin(link, next_page_link)
            proxy = next(self.proxy_cycle)
            next_page_resp = requests.get(next_page_link, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
            if next_page_resp.status_code == 200:
                product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                self.parse(product_response, next_page_link)

    def get_all_sku_mapping(self, product_url, sku_id, product_badge, material):
        if "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'product_badge': product_badge, 'material': material}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'product_badge': product_badge, 'material': material}
        elif "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'product_badge': product_badge, 'material': material}

    def sku_get(self, response):
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data and "sku" in json_data:
                        sku = json_data.get('sku')
                        return sku
            except json.JSONDecodeError:
                self.log('Error decoding JSON data')

    @inline_requests
    def parse_product(self, response, material, badge, product_url):
        content = {}
        specification = {}
        sku_id = ''
        item_brand = ''
        gtin13 = ''
        url_parts = product_url.split("/")
        if url_parts:
            if url_parts[3] in ['es-de', 'en-de', "de-de", 'es']:
                url_without_lang = "/".join(url_parts[4:])
            else:
                url_without_lang = "/".join(url_parts[3:])
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data and "sku" in json_data:
                    sku_id = json_data.get('sku')
                    item_brand = json_data["brand"].get("name")
                    gtin13 = json_data["offers"][0].get("gtin13")
                    break
            except json.JSONDecodeError:
                self.log('Error decoding JSON data')

        if sku_id and sku_id not in self.products:
            self.products.append(sku_id)
            secondary_material = response.css('.collapse dl:nth-child(2) dd::text').get()
            url = f'{self.base_url}{url_without_lang}'
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(response, material, secondary_material)
                content['en'] = {
                    "sku_link": resp.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            change_base_url = "https://singularu.com/"
            url = f'{change_base_url}{url_without_lang}'
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(resp, material, secondary_material)
                content['es'] = {
                    "sku_link": resp.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            else:
                self.log(f"Received 404 response for URL: {resp.url}")

            change_base_url = "https://singularu.com/"
            url = f'{change_base_url}de-de/{url_without_lang}'
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(resp, material, secondary_material)
                content['de'] = {
                    "sku_link": resp.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            else:
                self.log(f"Received 404 response for URL: {resp.url}")

            spec_mapping = '[{"countryCode":"AT","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"BE","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"DE","url":"/de-de/","url_countryCode":"de","currency_code":"EUR","language": "de"},{"countryCode":"EE","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"ES","url":"/","url_countryCode":"es","currency_code":"EUR","language": "es"},{"countryCode":"FI","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"FR","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"GR","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"IE","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"IT","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"LT","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"LU","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"LV","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"MC","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"MT","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"NL","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"PT","url":"/","url_countryCode":"es","currency_code":"EUR","language": "es"},{"countryCode":"SI","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"SK","url_countryCode":"en","currency_code":"EUR","language": "en"},{"countryCode":"SM","url_countryCode":"en","currency_code":"EUR","language": "en"}]'
            try:
                json_data = json.loads(spec_mapping)
                for item in json_data:
                    country_code = item.get('countryCode').lower()
                    currency_code = item.get('currency_code')
                    url_countryCode = item.get('url_countryCode')
                    url_code = item.get('url')
                    language = item.get('language')
                    if url_countryCode == 'en':
                        url = f'{self.base_url}{url_without_lang}'
                        req = Request(url, headers=rotate_headers(),  dont_filter=True)
                        resp = yield req
                        if resp.status == 200:
                            specification_info = self.collect_specification_info(resp, url_countryCode, currency_code, language, sku_id)
                            specification[country_code] = specification_info
                        else:
                            self.log(f"Received 404 response for URL: {resp.url}")
                    else:
                        new_url = "https://singularu.com"
                        url = f'{new_url}{url_code}{url_without_lang}'
                        req = Request(url, headers=rotate_headers(), dont_filter=True)
                        resp = yield req
                        if resp.status == 200:
                            specification_info = self.collect_specification_info(resp, url_countryCode, currency_code, language, sku_id)
                            specification[country_code] = specification_info
                        else:
                            self.log(f"Received 404 response for URL: {resp.url}")

            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

            list_img = []
            list_img_without_http = response.css('.product-carousel__image:not(.d-none) ::attr(src)').getall()
            if list_img_without_http:
                list_img_url = [url for url in list_img_without_http if not url.startswith('https://')]
                for images in list_img_url:
                    img = "http:" + images
                    list_img.append(img)

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

            time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            domain, domain_url = self.extract_domain_domain_url(response.url)
            size_dimensions = []

            measurment_dimension = response.css('.collapse[id=productDetail] dl:contains("MEASUREMENTS") dd')
            measurment = measurment_dimension.css('dd::text').get()
            if measurment:
                size_dimensions.append(measurment)
            elif measurment_dimension := response.css('.collapse[id=productDetail] dl:contains("MEDIDAS") dd'):
                measurment_sec = measurment_dimension.css('dd::text').get()
                if measurment_sec:
                    size_dimensions.append(measurment_sec)
            elif measurment_dimension := response.css('.collapse[id=productDetail] dl:contains("MAßE") dd'):
                measurment_sec = measurment_dimension.css('dd::text').get()
                if measurment_sec:
                    size_dimensions.append(measurment_sec)

            motif_dimension = response.css('.collapse[id=productDetail] dl:contains("MOTIF") dd')
            motif = motif_dimension.css('dd ::text').get()
            if motif:
                size_dimensions.append(motif)

            dimension_size = response.css('.collapse[id=productDetail] dl:contains("SIZE") dd')
            size_details = dimension_size.css('dd ::text').get()
            if size_details:
                size_dimensions.append(size_details)
            else:
                dimension_size = response.css('.collapse[id=productDetail] dl:contains("TALLAS") dd')
                size_details = dimension_size.css('dd ::text').get()
                if size_details:
                    size_dimensions.append(size_details)

            closure_dim = response.css('.collapse[id=productDetail] dl:contains("CLOSURE") dd')
            closure = closure_dim.css('dd::text').get()
            units = ['mm', 'cm', 'diameter', 'Length', 'thickness', 'width']
            if closure:
                for detail_text in closure:
                    if any(unit in detail_text for unit in units):
                        size_dimensions.append(detail_text.strip())
            elif closure_dim := response.css('.collapse[id=productDetail] dl:contains("CIERRE") dd'):
                closure = closure_dim.css('dd::text').get()
                if closure:
                    for detail_text in closure:
                        if any(unit in detail_text for unit in units):
                            size_dimensions.append(detail_text.strip())
            else:
                closure_dim = response.css('.collapse[id=productDetail] dl:contains("VERSCHLUSS") dd')
                closure = closure_dim.css('dd::text').get()
                units = ['mm', 'cm', 'diameter', 'Length', 'thickness', 'width']
                if closure:
                    for detail_text in closure:
                        if any(unit in detail_text for unit in units):
                            size_dimensions.append(detail_text.strip())

            details_dim = response.css('.collapse[id=productDetail] dl:contains("DETAILS") dd')
            if details_dim:
                detail = details_dim.css('dd::text').get()
                for text in detail:
                    if any(unit in text for unit in units):
                        size_dimensions.append(text.strip())
            else:
                details_dim = response.css('.collapse[id=productDetail] dl:contains("DETALLES") dd')
                if details_dim:
                    detail = details_dim.css('dd::text').get()
                    for text in detail:
                        if any(unit in text for unit in units):
                            size_dimensions.append(text.strip())

            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['brand'] = item_brand
            item['manufacturer'] = self.name
            item['product_badge'] = badge
            item['sku'] = sku_id
            item['gtin13'] = str(gtin13)
            item['sku_color'] = ''
            item['main_material'] = material
            item['secondary_material'] = secondary_material
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimensions
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response, material, secondary_material):
        full_description = ''
        short_description = ''
        sku_title = ""
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data and "sku" in json_data:
                    sku_title = json_data.get('name')
                    full_description_1 = json_data.get('description')
                    if full_description_1:
                        full_description = full_description_1.strip()

            except Exception as e:
                print(e)

        product_details = response.css('.collapse[id=productDetail] dd::text').getall()
        if len(product_details) > 2:
            product_short_description = product_details[2]
        else:
            product_short_description = ''
        if product_short_description:
            short_description = product_short_description.strip() + material + secondary_material
        sku_long_description = full_description + ''.join(short_description)
        return {
            "sku_title": sku_title,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, country_code, currency_code, language, sku_id):
        sku = ''
        sale_price = ''
        availability = ''
        product_name = ''
        product_sale_price = response.css('.product-price.price--large > span.fw-bold::text').get()
        if product_sale_price:
            sale_price = self.extract_price_info(product_sale_price)
        product_base_price = response.css('.product-price.price--large > span.text-black-50::text').get()
        if product_base_price:
            base_price = self.extract_price_info(product_base_price)
        else:
            base_price = sale_price
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    product_name = json_data.get('name')
                    for offer in json_data['offers']:
                        sku = offer.get('sku')
                        if sku == sku_id:
                            currency_code = offer.get('priceCurrency')
                            availability = offer.get('availability')
                            break
            except json.JSONDecodeError as e:
                print(f"decoding JSON Offers: {e}")
        sizes = []
        size = response.css('.filter-btn-size label::text').getall()
        if size:
            for item in size:
                sizes.append(item.strip())
        else:
            sizes = []
        shipping_expenses = self.extract_shipping_expenses(response)
        shipping_lead_time = self.extract_shipping_lead_time(response)
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        trustpilot_div = response.css('div.trustpilot-widget')
        if trustpilot_div:
            sku = trustpilot_div.attrib['data-sku']
        get_rewiews = self.get_review_rating(sku, product_name)
        numberOfstars = ''
        numberOfReviews = ''
        try:
            if get_rewiews:
                data = json.loads(get_rewiews.text)
                numberOfstars = data['aggregateRating']['ratingValue']
                numberOfReviews = data['aggregateRating']['reviewCount']

        except Exception as e:
            logging.error(f"processing Review Not Getting: {e}")

        return {
            "lang": language,
            "domain_country_code": country_code,
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "NA",
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            "condition": "NEW",
            "reviews_rating_value": numberOfstars,  # Use a default value, adjust as needed
            "reviews_number": numberOfReviews,  # Use a default value, adjust as needed
            "size_available": sizes if sizes else [],
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
            availability_value = availability.lower()
            if "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Product Out of Stock"
                return "No", out_of_stock_text
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return

    def get_review_rating(self, sku, product_name):
        sku_ids = sku.replace(",","%2C")
        product_sku_name = product_name.replace(' ', "%20")
        url = f'https://widget.trustpilot.com/data/jsonld/business-unit/5fe9a2a69f1be00001470940/product-imported?sku={sku_ids}&numberOfReviews=10&productName={product_sku_name}&language=en&templateId=5763bccae0a06d08e809ecbb'

        payload = {}
        headers = {
            'authority': 'widget.trustpilot.com',
            'accept': '*/*',
            'accept-language': 'en-GB,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://eu.singularu.com',
            'pragma': 'no-cache',
            'referer': 'https://eu.singularu.com/',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        return response

    def extract_shipping_expenses(self, response):
        envio_economy = ''
        envio_express = ''
        envio_super_express = ''
        shipping_expenses = ''
        try:
            shipping_text_de = response.css('.collapse[id="productShippingMd"] li::text').getall()
            shipping_text = response.css('.collapse[id="productShippingMd"] p ::text').getall()
            indices = [i + 1 for i, x in enumerate(shipping_text) if x.startswith('· Envío Economy') or x.startswith('· Envío Express 24h') or x.startswith('· Envío Súper Express')]
            if indices:
                next_values = [shipping_text[idx] if idx < len(shipping_text) else None for idx in indices]
                envio_economy = 'Envío Economy'+next_values[0].replace(",", ".").replace("-","")
                envio_economy = 'Envío Economy'+next_values[1].replace(",", ".").replace("-","")
                if len(next_values) > 2:
                    envio_super_express = 'Envío Súper Express'+next_values[2].replace(",", ".")
            elif shipping_text_de:
                for text in shipping_text_de:
                    if "€" in text:
                        envio_economy = 'Standardversand ' + text.split("-")[1].replace(",", ".").strip()
            else:
                shipping_text = response.css('.collapse[id="productShippingMd"] p ::text').getall()
                for text in shipping_text:
                    if "Express Shipping 24h" in text:
                        envio_super_express = 'Super Express Shipping'+text.split("-")[1].replace(",", ".").strip()
                    elif "Express Shipping 48h" in text:
                        envio_express = "Express Shipping" + text.split("-")[1].replace(",", ".").strip()
                    elif "Economy Shipping 7 days" in text:
                        envio_express = "Economy Shipping" + text.split("-")[1].replace(",", ".").strip()
                    elif "Free Shipping" in text:
                        envio_express = "Free Shipping" + text.split("-")[0].strip()
            shipping_expenses = envio_economy +envio_express +envio_super_express
        except Exception as e:
            print(e)
        return shipping_expenses

    def extract_shipping_lead_time(self, response):
        shipping_lead_time = ''
        envio_economy = ''
        envio_express = ''
        envio_super_express = ''
        express_express = ''
        try:
            if response.url.startswith("https://singularu.com/"):
                shipping_method = response.css('.collapse[id="productShippingMd"] strong::text').getall()
                for string in shipping_method:
                    if "Envío Economy" in string:
                        envio_economy = "Envío Economy" + string.split("· ")[-1].strip()
                    elif "Envío Express" in string:
                        envio_economy = "Envío Express" + string.split("· ")[-1].strip()
                    elif "Envío Súper Express" in string:
                        envio_super_express = "Envío Súper Express" + "Servicio disponible de Lunes a Sábado de 10:00 a 20:00."
                    elif "Standardversand" in string:
                        envio_economy = string
            elif response.url.startswith("https://eu.singularu.com/"):
                shipping_method = response.css('.collapse[id="productShippingMd"] p::text').getall()
                for text in shipping_method:
                    if "Express Shipping 24h" in text:
                        express_express = "Super Express Shipping" +text.split("-")[0].strip()
                    elif "Express Shipping 48h" in text:
                        envio_express = "Express Shipping" + text.split("-")[0].strip()
                    elif "Economy Shipping 7 days" in text:
                        envio_super_express = "Economy Shipping" + text.split("-")[0].strip()
            shipping_lead_time = envio_economy + envio_express+ envio_super_express+express_express
        except Exception as e:
            print(e)
        return shipping_lead_time



