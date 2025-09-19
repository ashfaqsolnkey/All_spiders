import aiohttp
import asyncio
import scrapy
import os.path
from scrapy import FormRequest
from inline_requests import inline_requests
from parsel import Selector
from scrapy.http import Request, TextResponse
from scrapy.utils.project import get_project_settings
from itertools import cycle
from urllib.parse import urlencode, urlparse, urljoin
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


async def get_page(session, url, proxy_cycle,headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=headers) as resp:
                logging.info(f"Response status for {url} with proxy {proxy} and Response Retry count {retry} timing: {resp.status}")
                resp.raise_for_status()
                return await resp.text()
        except aiohttp.ClientError as e:
            logging.error(f"get_page || Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"get_page || Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1

    return None


async def get_all(session, urls,proxy_cycle, headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle, headers))
        tasks.append(task)
    results = await asyncio.gather(*tasks)
    return [(url, result) for url, result in zip(urls, results)]


async def main(urls, proxy_cycle, headers):
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        data = await get_all(session, urls, proxy_cycle,headers)
        return data


class Guess(scrapy.Spider):
    name = "guess_mens"
    sku_mapping = {}
    # categories_id = ["Guess-Men-NewIn#4d9bbf42-0196-4cd4-96a9-160f6e9c4f15","Guess-Men-Jeans#b29b0e18-d97b-40c1-8faa-d98a5d295227","Guess-Men-Clothing#fd2bdad9-a2d2-4cfb-9608-3c06f086c5d0","Guess-Men-Bags#d15854ed-55f4-4d8a-b687-e7283b5049d9","Guess-Men-ShoesandAccessories#c9f41ec9-3096-40f5-8709-cd4c4d00af6c","Guess-Men-Marciano#b6d928d1-caec-4d25-b546-c8467f395ed7","Guess-Men-MidSeasonSale#53769eed-6726-4392-8f9c-42e7e0751aad","Guess-Men-PastCollections#00cb14a6-775c-4917-94c9-3471d3b2b430"]
    base_url = "https://www.guess.eu"
    handle_httpstatus_list = [430, 403, 404, 410, 301, 302]
    delivery_data = []
    spec_mapping = '[{"countryCode": "es", "url_countryCode": "en-es","delivery_countryCode":"en-ES"}, {"countryCode": "fr", "url_countryCode": "en-fr","delivery_countryCode":"en-FR"}]'
    # spec_mapping = '[{"countryCode": "at", "url_countryCode": "en-at","delivery_countryCode":"en-AT"},{"countryCode": "fr", "url_countryCode": "en-fr","delivery_countryCode":"en-FR"},{"countryCode": "be", "url_countryCode": "en-be","delivery_countryCode":"en-BE"},{"countryCode": "cz", "url_countryCode": "en-cz","delivery_countryCode":"en-CZ"}, {"countryCode": "dk", "url_countryCode": "en-dk","delivery_countryCode":"en-DK"},{"countryCode": "gr", "url_countryCode": "en-gr","delivery_countryCode":"en-GR"},{"countryCode": "ir", "url_countryCode": "en-ie","delivery_countryCode":"en-di"},{"countryCode": "it", "url_countryCode": "en-it","delivery_countryCode":"en-IT"},{"countryCode": "nl", "url_countryCode": "en-nl","delivery_countryCode":"en-NL"},{"countryCode": "no", "url_countryCode": "en-no","delivery_countryCode":"en-NO"},{"countryCode": "lu", "url_countryCode": "en-pl","delivery_countryCode":"en-PL"},{"countryCode": "pt", "url_countryCode": "en-pt","delivery_countryCode":"en-PT"},{"countryCode": "ru", "url_countryCode": "en-ru","delivery_countryCode":"en-RU"},{"countryCode": "es", "url_countryCode": "en-es","delivery_countryCode":"en-ES"},{"countryCode": "se", "url_countryCode": "en-se","delivery_countryCode":"en-SE"},{"countryCode": "ch", "url_countryCode": "en-ch","delivery_countryCode":"en-CH"},{"countryCode": "tr", "url_countryCode": "en-tr","delivery_countryCode":"en-TR"},{"countryCode": "gb", "url_countryCode": "en-gb","delivery_countryCode":"en-GB"}]'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    directory = get_project_settings().get("FILE_PATH")
    delivery_api = "https://www.guess.eu/dw/shop/v20_10/content/eu-needhelp-content?locale=en-ES&client_id=c83b61a8-b468-4e63-94fc-e9647617f9dc"
    if not os.path.exists(directory):
        os.makedirs(directory)

    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    start_urls = "https://www.guess.eu/en-es/home"
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
        yield Request(
            self.delivery_api, callback=self.delivery_call, headers=self.headers
        )
        yield scrapy.Request(
            self.start_urls,
            callback=self.country_base_url,
            headers=self.headers,
        )

    def delivery_call(self, response):
        try:
            delivery_data = json.loads(response.text)
            self.delivery_data = delivery_data["c_body"]
        except:
            self.delivery_data = []

    @inline_requests
    def country_base_url(self, response):
        categories_id = ["Guess-Men-NewIn#4d9bbf42-0196-4cd4-96a9-160f6e9c4f15",
                         "Guess-Men-Jeans#b29b0e18-d97b-40c1-8faa-d98a5d295227",
                         "Guess-Men-Clothing#fd2bdad9-a2d2-4cfb-9608-3c06f086c5d0",
                         "Guess-Men-Bags#d15854ed-55f4-4d8a-b687-e7283b5049d9",
                         "Guess-Men-ShoesandAccessories#c9f41ec9-3096-40f5-8709-cd4c4d00af6c",
                         "Guess-Men-Marciano#b6d928d1-caec-4d25-b546-c8467f395ed7",
                         "Guess-Men-MidSeasonSale#53769eed-6726-4392-8f9c-42e7e0751aad",
                         "Guess-Men-PastCollections#00cb14a6-775c-4917-94c9-3471d3b2b430"]

        for categorie_id in categories_id:
            api_url = 'https://yml5rk21lg-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.24.0)%3B%20Browser%20(lite)%3B%20instantsearch.js%20(4.73.0)%3B%20JS%20Helper%20(3.22.2)&x-algolia-api-key=769a17c8b936f70b64ab0c62f3fdf12e&x-algolia-application-id=YML5RK21LG'
            payload = {
                "requests": [
                    {
                        "indexName": "production__products__en_ES",
                        "params": f'attributesToSnippet=["name:7"]&clickAnalytics=true&distinct=true&enablePersonalization=true&facetFilters=[["categories.id:{categorie_id}"]]&facets=["*"]&filters=categories.id:"{categorie_id}"&hitsPerPage=99999&userToken=anonymous-ce6e9a01-a85f-4828-a7e4-107398667e53'
                    }
                ]
            }
            json_payload = json.dumps(payload)
            req = FormRequest(
                url=api_url,
                method="POST",
                headers=self.headers,
                body=json_payload,
            )
            resp = yield req
            if resp.status == 403:
                self.log(f"Received 403 Response for URL: {resp.url}")
            else:
                self.parse(resp)

        logging.info(f'Total Sku of guess ===========> : {len(self.sku_mapping)}')
        for sku_id, product_info in self.sku_mapping.items():
            product_badge = product_info.get('product_badge')
            product_url = product_info.get('product_url')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'product_badge': product_badge, 'sku_id': sku_id}
            )

    def parse(self, response):
        json_data = json.loads(response.text)
        hits = json_data.get('results')[0].get('hits')
        for hit in hits:
            product_url = hit.get('url')
            sku_id = hit.get('defaultVariantID')
            product_badge = ''
            self.get_all_sku_mapping(product_url, sku_id, product_badge)

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
        product_url_all_language = self.get_language_product_urls(response)
        parsed_url = urlparse(product_url)
        path_components = parsed_url.path.split("/")
        url_without_language = "/".join(path_components[2:])
        content = {}
        specification = {}
        sku_long_description = ''
        list_img = []
        mpn = ''
        gender = ''
        if 'women' in product_url:
            gender = 'women'
        elif 'girl' in product_url:
            gender = 'kids'
        elif 'boy' in product_url:
            gender = 'kids'
        elif 'kids' in product_url:
            gender = 'kids'
        elif 'baby' in product_url:
            gender = 'kids'
        elif 'men' in product_url:
            gender = 'men'
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            mpn = json_data.get("mpn")
            sku_long_description = json_data.get("description")
            image = json_data.get("image")
            for img in image:
                image_replace = img.replace('800', '1900')
                list_img.append(image_replace)

        properties = ["Length", "Width", "Total pendant length", "Thickness", "Size", "Charm", "Diameter dimensions",
                      "Total size", "Total pendant length"]
        size_dimensions = []
        pattern = re.compile(rf"({'|'.join(properties)})\s*:\s*([\d.]+)\s*(?:mm|in)?", re.IGNORECASE)
        matches = pattern.findall(sku_long_description)
        result_dict = {prop: value for prop, value in matches}
        for prop, value in result_dict.items():
            size_dimensions.append(f"{prop}: {value}")

        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": f'{self.base_url}{product_url}',
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        languages = ["es", "fr"]
        # languages = ["es", "fr", "pl", "ru", "de", "nl", "it"]
        for language in languages:
            logging.info(f'Processing: {language}')
            for lang, lang_url in product_url_all_language.items():
                if language == lang:
                    language_url = lang_url
                    req = Request(language_url, headers=self.headers, dont_filter=True)
                    resp = yield req
                    if resp.status == 404:
                        self.log(f"Received 404 Response for URL: {resp.url}")
                    elif resp.status in [301, 302]:
                        redirected_url = resp.headers.get(b'Location').decode('utf-8')
                        url = resp.urljoin(redirected_url)
                        req = Request(url, headers=self.headers, dont_filter=True)
                        resp = yield req
                        content_info = self.collect_content_information(resp)
                        content[language] = {
                            "sku_link": url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
                    else:
                        content_info = self.collect_content_information(resp)
                        content[language] = {
                            "sku_link": language_url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode').lower()
            url_countryCode = item.get("url_countryCode")
            if country_code in "mx":
                url = f'https://www.guess.{country_code}/{url_without_language}'
            else:
                url = f'{self.base_url}/{url_countryCode}/{url_without_language}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = resp.urljoin(redirected_url)
                req = Request(url, headers=self.headers, dont_filter=True)
                country_resp = yield req
                specification_info = self.collect_specification_info(country_resp, country_code)
                base_price = specification_info.get('base_price')
                if base_price:
                    specification[country_code] = specification_info
                else:
                    continue
            else:
                specification_info = self.collect_specification_info(resp, country_code)
                base_price = specification_info.get('base_price')
                if base_price:
                    specification[country_code] = specification_info
                else:
                    continue

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
                            req = Request(url_img, headers=self.headers, dont_filter=True)
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

        product_color = response.css('.attribute__name.text--medium.text--semibold>span::text').get()
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        domain, domain_url = self.extract_domain_domain_url(response.url)
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = 'Guess'
        item['product_badge'] = product_badge
        item['gender'] = gender
        item['manufacturer'] = self.name
        item['mpn'] = mpn
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = ''
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, resp):
        sku_long_description = ''
        sku_title = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            sku_title = json_data.get("name")
            description = json_data.get("description")
            selector = Selector(text=description)
            sku_long_description = selector.xpath('string()').extract_first()

        return {
            "sku_title": sku_title,
            "short_description": sku_long_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, country_code):
        standard_shipping_days, standard_shipping_cost, express_business_days, express_shipping_cost = self.extract_shipping_info(
            country_code.upper())
        shipping_lead_time = "standard_shipping -- " + standard_shipping_days + "\n" + "express_business -- " + express_business_days
        shipping_expenses = "standard_shipping_cost-- " + standard_shipping_cost + "\n" + "express_shipping_cost -- " + express_shipping_cost
        currency_code = ''
        sale_price = ''
        base_price = ''
        availability = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    sale_price = json_data["offers"].get("price")
                    currency_code = json_data["offers"].get("priceCurrency")
                    availability = json_data["offers"].get("availability")
                    break
            except Exception as e:
                print(e)
        price = response.css('.mobile-sticky__closed-content div.price span.price__strike-through-detail span::text').get()
        if price:
            base_price = self.extract_price_info(price)
        sizes = response.css('.js-attribute-btn::attr(data-attr-value)').getall()
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else sale_price,
            "sales_price": sale_price if sale_price else base_price,
            "active_price": sale_price if sale_price else base_price,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            "marketplace_retailer_name": 'guess',
            "condition": "NEW",
            "reviews_rating_value": 0.0,  # Use a default value, adjust as needed
            "reviews_number": 0,  # Use a default value, adjust as needed
            "size_available": sizes,
            "sku_link": response.url if response.url else 'NA',
        }

    def extract_shipping_info(self, country_code):
        data = self.delivery_data
        data_as_string = ''.join(data)
        country_shipping_info = data_as_string.split(f'class="show-in-{country_code}"')
        try:
            if len(country_shipping_info) > 1:
                standard_shipping_days = \
                    country_shipping_info[1].split('data-translation="standard_shipping"></div>')[1].split(
                        '="business_days"></span>')[1].split('<br><span')[0]
                standard_shipping_days = standard_shipping_days.strip() + ' days' if standard_shipping_days else ''

                standard_shipping_cost = \
                    country_shipping_info[1].split('data-translation="standard_shipping"></div>')[1].split(
                        'data-translation="shipping_cost"></span>')[1].split('<span class="free-shipping"')[0]

                express_business_days = \
                    country_shipping_info[1].split('data-translation="express_shipping"></div>')[1].split(
                        '="business_days"></span>')[1].split('<br>')[0]
                express_business_days = express_business_days.strip() + ' days' if express_business_days else ''

                express_shipping_cost = \
                    country_shipping_info[1].split('data-translation="express_shipping"></div>')[1].split(
                        '="shipping_cost"></span>')[1].split('</div>')[0]
            else:
                standard_shipping_days = ''
                standard_shipping_cost = ''
                express_business_days = ''
                express_shipping_cost = ''
        except Exception as e:
            print(f"Error occurred while extracting shipping info: {e}")
            standard_shipping_days = ''
            standard_shipping_cost = ''
            express_business_days = ''
            express_shipping_cost = ''

        return standard_shipping_days, standard_shipping_cost, express_business_days, express_shipping_cost

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "Ver disponibilidad en" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif " veure disponibilitat a botiga" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Temporarily out of stock"
                return "No", availability_value
        except Exception as e:
            return  "No"

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

    def get_language_product_urls(self,response):
        all_links = {}
        lang_split = ''
        urls = response.css('link[rel="alternate"]')
        for link in urls:
            lang_url = link.css('::attr(href)').get()
            name_lang = link.css('::attr(hreflang)').get()
            if name_lang:
                lang_split = name_lang.split('-')[0]

            if lang_split not in all_links:
                all_links[lang_split] = lang_url
        return all_links
