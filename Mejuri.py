from PIL import Image
from urllib.parse import urlencode, urljoin
from scrapy.http import Request, TextResponse
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, scrapy, json, cloudscraper
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


class Mejuri(scrapy.Spider):
    name = "mejuri"
    sku_mapping = {}
    target_urls = []
    base_url = "https://mejuri.com"
    handle_httpstatus_list = [430, 403, 404, 302, 301]
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
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

    start_urls = "https://mejuri.com/world/en/"
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
        yield scrapy.Request(
            self.start_urls,
            callback=self.country_base_url,
            headers=self.headers,
        )

    @inline_requests
    def country_base_url(self,response):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.country_base_url,
                headers=self.headers,
                dont_filter=True,
            )
            return

        # all_scripts = response.css('body>script::text').getall()
        # for script_content in all_scripts:
        #     try:
        #         if "window.__remixContext" in script_content:
        #             remix_context_data = script_content .split("window.__remixContext =")[1].split(";__remixContext.p =")[0]
        #             script_json_data = json.loads(remix_context_data)
        #             megamenus = script_json_data["state"].get('loaderData').get("root").get("header").get("menu").get("megamenu")
        #             for megamenu in megamenus:
        #                 if "content" in megamenu:
        #                     link_entries = megamenu.get("content")[0].get("links")
        #                     for lin_entries in link_entries:
        #                         relative_url = lin_entries.get("slug")
        #                         if relative_url.startswith('https://mejuri.com/world/en'):
        #                             self.target_urls.append(relative_url)
        #                         else:
        #                             absolute_url = "https://mejuri.com/world/en" + relative_url
        #                             self.target_urls.append(absolute_url)
        #     except Exception as e:
        #         print("Unexpected error in script_content:", e)

        filtered_urls = ['https://mejuri.com/world/en/collections/hoop-earrings','https://mejuri.com/world/en/collections/new','https://mejuri.com/world/en/collections/shop-all','https://mejuri.com/world/en/collections/rings','https://mejuri.com/world/en/collections/necklaces','https://mejuri.com/world/en/collections/bracelets','https://mejuri.com/world/en/collections/mens']
        for link in filtered_urls:
            try:
                page_counter = 0
                product_response = yield Request(link, headers=self.headers, dont_filter=True)
                if product_response.status == 200:
                    self.parse(product_response, link, page_counter)
                elif product_response.status in [301, 302]:
                    product_retry_url = product_response.headers.get(b'location').decode('utf-8')
                    product_response_retry_url = product_response.urljoin(product_retry_url)
                    product_retry_res = yield Request(product_response_retry_url, headers=self.headers, dont_filter=True)
                    self.parse(product_retry_res, link, page_counter)
                else:
                    print(f"Received Response for URL: {product_response.status}")
            except Exception as e:
                self.log("Unexpected error in target_urls processing")
                print(f"Unexpected error: {e}")

        for sku_id, product_info in self.sku_mapping.items():
            product_url = product_info.get('product_urls')
            material = product_info.get('material')
            product_badge = product_info.get('product_badge')
            base_url = 'https://mejuri.com'
            url = urljoin(base_url, product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id, 'material': material, 'product_badge': product_badge}
            )

    def parse(self, response,link, page_counter):
        product_urls = response.css('div.relative.flex.flex-col.h-full')
        for product_element in product_urls:
            product_url = product_element.css('div[data-testid="product-card-hover-quick-add"] a::attr(href)').get()
            if product_url:
                product_url = urljoin(response.url, product_url)
            sku_id = product_element.css('[data-object-id]::attr(data-object-id)').get()
            material_Name = product_element.css('div.type-caption > span::text').get()
            product_badge = product_element.css('div.absolute.top-md.left-md.flex.gap-2>div::text').get() or ''
            self.get_all_sku_mapping(product_url, sku_id, material_Name, product_badge)

        if product_urls:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}?page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")
                proxy = next(self.proxy_cycle)
                # session = requests.session()
                scrapper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
                next_page_resp = scrapper.get(next_page_url, headers=self.headers,
                                              proxies={'http': proxy, 'https': proxy})
                print(next_page_resp.status_code)
                if next_page_resp.status_code == 200:
                    product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                    self.parse(product_response, link, counter)
            except Exception as e:
                print("Unexpected error in pagination:", e)

    def get_all_sku_mapping(self, product_url, sku_id, material_Name, product_badge):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "en/" not in existing_url:
                self.sku_mapping[sku_id] = {'product_urls': product_url, 'material': material_Name, 'product_badge': product_badge}

            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_urls': product_url, 'material': material_Name, 'product_badge': product_badge}
        elif product_url and "en/" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_urls': product_url, 'material': material_Name, 'product_badge': product_badge}

    @inline_requests
    def parse_product(self, response, product_url, sku_id, material, product_badge):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id, 'material': material, 'product_badge': product_badge}
            )
            return
        elif response.status in [404]:
            logging.warning(f"Page not found for {product_url}")
            return
        short_description = ' '
        content = {}
        specification = {}
        size_dimensions = []
        list_img = []
        img_selectors = response.css('div.h-full.relative.overflow-hidden.z-base.w-screen>img::attr(srcset)').getall()
        for img_selector in img_selectors:
            img_split = img_selector.split(',')[-1]
            img_url = img_split.split()[0]
            list_img.append(img_url)

        script_tags = response.css('script::text').getall()
        for script_tag in script_tags:
            try:
                if 'window.__remixContext = {' in script_tag:
                    split_text = script_tag.split(';__remixContext.p = function(v,e,p,x) {')[0].split('window.__remixContext = {')[1]
                    product_details_regex = r'"productDetails":\{"reference":\{"id":"(gid:\/\/shopify\/Metaobject\/\d+)","field":\{"value":"(.*?)"\}\}\}'
                    product_match = re.search(product_details_regex, split_text)
                    if product_match:
                        field_value = product_match.group(2)
                        unescaped_field_value = field_value.encode().decode('unicode_escape')
                        parsed_data = json.loads(unescaped_field_value)

                        pendant_text = parsed_data['children'][0]['children'][0]['value']
                        pendant_details = pendant_text.replace("\\r", "").replace("\\n", "").split("- ")
                        size_dimensions = [detail.strip() for detail in pendant_details if detail.strip()]
                        short_description = short_description.join(pendant_details)
            except json.JSONDecodeError:
                self.log('Error in script tag size diemension')
        if material == '':
            material = response.css('.flex-row.mb-xxs div::text').get()
        url_without_language = product_url.split('world/en/')[1]
        if url_without_language.startswith('shop'):
            split_url = url_without_language.split('/')[1:]
            url_without_language = '/'.join(split_url)

        content_info = self.collect_content_information(response, short_description)
        content["en"] = {
            "sku_link": product_url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        spec_mapping = '[{"countryCode": "US", "url_countryCode": "world/en", "currency": "USD"},{"countryCode": "GB", "url_countryCode": "gb/en", "currency": "GBP"},{"countryCode": "DE", "url_countryCode": "de/en", "currency": "EUR"},{"countryCode": "CA", "url_countryCode": "ca/en", "currency": "CAD"},{"countryCode": "AU", "url_countryCode": "au/en", "currency": "AUD"}]'
        common_mapping = ['AE', 'TH', 'TW', 'SE', 'ES', 'KR', 'SK', 'SG', 'SA', 'QA', 'PR', 'PL', 'PH', 'NO', 'NZ', 'NL', 'MY', 'JP', 'IL', 'IE', 'ID', 'HU', 'HK', 'FR', 'FI', 'DK', 'CZ', 'BE', 'AT']
        json_data = json.loads(spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode').lower()
            url_countryCode = item.get("url_countryCode")
            currency_code = item.get("currency")
            url = f'{self.base_url}/{url_countryCode}/{url_without_language}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            elif resp.status in [301, 302]:
                try:
                    redirected_url = resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    scraper = cloudscraper.create_scraper()
                    country_response = scraper.get(url,headers=self.headers)
                    resp = TextResponse(url='', body=country_response.text, encoding='utf-8')
                    specification_info = self.collect_specification_info(resp, country_code, currency_code, url)
                    specification[country_code.lower()] = specification_info
                except requests.exceptions.RequestException as e:
                    print("Error:", e)
            else:
                specification_info = self.collect_specification_info(resp, country_code, currency_code, url)
                specification[country_code.lower()] = specification_info

        us_data = next((item for item in json_data if item['countryCode'] == 'US'), None)
        for country_code in common_mapping:
            url_countryCode = us_data["url_countryCode"]
            currency_code = us_data["currency"]
            url = f'{self.base_url}/{url_countryCode}/{url_without_language}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            elif resp.status in [301, 302]:
                try:
                    redirected_url = resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    scraper = cloudscraper.create_scraper()
                    country_response = scraper.get(url)
                    resp = TextResponse(url='', body=country_response.text, encoding='utf-8')

                    specification_info = self.collect_specification_info(resp, country_code, currency_code, url)
                    specification[country_code.lower()] = specification_info
                except requests.exceptions.RequestException as e:
                    print("Error:", e)
            else:
                specification_info = self.collect_specification_info(resp, country_code, currency_code,url)
                specification[country_code.lower()] = specification_info

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(self, list_img)
        else:
            if list_img:
                directory = self.directory + sku_id
                for url_pic in list_img:
                    trial_image = 0
                    while trial_image < 10:
                        try:
                            proxy = next(self.proxy_cycle)
                            res = requests.get(url_pic, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                            if res.status_code == 403:
                                print("response ", res.status_code)
                            else:
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

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        badge = response.css(".styled__SliderHeaderWrapper-sc-1xjbwxp-14.eQBpID span.styled__Container-sc-aw9czy-0.TnPFK::text").get()
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = "Mejuri"
        item['mpn'] = ''
        item['manufacturer'] = self.name
        item['product_badge'] = product_badge
        item['sku'] = sku_id
        item['main_material'] = material
        item['secondary_material'] = ''
        item['sku_color'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['specification'] = specification
        item['content'] = content
        yield item

    def collect_specification_info(self, response,country_code, currency_code, url):
        base_price = ''
        availability = ''
        total_review = ''
        rating_value = ''
        base_price = ''
        sales_price = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        try:
            for script_content in script_tag_content:
                json_data = json.loads(script_content)
                if isinstance(json_data, list) and len(json_data) > 1 and 'offers' in json_data[1]:
                    currency_code = json_data[1]['offers'].get('priceCurrency', 'N/A')
                    availability = json_data[1]['offers'].get('availability', 'N/A')

                    if 'aggregateRating' in json_data[0]:
                        rating_value = json_data[0]['aggregateRating'].get('ratingValue', 'N/A')
                        total_review = json_data[0]['aggregateRating'].get('ratingCount', 'N/A')
                    else:
                        rating_value = 'N/A'
                        total_review = 'N/A'
                    break
                elif isinstance(json_data, dict) and 'offers' in json_data:
                    currency_code = json_data['offers'].get('priceCurrency', 'N/A')
                    availability = json_data['offers'].get('availability', 'N/A')

                    if 'aggregateRating' in json_data:
                        rating_value = json_data['aggregateRating'].get('ratingValue', 'N/A')
                        total_review = json_data['aggregateRating'].get('ratingCount', 'N/A')
                    else:
                        rating_value = 'N/A'
                        total_review = 'N/A'
                    break
        except json.JSONDecodeError:
            self.log('Error decoding JSON data')

        base_price_string = response.css('span.line-through.text-content-mid::text').get()
        if base_price_string:
            base_price = self.extract_price_info(base_price_string)
        else:
            base_price_str = response.css('div.flex.gap-x-xs.flex-wrap>span::text').get()
            base_price = self.extract_price_info(base_price_str)

        for index, sr_only_text in enumerate(response.css('div.flex.gap-x-xs.flex-wrap span.sr-only::text').getall()):
            if "Sale Price" in sr_only_text:
                price_string = response.css('div.flex.gap-x-xs.flex-wrap span::text').getall()[-1]
                sales_price = self.extract_price_info(price_string)
                print(f"Sale Price: {sales_price}")
                break

        sizes = response.css('div.flex.gap-xs.flex-wrap.justify-center button span.flex::text').getall()
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": "en",
            "domain_country_code": country_code.lower(),
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": sales_price if sales_price else base_price,
            "active_price": sales_price if sales_price else base_price,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": '',
            "shipping_expenses": "Free Shipping",
            "marketplace_retailer_name": 'mejuri',
            "condition": "NEW",
            "reviews_rating_value": rating_value,
            "reviews_number": total_review,
            "size_available": sizes,
            "sku_link": url,
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


    def collect_content_information(self, response, short_description):
        sku_title = ''
        sku_short_description = short_description
        sku_long_description = ''

        size_deimension = response.css('.transition-opacity.duration-75.pb-md.opacity-100.delay-75 p::text').extract()
        print(size_deimension)
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if isinstance(json_data, list):
                    for entry in json_data:
                        sku_title = entry.get('name')
                        sku_long_description = entry.get('description')
                        break
                elif isinstance(json_data, dict) and 'offers' in json_data:
                    sku_title = json_data.get('name', 'N/A')
                    sku_long_description = json_data.get('description', 'N/A')
                    break
            except json.JSONDecodeError:
                print("Error parsing JSON-LD content.")
                continue

        return {
            "sku_title": sku_title,
            "sku_long_description": f'{sku_long_description}{sku_short_description}',
            "sku_short_description": f'{sku_long_description}{sku_short_description}'
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
            return "No"

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