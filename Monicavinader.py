import scrapy
from PIL import Image
from urllib.parse import urlencode, urljoin
from scrapy.http import Request, TextResponse
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from scrapy.selector import Selector
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class Monicavinader(scrapy.Spider):
    name = "monicavinader"
    sku_mapping = {}
    all_target_urls = []
    get_country_code = ''
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    base_url = "https://www.monicavinader.com"
    handle_httpstatus_list = [430, 404, 307, 302, 301, 403]
    spec_mapping = '[ {"countryCode": "sg", "url_countryCode": "/hk"},{"countryCode": "gb", "url_countryCode": "/"}, {"countryCode": "us", "url_countryCode": "/us"}, {"countryCode": "es", "url_countryCode": "/es"},{"countryCode": "au", "url_countryCode": "/au"}, {"countryCode": "ae", "url_countryCode": "/ae"},{"countryCode": "ca", "url_countryCode": "/ca"},{"countryCode": "cn", "url_countryCode": "/cn"},{"countryCode": "de", "url_countryCode": "/de"},{"countryCode": "hk", "url_countryCode": "/hk"},{"countryCode": "ar", "url_countryCode": "/us"},{"countryCode": "at", "url_countryCode": "/es"},{"countryCode": "be", "url_countryCode": "/us"},{"countryCode": "cl", "url_countryCode": "/us"},{"countryCode": "co", "url_countryCode": "/us"},{"countryCode": "cz", "url_countryCode": "/es"},{"countryCode": "dk", "url_countryCode": "/es"},{"countryCode": "eg", "url_countryCode": "/ae"},{"countryCode": "fr", "url_countryCode": "/es"},{"countryCode": "gr", "url_countryCode": "/es"},{"countryCode": "it", "url_countryCode": "/es"},{"countryCode": "jp", "url_countryCode": "/hk"},{"countryCode": "mx", "url_countryCode": "/us"},{"countryCode": "nl", "url_countryCode": "/es"},{"countryCode": "no", "url_countryCode": "/es"},{"countryCode": "pe", "url_countryCode": "/us"},{"countryCode": "qa", "url_countryCode": "/ae"},{"countryCode": "sa", "url_countryCode": "/ae"},{"countryCode": "se", "url_countryCode": "/es"},{"countryCode": "ch", "url_countryCode": "/es"},{"countryCode": "tw", "url_countryCode": "/hk"},{"countryCode": "tr", "url_countryCode": "/es"},{"countryCode": "id", "url_countryCode": "/us"},{"countryCode": "my", "url_countryCode": "/us"},{"countryCode": "nz", "url_countryCode": "/us"},{"countryCode": "za", "url_countryCode": "/us"},{"countryCode": "kr", "url_countryCode": "/us"},{"countryCode": "th", "url_countryCode": "/us"},{"countryCode": "ng", "url_countryCode": "/us"}]'
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
    start_urls = "https://www.monicavinader.com/es/"

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
    def country_base_url(self, response):
        try:
            url = 'https://www.monicavinader.com/es/'
            country_request = scrapy.Request(url, headers=self.headers, dont_filter=True)
            target_response = yield country_request
            if target_response.status == 200:
                self.get_target_urls(target_response)
            elif target_response.status == 302:
                redirected_url = target_response.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                target_response = yield req
                self.get_target_urls(target_response)
            else:
                self.log(f"Received Response for URL: {target_response.status}")

        except Exception as e:
            logging.error(f"Error scraping URL: {url}. Error: {e}")

        filtered_urls = list(set(self.all_target_urls))
        for link in filtered_urls:
            try:
                page_counter = 200
                skip_links = ['gift-guides', 'about', 'logistics', 'repairs-recycling', 'store-services']
                if not any(skip_link in link for skip_link in skip_links) and not link.startswith('https'):
                    json_key = ''
                    url = response.urljoin(link)
                    proxy = next(self.proxy_cycle)
                    request = scrapy.Request(url, headers=self.headers, dont_filter=True)
                    list_product_response = yield request
                    if list_product_response.status == 200:
                        script_list = list_product_response.css('script::text').getall()
                        if script_list:
                            for script_tag in script_list:
                                if 'window.mv.constructor.indexes = {' in script_tag:
                                    filter_name = re.search(r'window\.mv\.plp\.filterName\s*=\s*"([^"]+)"', script_tag)
                                    filter_value = re.search(r'window\.mv\.plp\.filterValue\s*=\s*"([^"]+)"', script_tag)
                                    script_key = script_tag.split("key:")[1].split(',')[0]
                                    if script_key:
                                        json_key = script_key.replace("'", " ").strip()
                                    if filter_name and filter_value:
                                        filter_name_match = filter_name.group(1)
                                        filter_value_match = filter_value.group(1)
                                        product_api = f'https://ac.cnstrc.com/browse/{filter_name_match}/{filter_value_match}?key={json_key}&offset=0&num_results_per_page=200'
                                        requests_api = requests.get(product_api, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                                        list_product_response = TextResponse(url='', body=requests_api.text, encoding='utf-8')
                                        self.parse(list_product_response, filter_name_match, filter_value_match, json_key, page_counter)
                    else:
                        self.log(f"Received Response for URL: {list_product_response.status_code}")
            except Exception as e:
                print(e)

        logging.info(f'Total Sku of Monicavinader : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            product_badge = self.sku_mapping[sku_id].get('badge')
            product_url = self.sku_mapping[sku_id].get('product_url')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'product_badge': product_badge}
            )

    def get_target_urls(self, response):
        if response:
            target_urls = response.css('.header-nav__links>li>a::attr(href)').getall()
            target_urls_list = []
            for target_url in target_urls:
                if "stockists" not in target_url and not target_url.endswith(".pdf") and not target_url.endswith("/factories") and not target_url.startswith("https://help.monicavinader") and not target_url.endswith("/mv-events"):
                    target_urls_list.append(target_url)
            for link in target_urls_list:
                if link and link not in self.all_target_urls:
                    self.all_target_urls.append(link)

    def parse(self, response, filter_name_match, filter_value_match, json_key, page_counter):
        data = json.loads(response.text)
        total_count = data.get('response').get('total_num_results')
        for result in data.get('response').get('results'):
            main_data = result.get('data')
            product_url = main_data.get('url')
            product_badge = main_data.get('badge')
            sku_id = main_data.get('code')
            if 'gift-sets' not in product_url:
                self.get_all_sku_mapping(product_url, sku_id, product_badge)

        if total_count > page_counter:
            try:
                offset = int(page_counter) + 1
                counter = 99
                proxy = next(self.proxy_cycle)
                product_api = f'https://ac.cnstrc.com/browse/{filter_name_match}/{filter_value_match}?key={json_key}&offset={offset}&num_results_per_page={counter}'
                requests_api = requests.get(product_api, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                list_product_response = TextResponse(url='', body=requests_api.text, encoding='utf-8')
                offset = int(offset) + int(counter)
                self.parse(list_product_response, filter_name_match, filter_value_match, json_key, offset)
            except Exception as e:
                self.log(f"Error next_page: {e}")

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
    def parse_product(self, response, product_url, product_badge):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'product_badge': product_badge}
            )
            return

        url_parts = product_url.split("/")
        url_without_language = "/".join(url_parts[3:])
        content = {}
        size_dimensions = []
        specification = {}
        brand = ''
        sku_id = ''
        image = ''
        mpn = ''
        sku_title = ''
        delivery_data = ''
        barcode = ''
        sku_long_description = ''
        secondary_material = ''
        html_content = response.text
        pattern = re.compile(r'<script>.*?if \(typeof dataLayer == "undefined"\) \{(.*?)\}</script>', re.DOTALL)
        match = pattern.search(html_content)
        if match:
            script_content = match.group(1).strip()
            script_data = scrapy.Selector(text=script_content).xpath('//text()').get()
            split_script = script_data.split("dataLayer.push(")[1].split(");")[0]
            if split_script:
                json_data = json.loads(split_script)
                sku_id = json_data['products']['productCode']

        script_tags = response.css('script::text').getall()
        for script_content in script_tags:
            time.sleep(2)
            if '"event": "productDetail",' in script_content:
                split_content = script_content.split("dataLayer.push(")[1].split(");")[0]
                if split_content:
                    try:
                        json_content = json.loads(split_content)
                        barcode_gtin13 = json_content['ecommerce']["detail"]["products"][0]
                        if "barcode" in barcode_gtin13:
                            barcode = barcode_gtin13["barcode"]
                            break
                    except json.JSONDecodeError as e:
                        print(f"JSON decoding error: {e}")
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            try:
                cleaned_json = script_tag_content.strip()
                data = json.loads(cleaned_json)
                if data:
                    sku_title = data.get("name")
                    mpn = data.get("mpn")
                    brand = data.get("brand", {}).get("name")
                    sku_long_description = data.get("description")
                    image = data.get("image")
                else:
                    self.logger.warning("No Product JSON-LD block found.")
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode failed: {e}")

        patterns = {
            "Chain width": r'Chain width (\d+(\.\d+)?)mm',
            "Heart dimensions": r'Heart height (\d+(\.\d+)?)mm, width (\d+(\.\d+)?)mm, thickness (\d+(\.\d+)?)mm',
            "height": r'height (\d+(\.\d+)?)mm',
            "width": r'width (\d+(\.\d+)?)mm',
            "thickness": r'thickness (\d+(\.\d+)?)mm',
        }

        extracted_dimensions = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, sku_long_description)
            if match:
                dimension_value = match.group(1)
                extracted_dimensions[key] = f"{key} {dimension_value}mm"
        for dimension in extracted_dimensions.values():
            dim_key_value = re.split(r'(\d+\.?\d*)', dimension)
            size_dimensions.append(f'{dim_key_value[0]}: {" ".join(dim_key_value[1:])}')

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode').lower()
            url_countryCode = item.get('url_countryCode')
            if url_countryCode == "/":
                delivery_api = f'https://www.monicavinader.com/locale/info?country={country_code.upper()}'
                country_url = f'{self.base_url}/{url_without_language}?set_country={country_code.upper()}'
            else:
                delivery_api = f'https://www.monicavinader.com{url_countryCode}/locale/info?country={url_countryCode.split("/")[1].upper()}'
                country_url = f'{self.base_url}{url_countryCode}/{url_without_language}?set_country={url_countryCode.split("/")[1].upper()}'
            try:
                session = requests.Session()
                scraper = cloudscraper.create_scraper(browser={'platform': 'windows', 'browser': 'chrome', 'mobile': False}, sess=session)
                delivery_resp = scraper.get(delivery_api, headers=self.headers)
                if delivery_resp.status_code == 200:
                    delivery_data = json.loads(delivery_resp.text)
            except Exception as e:
                print(e)
            try:
                session = requests.Session()
                scraper = cloudscraper.create_scraper(browser={'platform': 'windows', 'browser': 'chrome', 'mobile': False}, sess=session)
                country_resp = scraper.get(country_url, headers=self.headers)
                if country_resp.status_code == 200:
                    specification_info = self.collect_specification_info(country_resp, country_code, delivery_data, country_url)
                    specification[country_code] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
            except Exception as e:
                print(e)

        content['es'] = {
            "sku_link": response.url,
            "sku_title": sku_title,
            "sku_short_description": sku_long_description,
            "sku_long_description": ''
        }
        if image is None:
            list_img = response.css('p.js-main-gallery-image-zoom::attr(data-zoom)').getall()
        else:
            list_img = image
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
        material_ele = response.css("p.product-details__subtitle::text").get() or ''
        if "&" in material_ele:
            main_material = material_ele.split("&")[0].strip()
            secondary_material = material_ele.split("&")[1].strip()
        else:
            main_material = material_ele.strip()
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        domain, domain_url = self.extract_domain_domain_url(response.url)
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = brand
        item['product_badge'] = product_badge
        item['manufacturer'] = self.name
        item['mpn'] = mpn
        item['sku'] = sku_id
        item['gtin13'] = barcode
        item['sku_color'] = ''
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_specification_info(self, response, country_code, delivery_data,url):
        if not isinstance(response, TextResponse):
            response = TextResponse(url=response.url, body=response.text, encoding='utf-8')
        price_currency = ''
        base_price = ''
        availability = ''
        delivery_benefits = ''
        basket_cost = ''
        try:
            basket_cost = delivery_data["payload"]["basketcost"]
            benefits_html = delivery_data["payload"]["delivery"]["benefits"]
            delivery_join = Selector(text=benefits_html).xpath('//ul/li/text()').getall()
            delivery_benefits = ''.join(delivery_join)
        except Exception as e:
            print(e)

        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        try:
            if script_tag_content:
                json_data = json.loads(script_tag_content)
                price = json_data["offers"].get("price")
                base_price = "{:.2f}".format(float(price))
                price_currency = json_data["offers"].get("priceCurrency")
                availability = json_data["offers"].get("availability")
        except Exception as e:
            print(e)

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock = response.css('.js-stock-messaging.product-details__stock::text').get()
        if out_of_stock:
            out_of_stock_text = out_of_stock.strip()
        else:
            out_of_stock_text = product_availability[1]

        sizes = [size.strip() for size in response.css('div.size-selector__options a.js-change-size::text').getall()]

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": price_currency if price_currency else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": base_price if base_price else 0.0,
            "active_price": base_price if base_price else 0.0,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": delivery_benefits if delivery_benefits else 'NA',
            "shipping_expenses": basket_cost if basket_cost else 0.0,
            # Use a default value, adjust as needed
            "marketplace_retailer_name": 'monicavinader',
            "condition": "NEW",
            "reviews_rating_value": 0.0,  # Use a default value, adjust as needed
            "reviews_number": 0,  # Use a default value, adjust as needed
            "size_available": sizes if sizes else [],
            "sku_link": url,
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

