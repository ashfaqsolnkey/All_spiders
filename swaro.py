import scrapy
from urllib.parse import urlencode
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class Swaro(scrapy.Spider):
    name = "swaro"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.swarovski.com"
    handle_httpstatus_list = [404, 403, 500, 430, 503]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)

    directory = get_project_settings().get("FILE_PATH")
    if not os.path.exists(directory):
        os.makedirs(directory)
    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    start_urls = "https://www.swarovski.com/en_GB-GB/"
    # spec_mapping = '[{"countryName" : "Spain" , "codeUrl":"en-ES", "countryCode" :"ES", "currencyCode":"EUR"}, {"countryName" : "United States" , "codeUrl":"en-US", "countryCode" :"US", "currencyCode":"USD" }]'

    spec_mapping = '[{"countryName" : "Spain" , "codeUrl":"en-ES", "countryCode" :"ES", "currencyCode":"EUR"}, {"countryName" : "Canada" ,"codeUrl": "en_GB-CA", "countryCode" :"CA", "currencyCode":"CAD"}, {"countryName" : "United States" , "codeUrl":"en-US", "countryCode" :"US", "currencyCode":"USD" },{"countryName" : "Austria" , "codeUrl":"en-AT" , "countryCode" :"AT", "currencyCode":"EUR"},{"countryName" : "Finland" , "codeUrl":"en-FI" , "countryCode" :"FI", "currencyCode":"EUR"},{"countryName" : "Hungary"  , "codeUrl":"en-HU", "countryCode" :"HU", "currencyCode":"HUF"},{"countryName" : "Netherlands" , "codeUrl":"en-NL", "countryCode" :"NL", "currencyCode":"EUR"}, {"countryName" : "Slovenia" , "codeUrl":"en-SI" , "countryCode" :"SL", "currencyCode":"EUR"},{"countryName" : "United Kingdom" , "codeUrl":"en_GB-GB", "countryCode" :"GB", "currencyCode":"GBP"}, {"countryName" : "Belgium" , "codeUrl":"en-BE", "countryCode" :"BE", "currencyCode":"EUR"}, {"countryName" : "France" , "codeUrl":"en-FR", "countryCode" :"FR", "currencyCode":"EUR"},{"countryName" : "Ireland" , "codeUrl":"en_GB-IE", "countryCode" :"IR", "currencyCode":"EUR"}, {"countryName" : "Poland" , "codeUrl":"en-PL", "countryCode" :"PL", "currencyCode":"PLN"}, {"countryName" : "Czech Republic" , "codeUrl":"en-CZ", "countryCode" :"CZ", "currencyCode":"CZK"},{"countryName" : "Germany" , "codeUrl":"en-DE" , "countryCode" :"DE", "currencyCode":"EUR"},{"countryName" : "Italy" , "codeUrl":"en-IT" , "countryCode" :"IT", "currencyCode":"EUR"},{"countryName" : "Portugal" , "codeUrl":"en-PT", "countryCode" :"PT", "currencyCode":"EUR"},{"countryName" : "Sweden" , "codeUrl":"en-SE", "countryCode" :"SE", "currencyCode":"SEK"},{"countryName" : "Denmark" , "codeUrl":"en-DK" , "countryCode" :"DK", "currencyCode":"DKK"},{"countryName" : "Greece" , "codeUrl":"en-GR" , "countryCode" :"GR", "currencyCode":"EUR"}, {"countryName" : "Luxembourg"  , "codeUrl":"en-LU" , "countryCode" :"LU", "currencyCode":"EUR"}, {"countryName" : "Romania" , "codeUrl":"en-RO", "countryCode" :"RO", "currencyCode":"RON"},{"countryName" : "Switzerland" , "codeUrl":"en-CH" , "countryCode" :"CH", "currencyCode":"CHF"}, {"countryName" : "Australia" , "codeUrl":"en_GB-AU", "countryCode" :"AU", "currencyCode":"AUD"}, {"countryName" : "New Zealand" , "codeUrl":"en_GB-NZ" , "countryCode" :"NZ", "currencyCode":"NZD"}, {"countryName" : "India"  , "codeUrl":"en-IN", "countryCode" :"IN", "currencyCode":"INR"},{"countryName" : "Singapore" , "codeUrl":"en-SG" , "countryCode" :"SG", "currencyCode":"SGD"}, {"countryName" : "Hong Kong" , "codeUrl":"en-HK", "countryCode" :"HK", "currencyCode":"HKD"},{"countryName" : "Japan" , "codeUrl":"en-JP", "countryCode" :"JP", "currencyCode":"JPY"},{"countryName" : "Thailand" , "codeUrl":"en-TH", "countryCode" :"TH", "currencyCode":"THB"},{"countryName" : "Korea Republic of" , "codeUrl":"en-KR", "countryCode" :"KR", "currencyCode":"KRW"},{"countryName" : "Malaysia" , "codeUrl":"en-MY" , "countryCode" :"MY", "currencyCode":"MYR"},{"countryName" : "Taiwan Region" , "codeUrl":"en-TW" , "countryCode" :"TW", "currencyCode":"TWD"},{"countryName" : "South Africa" , "codeUrl":"en_GB-ZA" , "countryCode" :"ZA", "currencyCode":"ZAR"}]'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'DNT': '1',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Priority': 'u=0, i',
        'TE': 'trailers'
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
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            url_country_code = item.get('codeUrl')
            url = f'{self.base_url}/{url_country_code}/'
            req = yield Request(url, headers=self.headers, dont_filter=True)
            self.get_target_urlss(req)

        params = {'page': 9999}
        filtered_urls = list(set(self.all_target_urls))
        for link in filtered_urls:
            url = link + '?sort=relevance&' + urlencode(params)
            request = scrapy.Request(url, headers=self.headers, dont_filter=True)
            link_resp = yield request
            if link_resp.status == 200:
                self.parse(link_resp)
            else:
                self.log(f"Received Response for URL: {link_resp.status}")

        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': url, 'sku': sku_id}
            )

    def get_target_urlss(self, response):
        product_urls = response.css('.swa-main-navigation__menu-item>div>a::attr(href)').getall()
        for link in product_urls:
            if link not in self.all_target_urls:
                url = urljoin(response.url, link)
                self.all_target_urls.append(url)

    def parse(self, response):
        sku_id = ''
        print(f"response url {response.url}")
        product_elements = response.css('div.swa-product-tile-plp-wrapper')
        for product_ele in product_elements:
            product_url = product_ele.css(".swa-product-tile-plp a::attr(href)").get()
            product_tiles = product_ele.css('a[data-gtm-product-id]')
            for tile in product_tiles:
                sku_id = tile.attrib['data-gtm-product-id']
            self.get_all_sku_mapping(product_url, sku_id)

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
    def parse_product(self, response, product_url, sku):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': url, 'sku': sku}
            )
            return
        matched_keywords = ["en_GB-CA", "en-US", "en-AT", "en-FI", "en-HU", "en-NL", "en-SI", "en_GB-GB", "en-BE",
                            "en-FR", "en_GB-IE", "en-PL", "en-ES", "en-CZ", "en-DE", "en-IT", "en-PT", "en-SE", "en-DK",
                            "en-GR", "en-LU", "en-RO", "en-CH", "en_GB-AU", "en_GB-NZ", "en-IN", "en-SG", "en-HK",
                            "en-JP", "en-TH", "en-KR", "zh-CN", "en-MY", "en-TW", "en_GB-ZA"]
        url_parts = ''
        urlwithoutlang = ''
        try:
            for keyword in matched_keywords:
                if keyword in product_url:
                    url_parts = product_url.split(keyword)
            if url_parts:
                urlwithoutlang = url_parts[1]
            else:
                url_parts = product_url.split(".com/")[1]
                urlwithoutlang = "/" + "/".join(url_parts.split('/')[1:])
        except Exception as e:
            print("Error in url_without_lang", e)

        content = {}
        specification = {}

        content_info = self.collect_content_information(response)
        content['en'] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        languages = [ "es-ES", "hu-HU", "de-AT", "pl-PL", "cs-CZ", "it-IT", "pt-PT", "ro-RO", "el-GR", "ja-JP", "th-TH", "ko-KR"]
        for language in languages:
            logging.info(f'Processing: {language}')
            url = f"{self.base_url}/{language}{urlwithoutlang}"
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            language_resp = yield req
            lang = language.split('-')[0]
            f_lang = lang.split("_")[0]
            if language_resp.status == 200:
                content_info = self.collect_content_information(language_resp)
                content[f_lang] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            elif language_resp.status in [301, 302]:
                redirected_url = language_resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                redirected_url_resp = yield req
                if redirected_url_resp.status == 200:
                    content_info = self.collect_content_information(redirected_url_resp)
                    content[f_lang] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            else:
                self.log(f"Received 404 Response for URL: {req.url}")

        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode').lower()
                currency_code = item.get('currencyCode')
                url_country_code = item.get('codeUrl')
                if country_code == 'cn':
                    country_url = f'https://www.swarovski.com.cn/{url_country_code}{urlwithoutlang}'
                else:
                    country_url = f'{self.base_url}/{url_country_code}{urlwithoutlang}'
                country_req = scrapy.Request(country_url, headers=self.headers, dont_filter=True)
                country_resp = yield country_req
                if country_resp.status == 200:
                    specification_info = self.collect_specification_info(country_resp, country_code, currency_code)
                    specification[country_code] = specification_info
                elif country_resp.status in [301, 302]:
                    redirected_url = country_resp.headers.get('Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                    redirected_resp = yield req
                    if redirected_resp.status == 200:
                        specification_info = self.collect_specification_info(redirected_resp, country_code,currency_code)
                        specification[country_code] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return

        list_img = []
        picture_sources = response.css('div.splide__list.splide__thumbnails picture source:last-of-type::attr(srcset)').getall()
        pattern = re.compile(r'^https://.*3x$')
        for pictures in picture_sources:
            pics = re.split(r',\s*(?=https://)', pictures)
            for pic in pics:
                if pattern.match(pic):
                    i_img = pic.split(".jpg")[0].strip()
                    list_img.append(i_img + ".jpg")

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku + "/"
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

        badge = response.css("span.ab-288-label::text").get() or " "
        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        product_details = response.css(
            '.swa-accessible-tab__description-sec .swa-product-details__drawer__specs li')
        key_value_pairs = {}
        for li in product_details:
            text = li.css('::text').get()
            key, value = text.split(':', 1)
            key_value_pairs[key.strip()] = value.strip()
        keys_to_match = ["Length", "Width", "Size","Minimum length","Watch strap length","Opening distance","Case size","Maximum length","Inner diameters","Height"]
        size_dimension = []
        for key in keys_to_match:
            if key in key_value_pairs:
                dimension = f'{key}: {key_value_pairs[key]}'
                size_dimension.append(dimension)

        collection_name = self.find_key(key_value_pairs, "Collection")
        product_color = key_value_pairs.get("Colour") or key_value_pairs.get("Color")
        main_material = key_value_pairs.get("Material")

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_name
        item['brand'] = 'Swarovski'
        item['manufacturer'] = self.name
        item['product_badge'] = badge
        item['sku'] = sku
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def find_key(self, dictionary, key):
        for k in dictionary:
            if key.lower() in k.lower():
                return dictionary[k]
        return None

    def collect_content_information(self, response):
        sku_title = response.css('.swa-product-information__title::text').get()
        sku_short_description = ''
        sku_short_description = response.css(".swa-accessible-tab__description-first::text").get()
        if sku_short_description is None:
            sku_short_description = response.css(".swa-accessible-tab__description-first>p::text").get()
        sku_long_sec = response.css('#product-details-classifications-ellipsis>li::text').getall()
        sku_long_description = f"{sku_short_description} {' '.join(sku_long_sec)}"
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, currency_code):
        availability = ''
        sales_price = ''
        item_url = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    sales_price = json_data['offers'].get("price")
                    currency_code = json_data['offers'].get("priceCurrency")
                    availability = json_data['offers'].get("availability")
                    item_url = json_data.get('url')
                    break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON Offers: {e}")
        sale_price = str(sales_price)
        price_string = resp.css(".swa-product-information__price__original::text").get()
        if price_string is not None:
            base_price = self.extract_price_info(price_string)
        else:
            base_price = sale_price
        size_available = resp.css('.swa-product-size-selector__list>a::text').getall()
        peninsula_list = resp.css('div[role="tabpanel"] p:nth-child(-n+2)::text').getall()
        pen_shipping = peninsula_list[1:3]
        peninsula_shipping = ''.join(item for item in pen_shipping)
        shipping_data = resp.css('div[role="tabpanel"] p:nth-child(-n+2)::text').getall()
        ship_expenses = shipping_data[3:5]
        shipping_expenses = ''.join(item for item in ship_expenses)
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": country_code,
            "domain_country_code": country_code,
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": peninsula_shipping,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": "",
            "reviews_number": "",
            "size_available": size_available,
            "sku_link": item_url
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

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "LimitedAvailability" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Temporarily out of stock"
                return "No", out_of_stock_text
        except Exception as e:
            return "No"



