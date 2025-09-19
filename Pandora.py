import scrapy
import urllib3
from numpy import random
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from PIL import Image
from scrapy.http import Request, TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests, cloudscraper, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers
from itertools import cycle


class Pandora(scrapy.Spider):
    name = "pandora"
    base_url = ".pandora.net"
    target_urls = []
    sku_mapping = {}
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    urllib3.disable_warnings()

    spec_mapping = '[{"country": "United States","countryCode": "US","currencyCode": "USD","codeUrl": "en" , "locale":"en-US"}, {"country": "Spain","countryCode": "ES","currencyCode": "EUR","codeUrl": "es", "locale":"PND-ES"}]'
    # spec_mapping = '[{"country": "France","countryCode": "FR","currencyCode": "EUR","codeUrl": "fr", "locale":"fr-FR"}, {"country": "United States","countryCode": "US","currencyCode": "USD","codeUrl": "en" , "locale":"en-US"},{"country": "Hong Kong","countryCode": "HK","currencyCode": "HKD","codeUrl": "en", "locale": "en-HK"}, {"country": "Singapore","countryCode": "SG","currencyCode": "SGD","codeUrl": "en" , "locale":"en-SG"}, {"country": "Malaysia","countryCode": "MY","currencyCode": "MYR","codeUrl": "en", "locale":"en-MY"}, {"country": "Turkey","countryCode": "TR","currencyCode": "TRY","codeUrl": "tr", "locale":"tr-TR"}, {"country": "Ireland","countryCode": "Ie","currencyCode": "EUR","codeUrl": "en", "locale" :"en-IE"},{"country": "Denmark","countryCode": "DK","currencyCode": "DKK","codeUrl": "da", "locale":"da-DK"},{"country": "Portugal","countryCode": "PT","currencyCode": "EUR","codeUrl": "pt", "locale":"pt-PT"},{"country": "United Kingdom","countryCode": "UK","currencyCode": "GBP","codeUrl": "en","locale":"en-GB"}, {"country": "UAE","countryCode": "AE","currencyCode": "AED","codeUrl": "en","locale":"en-AE"}, {"country": "Canada","countryCode": "CA","currencyCode": "CAD","codeUrl": "en", "locale" :"en-CA"}, {"country": "Australia","countryCode": "AU","currencyCode": "AUD","codeUrl": "en", "locale":"en-AU"}, {"country": "New Zealand","countryCode": "NZ","currencyCode": "NZD","codeUrl": "en","locale":"en-NZ"}, {"country": "Japan","countryCode": "JP","currencyCode": "JPY","codeUrl": "ja", "locale" :"ja-JP"}, {"country": "Netherlands","countryCode": "NL","currencyCode": "EUR","codeUrl": "nl", "locale" :"nl-NL"}, {"country": "Spain","countryCode": "ES","currencyCode": "EUR","codeUrl": "es", "locale":"PND-ES"},{"country": "Czech Republic","countryCode": "CZ","currencyCode": "CZK","codeUrl": "cs", "locale":"cs-CZ"}]'
    firefox_user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0"
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0"
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0"
    ]

    random_user_agent = random.choice(firefox_user_agents)
    headers = {
        "User-Agent": random_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1"
    }

    RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 429, 408, 403]
    handle_httpstatus_list = [430, 500, 403, 404,  301, 302]
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
    start_urls = "https://us.pandora.net/"

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
        url = ''
        for item in json_data:
            try:
                country_code = item.get('countryCode').lower()
                language_code = item.get('codeUrl').lower()
                url_country_code = country_code
                url = f'https://{url_country_code}{self.base_url}/{language_code}'
                country_request = scrapy.Request(url, headers=self.headers, dont_filter=True)
                target_response = yield country_request
                if target_response.status == 200:
                    self.get_target_urls(target_response,url)
                elif target_response.status in [301, 302]:
                    target_retry_url = target_response.headers.get(b'location').decode('utf-8')
                    target_response_retry_url = target_response.urljoin(target_retry_url)
                    target_retry_req = scrapy.Request(target_response_retry_url, headers=self.headers,
                                                       dont_filter=True)
                    target_retry_resp = yield target_retry_req
                    self.get_target_urls(target_retry_resp,url)
                else:
                    self.log(f"Received Response for URL: {target_response.status}")
            except Exception as e:
                logging.error(f"Error scraping URL: {url}. Error: {e}")

        for link in self.all_target_urls:
            if link:
                try:
                    url = response.urljoin(link)
                    req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                    product_response = yield req
                    if product_response.status == 200:
                        self.parse(product_response, url)
                    else:
                        self.log(f"Received Response for URL: {product_response.status}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {link}: {e}")

        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id}
            )

    def get_target_urls(self, response, target_base_url):
        target_urls = response.css('a.chakra-link::attr(href)').getall()
        target_urls_list = list(set(target_urls))
        for link in target_urls_list:
            absolute_url = urljoin(target_base_url, link)
            if absolute_url not in self.all_target_urls:
                if 'baby-and-christening' not in absolute_url and 'login' not in absolute_url and 'stores' not in absolute_url and 'gift-sets' not in absolute_url:
                    self.all_target_urls.append(absolute_url)

    def parse(self, response, parse_base_url):
        product_urls = response.css('div.css-rklm6r')
        for product_element in product_urls:
            product_url = product_element.css('a.chakra-link.css-7pyjxw::attr(href)').get()
            sku_id = product_element.css('a.chakra-link.css-7pyjxw::attr(data-pid)').get()
            absolute_url = urljoin(parse_base_url, product_url)
            self.get_all_sku_mapping(absolute_url, sku_id)

        next_page = response.xpath('//button[@class="btn btn-outline-primary more"]/@data-url').get()
        if next_page:
            retry = 1
            while retry <= 5:
                try:
                    proxy = next(self.proxy_cycle)
                    # session = requests.session()
                    scrapper = cloudscraper.create_scraper(
                        browser={"browser": "chrome", "platform": "windows", "mobile": False}
                    )
                    next_page_resp = scrapper.get(next_page, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                    print(next_page_resp.status_code)
                    if next_page_resp.status_code == 200:
                        product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                        self.parse(product_response, next_page)
                        break
                    elif next_page_resp.status_code == 403:
                        time.sleep(4)
                        retry += 1
                        print('Retrying with count :- ' + str(retry))

                except Exception as e:
                    time.sleep(4)
                    retry += 1
                    self.log(f"Error next_page: {e}")
                    logging.info("ERROR-1: " + str(e))
                    print('Retrying with count :- ' + str(retry))

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
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get(b'Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id}
            )
            return
        url_parts = response.url.split(".net/")[1]
        if url_parts.startswith('products'):
            url_without_lang = url_parts.split('/', 1)[1]
        else:
            url_without_lang = "/".join(url_parts.split('/')[1:])
        content = {}
        specification = {}
        list_img = []
        brand = ''
        mpn = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            json_data = json.loads(script_content)
            try:
                if 'mpn' in json_data:
                    mpn = json_data.get("mpn")
                    brand = json_data["brand"].get("name")
                    break
            except json.JSONDecodeError as e:
                self.log(f"Error decoding JSON Images: {e}")

        language_mapping = '[{"language_countryCode": "us","language": "en"}, {"language_countryCode": "it","language": "it"},{"language_countryCode": "dk","language": "da"},{"language_countryCode": "pt","language": "pt"},{"language_countryCode": "fr","language": "fr"},{"language_countryCode": "cn","language": "zh"},{"language_countryCode": "jp","language": "ja"},{"language_countryCode": "nl","language": "nl"},{"language_countryCode": "no","language": "nb"},{"language_countryCode": "de","language": "de"},{"language_countryCode": "es","language": "es"},{"language_countryCode": "se","language": "sv"},{"language_countryCode": "gr","language": "el"},{"language_countryCode": "cz","language": "on"},{"language_countryCode": "pl","language": "pl"}]'
        json_data = json.loads(language_mapping)
        for item in json_data:
            url_country_code = item["language_countryCode"]
            language = item["language"]
            url = f"https://{url_country_code}{self.base_url}/{language}/{url_without_lang}"
            req = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(resp)
                if content_info:
                    content[language] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }

            elif resp.status == 301:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                content_info = self.collect_content_information(resp)
                if content_info:
                    content[language] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
                else:
                    self.log(f"Received 404 Response for URL: {req.url}")

            else:
                self.log(f"Received 404 Response for URL: {resp.url}")

        reviews_number = ''
        reviews_rating_value = ''
        try:
            review_api = f"https://api.bazaarvoice.com/data/display/0.2alpha/product/summary?PassKey=ua8wlktbp7dm9rbxu245ixjlt&productid={sku_id}&contentType=reviews,questions&reviewDistribution=primaryRating,recommended&rev=0&contentlocale=en_IE,en_GB,en_US,en_CA,fr_CA,fr_FR,it_IT,de_DE,nl_NL,da_DK,sv_SE,pl_PL,en_AU,en_NZ,es_ES&incentivizedStats=true"
            try:
                req = scrapy.Request(review_api, headers=self.headers, dont_filter=True)
                review_response = yield req
                if review_response.status != 403:
                    data = review_response.json()
                    try:
                        review_summary = data.get('reviewSummary')
                        if review_summary:
                            reviews_number = review_summary.get('numReviews')
                            reviews_rating = review_summary.get('primaryRating', {}).get('average')
                            reviews_rating_value = reviews_rating
                    except Exception as e:
                        self.log(e)
                else:
                    self.log(f"No review summary found in the response: {review_api}")

            except Exception as e:
                self.log(f"Error: {e}")

            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode').lower()
                locale = item.get("locale")
                currency_code = item.get('currencyCode')
                language_code = item.get('codeUrl').lower()
                url_country_code = country_code
                url = f'https://{url_country_code}{self.base_url}/{language_code}/{url_without_lang}'
                specification_resp = yield Request(url, headers=self.headers, dont_filter=True)
                if specification_resp.status == 200:
                    specification_info = self.collect_specification_info(specification_resp, country_code, currency_code,
                                                                         reviews_rating_value, reviews_number,
                                                                         sku_id,
                                                                         locale, url)
                    if specification_info:
                        specification[country_code] = specification_info
                    else:
                        self.log(f"Received {specification_resp.status} Response for URL: {specification_resp.url}")
                elif specification_resp.status in [301, 302]:
                    specification_retry_url = specification_resp.headers.get(b'location').decode('utf-8')
                    specification_response_retry_url = specification_resp.urljoin(specification_retry_url)
                    specification_retry_req = scrapy.Request(specification_response_retry_url, headers=self.headers,
                                                      dont_filter=True)
                    specification_url_resp = yield specification_retry_req
                    specification_info = self.collect_specification_info(specification_url_resp, country_code, currency_code,
                                                                         reviews_rating_value, reviews_number,
                                                                         sku_id,
                                                                         locale, specification_retry_url)
                    if specification_info:
                        specification[country_code] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {specification_resp.url}")

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return
        attributes = {}
        material = ''
        collection_value = ''
        color_value = ''
        size_dimensions = []
        main_material = ''
        raw_data = response.css('span.datalayer-view-event::attr(data-tealium-view)').get()
        json_data = json.loads(raw_data)
        products = json_data[0].get("products", [])
        for product in products:
            main_material = product.get("metal", "").strip()
            collection_value = product.get("collection", "").strip()
            material = product.get("material", "").strip()
            if material.lower() in ['no other material', 'sin ningún otro material']:
                material = ''
            break

        color_value = response.css('a.color-variant-link.selected::attr(data-product-color-group)').get()
        if not color_value:
            color_value = response.css('a.metal-swatch.selected::attr(data-product-metal-group)').get()

        details = response.css('div.product-attributes-text > p.product-attributes-title::text').getall()
        for detail in details:
            if detail.strip() == 'Dimensions' or detail.strip() == 'Dimensiones':
                mm_values = response.css(
                    'div.product-attributes-text > p.product-attributes-description::text').getall()
                size_dimensions = [val.strip() for val in mm_values if 'mm' in val]
                break

        image_sources = response.css('img.js-product-image::attr(data-img)').getall()
        for image in image_sources:
            json_data = json.loads(image)
            hires_url = json_data.get('hires')
            desired_part = urljoin(product_url, hires_url)
            list_img.append(desired_part)

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(self, list_img)
        else:
            if list_img:
                directory = self.directory + sku_id + "/"
                for url_img in list_img:
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
                        image_info = os.path.join(directory, filename)
                        product_images_info.append(image_info)

                    except Exception as e:
                        logging.error(f"Error processing image: {e}")

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_value
        item['brand'] = brand
        item['mpn'] = mpn
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['main_material'] = main_material
        item['secondary_material'] = material
        item['sku_color'] = color_value
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['specification'] = specification
        item['content'] = content
        yield item

    def collect_content_information(self, response):
        sku_title = ''
        sku_short_description = ''
        dimension_pairs_text = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            json_data = json.loads(script_content)
            if 'description' in json_data:
                sku_title = json_data['name']
                sku_short_description = json_data['description']
                break
        if not sku_title:
            return

        dimension_pairs = {}
        dimension_items = response.css('.product-attributes .attribute-value .attribute-dimension')
        for item in dimension_items:
            key = item.css('.attribute-dimension::text').get(default='').strip()
            value = item.xpath('normalize-space(following-sibling::text()[1])').get()
            dimension_pairs[key] = value
        if dimension_pairs:
            dimension_pairs_text = ' '.join([f"{key}: {value}" for key, value in dimension_pairs.items()])

        description_text = [text.strip() for text in
                            response.css('span.attribute-label::text, span.attribute-value-item::text').getall()]
        descriptions_text = ' '.join(text.strip() for text in description_text).strip()
        sku_long_description = sku_short_description + descriptions_text + dimension_pairs_text if sku_short_description else descriptions_text
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, currency_code, reviews_rating_value, reviews_number,
                                   sku_id, locale, productUrl):
        r_locale = ''
        if locale == 'PND-ES':
            r_locale = 'es_ES'
        elif locale == "en-IE":
            locale = "ga-IE"
            r_locale = 'en-IE'
        else:
            r_locale = locale.replace("-", "_")

        sales_price = ""
        availability = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            json_data = json.loads(script_content)
            if 'offers' in json_data:
                sales_price = json_data["offers"].get('price')
                currency_code = json_data["offers"].get('priceCurrency')
                availability = json_data["offers"].get("availability")
                break
        if sales_price == "":
            return
        base_price = resp.css('span.strike-through.list > span.value::attr(content)').get() or sales_price

        shipping_expenses = resp.xpath('//*[@id="shipping-returns"]/div/div[1]/div[2]/p[1]/text()[1]').get(
            default='').strip()
        shipping_lead_time = resp.xpath('//*[@id="shipping-returns"]/div/div[1]/div[2]/p[1]/text()[2]').get(
            default='').strip()
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]
        sizes = resp.css('.col-12>.size-container>.size-attributes.selectable> button::text').getall()
        unique_sizes = set(size.strip() for size in sizes)
        unique_sizes_list = list(unique_sizes)
        total_stock_quantity = ''
        retry_count = 3
        headers = {
            'Cookie': f'__cf_bm=V86wufVOeEqxevRhTAL83K3my.fzsuUUx1cHHslLtPE-1716618220-1.0.1.1-goYcVVujyh6A9Rjt2t19hmfqaWstfeji7u9_zqP8NRIN7kU3NyMoKG01oYnV3JoEh3KdT5HOvjWtQCDsNxiVPA; __cq_dnt=0; _cfuvid=6lSmTAd7hUEMQgMh8QedZcJSx.9oRVMxej4xtwkJ33E-1716618220924-0.0.1.1-604800000; cqcid=abxMNC7bUF3C1ng6o0O0PYAPOS; cquid=||; dw_dnt=0; dwac_888e3c8bea85b5d3da431371a2=R8xgfK6qPl1YPj19eIIWk9mNFQQXGS2aFk8%3D|dw-only|||{currency_code.upper()}|false|Europe%2FLondon|true; dwanonymous_544105000ecfeb2b55a2de2e32b439d5=abxMNC7bUF3C1ng6o0O0PYAPOS; dwsid=7l9xAyn7HQxLaooNZZYa_nAeBHuQSA7LBRs_8RSS3oaG_9ZSKSKwaUfJdC-7naxgv5-cN9iIAcedTqsgFk-Hlw==; sid=R8xgfK6qPl1YPj19eIIWk9mNFQQXGS2aFk8'
        }
        check_stock_availability = f"https://{country_code}.pandora.net/on/demandware.store/Sites-{locale}-Site/{r_locale}/Product-Variation?pid={sku_id}"
        proxy = next(self.proxy_cycle)
        scraper = cloudscraper.create_scraper()
        res = scraper.get(check_stock_availability, headers=headers, proxies={'http': proxy, 'https': proxy})
        try:
            if res.status_code == 200:
                total_stock_quantity = self.get_ats_count(res)
            elif res.status_code == 403 and retry_count > 0:
                retry_count -= 1
                total_stock_quantity = self.get_ats_count(res)
            elif res.status_code in [301, 302]:
                proxy = next(self.proxy_cycle)
                new_location = res.headers['Location']
                res = cloudscraper.create_scraper().get(new_location, headers=self.headers
                                                        , proxies={'http': proxy, 'https': proxy})
                if res.status_code == 200:
                    total_stock_quantity = self.get_ats_count(res)
            else:
                print(f"Received 404 in ATS Response ")
        except Exception as e:
            print(e)

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": sales_price if sales_price else base_price,
            "active_price": sales_price if sales_price else base_price,
            "stock_quantity": total_stock_quantity if total_stock_quantity else 'NA',
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            # Use a default value, adjust as needed
            "marketplace_retailer_name": 'pandora',
            "condition": "NEW",
            "reviews_rating_value": reviews_rating_value,  # Use a default value, adjust as needed
            "reviews_number": reviews_number,  # Use a default value, adjust as needed
            "size_available": unique_sizes_list if unique_sizes_list else [],
            "sku_link": productUrl if resp.url else 'NA',
        }

    def get_ats_count(self, res):
        total_stock_quantity = ''
        try:
            data = res.json()
            str_Data = json.dumps(data)
            if "ATS" in str_Data:
                stock_quantity = data['product']['availability']['ATS']
                total_stock_quantity = stock_quantity
            else:
                parsed_data = data
                urls = [value['url'] for value in parsed_data['product']['variationAttributes'][0]['values']]

                total_stock_quantity = 0
                for url in urls:
                    proxy = next(self.proxy_cycle)
                    scraper = cloudscraper.create_scraper()
                    res = scraper.get(url, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                    if res.status_code == 200:
                        try:
                            data = res.json()
                            str_Data = json.dumps(data)
                            if "ATS" in str_Data:
                                stock_value = data['product']['availability']['ATS']
                                total_stock_quantity += stock_value
                        except Exception as e:
                            self.log(f"Received Response for : {e}")
        except Exception as e:
            self.log(f"Received Response for : {e}")
        return total_stock_quantity

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
