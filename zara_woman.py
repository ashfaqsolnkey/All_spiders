import scrapy
import nest_asyncio
from bs4 import BeautifulSoup
from scrapy import Request
from urllib.parse import urlencode, urljoin
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class Zara(scrapy.Spider):
    name = "zara_woman"
    all_target_urls = []
    all_products = []
    sku_mapping = {}
    base_url = "https://www.zara.com"
    handle_httpstatus_list = [404, 403, 500, 430, 410, 503]
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

    start_urls = "https://www.zara.com/us/"
    spec_mapping = '[ {"countryCode": "us", "url_countryCode":"us/en","Country_Name":"United States","currencyCode":"USD"},{"countryCode": "es", "url_countryCode":"es/en","Country_Name":"Spain","currencyCode":"EUR"}]'
    # spec_mapping = '[{"countryCode": "eg", "url_countryCode":"eg/en","Country_Name":"Egypt","currencyCode":"EGP"},{"countryCode": "za", "url_countryCode":"za/en","Country_Name":"South Africa","currencyCode":"ZAR"},{"countryCode": "ma", "url_countryCode":"ma/en","Country_Name":"Morocco","currencyCode":"MAD"},{"countryCode": "cn", "url_countryCode":"cn/en","Country_Name":"China","currencyCode":"CNY"},{"countryCode": "hk", "url_countryCode":"hk/en","Country_Name":"Hong Kong","currencyCode":"HKD"},{"countryCode": "sg", "url_countryCode":"sg/en","Country_Name":"Singapore","currencyCode":"SGD"},{"countryCode": "id", "url_countryCode":"id/en","Country_Name":"Indonesia","currencyCode":"IDR"},{"countryCode": "jp", "url_countryCode":"jp/en","Country_Name":"Japan","currencyCode":"JPY"},{"countryCode": "my", "url_countryCode":"my/en","Country_Name":"Malaysia","currencyCode":"MYR"},{"countryCode": "ph", "url_countryCode":"ph/en","Country_Name":"Philippines","currencyCode":"PHP"},{"countryCode": "kr", "url_countryCode":"kr/en","Country_Name":"South Korea","currencyCode":"KRW"},{"countryCode": "tw", "url_countryCode":"tw/en","Country_Name":"Taiwan","currencyCode":"TWD"},{"countryCode": "th", "url_countryCode":"th/en","Country_Name":"Thailand","currencyCode":"THB"},{"countryCode": "vn", "url_countryCode":"vn/en","Country_Name":"Vietnam","currencyCode":"VND"},{"countryCode": "ru", "url_countryCode":"ru/en","Country_Name":"Russia","currencyCode":"RUB"},{"countryCode": "tr", "url_countryCode":"tr/en","Country_Name":"Turkey","currencyCode":"TRY"},{"countryCode": "de", "url_countryCode":"de/en","Country_Name":"Germany","currencyCode":"EUR"},{"countryCode": "it", "url_countryCode":"it/en","Country_Name":"Italy","currencyCode":"EUR"},{"countryCode": "nl", "url_countryCode":"nl/en","Country_Name":"Netherlands","currencyCode":"EUR"},{"countryCode": "no", "url_countryCode":"no/en","Country_Name":"Norway","currencyCode":"NOK"},{"countryCode": "dk", "url_countryCode":"dk/en","Country_Name":"Denmark","currencyCode":"DKK"},{"countryCode": "lu", "url_countryCode":"lu/en","Country_Name":"Poland","currencyCode":"EUR"},{"countryCode": "pt", "url_countryCode":"pt/en","Country_Name":"Portugal","currencyCode":"EUR"},{"countryCode": "es", "url_countryCode":"es/en","Country_Name":"Spain","currencyCode":"EUR"},{"countryCode": "se", "url_countryCode":"se/en","Country_Name":"Sweden","currencyCode":"SEK"},{"countryCode": "ch", "url_countryCode":"ch/en","Country_Name":"Switzerland","currencyCode":"CHF"},{"countryCode": "uk", "url_countryCode":"gb/en","Country_Name":"United Kingdom","currencyCode":"GBP"},{"countryCode": "gr", "url_countryCode":"gr/en","Country_Name":"Greece","currencyCode":"EUR"},{"countryCode": "cz", "url_countryCode":"cz/en","Country_Name":"Czechia","currencyCode":"CZK"},{"countryCode": "fr", "url_countryCode":"fr/en","Country_Name":"France","currencyCode":"EUR"},{"countryCode": "at", "url_countryCode":"at/en","Country_Name":"Austria","currencyCode":"EUR"},{"countryCode": "be", "url_countryCode":"be/en","Country_Name":"Belgium","currencyCode":"EUR"},{"countryCode": "ua", "url_countryCode":"ua/en","Country_Name":"Ukraine","currencyCode":"UAH"},{"countryCode": "il", "url_countryCode":"il/en","Country_Name":"Israel","currencyCode":"ILS"},{"countryCode": "sa", "url_countryCode":"sa/en","Country_Name":"Saudi Arabia","currencyCode":"SAR"},{"countryCode": "ae", "url_countryCode":"ae/en","Country_Name":"United Arab Emirates","currencyCode":"AED"},{"countryCode": "qa", "url_countryCode":"qa/en","Country_Name":"Qatar","currencyCode":"QAR"},{"countryCode": "us", "url_countryCode":"us/en","Country_Name":"United States","currencyCode":"USD"},{"countryCode": "ca", "url_countryCode":"ca/en","Country_Name":"Canada","currencyCode":"CAD"},{"countryCode": "mx", "url_countryCode":"mx/en","Country_Name":"Mexico","currencyCode":"MXN"},{"countryCode": "au", "url_countryCode":"au/en","Country_Name":"Australia","currencyCode":"AUD"},{"countryCode": "nz", "url_countryCode":"nz/en","Country_Name":"New Zealand","currencyCode":"NZD"},{"countryCode": "br", "url_countryCode":"br/en","Country_Name":"Brazil","currencyCode":"BRL"},{"countryCode": "cl", "url_countryCode":"cl/en","Country_Name":"Chile","currencyCode":"CLP"},{"countryCode": "co", "url_countryCode":"co/en","Country_Name":"Colombia","currencyCode":"COP"},{"countryCode": "ec", "url_countryCode":"ec/en","Country_Name":"Ecuador","currencyCode":"USD"},{"countryCode": "ar", "url_countryCode":"ar/en","Country_Name":"Argentina","currencyCode":"ARS"},{"countryCode": "pe", "url_countryCode":"pe/en","Country_Name":"Peru","currencyCode":"PEN"},{"countryCode": "uy", "url_countryCode":"uy/en","Country_Name":"Uruguay","currencyCode":"UYU"},{"countryCode": "ve", "url_countryCode":"ve/en","Country_Name":"Venezuela","currencyCode":"VEF"}]'

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
    nest_asyncio.apply()

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
            meta={
                'dont_redirect': True,
                'handle_httpstatus_list': [301, 302]
            },
            headers=self.headers,
        )

    @inline_requests
    def country_base_url(self, response):
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            url_country_code = item.get('countryCode')
            url = f'{self.base_url}/{url_country_code}/'
            req = yield Request(url, headers=self.headers, dont_filter=True)
            self.get_target_urls(req, url)

        target_urls_list = list(set(self.all_target_urls))
        for link in target_urls_list:
            cat_group_id = ''
            request = scrapy.Request(link, headers=self.headers, dont_filter=True)
            resp = yield request
            if resp.status == 200:
                all_script_tags = resp.css('script').getall()
                for script_tag in all_script_tags:
                    if 'zara.enhancements = {};zara.analyticsData' in script_tag:
                        json_data_str = script_tag.split('zara.analyticsData = ')[1].split(';</script>')[0].rstrip(';')
                        json_data = json.loads(json_data_str)
                        cat_group_id = json_data.get('catGroupId')
                        self.log(f'catGroupId: {cat_group_id}')
                        break
            if cat_group_id:
                country_code = link.split('.com/')[1].split('/')[0]
                product_api = f'category/{cat_group_id}/products?ajax=true'
                product_json_api = f'https://www.zara.com/{country_code}/en/{product_api}'
                api_request = scrapy.Request(product_json_api, headers=self.headers, dont_filter=True)
                api_resp = yield api_request
                if api_resp.status == 200:
                    self.parse(api_resp, link, cat_group_id, country_code)
            else:
                self.log(f"Received Response for URL: {resp.status}")

        logging.info(f'Total Sku of Zara : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            link = product_url
            url = response.urljoin(link)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': url, 'sku': sku_id}
            )

    def parse(self, product_resp, base_url, cat_group_id, country_code):
        if cat_group_id:
            try:
                data = product_resp.json()
                products = data.get("productGroups", [{}])[0].get("elements", [])
                for product in products:
                    for component in product.get("commercialComponents", []):
                        seo = component.get("seo", {})
                        if all(k in seo for k in ["keyword", "seoProductId", "discernProductId"]):
                            product_url = urljoin(
                                base_url,
                                f"/{country_code}/en/{seo['keyword']}-p{seo['seoProductId']}.html"
                                f"?v1={seo['discernProductId']}&v2={cat_group_id}"
                            )
                            self.get_all_sku_mapping(product_url, seo["seoProductId"])
            except Exception as e:
                self.log(f"Error next_page: {e}")

    def get_target_urls(self, response, base_url):
        target_url = response.css('ul.layout-categories-category__subcategory.layout-categories-category__subcategory--hidden>li>a::attr(href)').getall()
        match_keyword = ["mkt1401", "mkt1000", "mkt2005", "mkt1399", "mkt6612", "mkt1484", "home-mkt2085" , "mkt6615", "mkt1050", "babygirl-l87", "kids-babyboy-l5", "stores-st1404", "mkt534","info-l1397", "mkt6899", "mkt5167", "mkt3042", "l7531", "kids-newborn-l474"]
        for link in target_url:
            if any(keyword in link for keyword in match_keyword):
                continue
            if "woman" in link or "mujer" in link:
                absolute_url = urljoin(base_url, link)
                if absolute_url not in self.all_target_urls:
                    self.all_target_urls.append(absolute_url)

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
        if response.status == 200:
            url_split = product_url.split("/")
            url_without_language = "/".join(url_split[5:])
            content = {}
            specification = {}
            main_material = ""
            converted_tags = []
            all_script_tags = response.css('script').getall()
            for script_tag in all_script_tags:
                if "window.zara.appConfig = {" in script_tag:
                    script_tag_content = script_tag.strip().split("window.zara.viewPayload =")[1]
                    tag_content = script_tag_content.split("};</script>")[0] + "}"
                    json_data = json.loads(tag_content)
                    categorys = json_data["category"]['seo']['keyWordI18n']
                    language_tags = [category['languageTag'].replace('-', '/') for category in categorys]
                    converted_tags = ["/".join(tag.split("/")[::-1]).lower() for tag in language_tags]
                    if "detailedComposition" in json_data:
                        products = json_data["product"]["detail"]["detailedComposition"]["parts"]
                        for product in products:
                            components = product['components']
                            if components:
                                main_material = ", ".join(
                                    [f"{component['material']} {component['percentage']}" for component in components])
                                break
                            else:
                                areas = product['areas'][0]['components']
                                main_material = ", ".join(
                                    [f"{area['material']} {area['percentage']}" for area in areas])
                                break
                    break
            languages = ["us/en", "es/es", "fr/fr", "jp/ja", "sa/ar", "pl/pl", "sk/sk", "uz/uz", "bg/bg", "fi/fi",
                         "hr/hr", "id/id", "it/it", "lv/lv", "lt/lt", "mk/mk", "nl/nl", "no/no", "si/si", "kr/ko",
                         "uz/ru"]
            special_headers = {
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

            filtered_tags = [tag for tag in converted_tags if tag in languages]
            for language in filtered_tags:
                lang = language.split('/')[1]
                logging.info(f'Processing: {language}')
                url = f"{self.base_url}/{language}/{url_without_language}"
                req = Request(url, headers=special_headers, dont_filter=True)
                language_resp = yield req
                if language_resp.status == 200:
                    content_info = self.collect_content_information(language_resp, url)
                    if content_info:
                        content[lang] = {
                                "sku_link": content_info["sku_link"],
                                "sku_title": content_info["sku_title"],
                                "sku_short_description": content_info["sku_short_description"],
                                "sku_long_description": content_info["sku_long_description"]
                            }

                elif language_resp.status in [301, 302]:
                    redirected_url = language_resp.headers.get('Location').decode('utf-8')
                    url = language_resp.urljoin(redirected_url)
                    req = Request(url, headers=special_headers, dont_filter=True)
                    redirected_response = yield req
                    if redirected_response.status == 200:
                        content_info = self.collect_content_information(redirected_response, url)
                        content[lang] = {
                            "sku_link": content_info["sku_link"],
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["sku_short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
                else:
                    self.log(f"Received {language_resp.status} Response for URL: {req.url}")
            try:
                json_data = json.loads(self.spec_mapping)
                for item in json_data:
                    components = ''
                    country_code = item.get('countryCode').lower()
                    url_country_code = item.get('url_countryCode')
                    shipping_api = f"https://www.zara.com/{url_country_code}/product/Wear/delivery-return-conditions?ajax=true"
                    shipping_req = scrapy.Request(shipping_api, headers=special_headers, dont_filter=True)
                    shipping_resp = yield shipping_req
                    if shipping_resp.status == 200:
                        data = shipping_resp.json()
                        components = data['content']['components']

                    country_url = f'{self.base_url}/{url_country_code}/{url_without_language}'
                    country_req = scrapy.Request(country_url, headers=special_headers, dont_filter=True)
                    country_resp = yield country_req
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, country_code,
                                                                             url_country_code, components)
                        specification[country_code] = specification_info
                    elif country_resp.status in [301, 302]:
                        redirected_url = country_resp.headers.get(b'Location').decode('utf-8')
                        url = country_resp.urljoin(redirected_url)
                        req = scrapy.Request(url, headers=special_headers, dont_filter=True)
                        country_response = yield req
                        if country_response.status == 200:
                            specification_info = self.collect_specification_info(country_response, country_code,
                                                                                 url_country_code, components)
                            specification[country_code] = specification_info
                    else:
                        self.log(f'Received {country_resp.status} Response for URL: {country_url}')

            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON in specification_info: {e}')

            list_img = []
            list_img_without_http = response.css('.media__wrapper source[sizes="38vw"]::attr(srcset)').getall()
            for images in list_img_without_http:
                img_src = images.split(",")
                for pic in img_src:
                    if 'w=2048' in pic:
                        list_img.append(pic)

            is_production = get_project_settings().get("IS_PRODUCTION")
            product_images_info = []
            if is_production:
                product_images_info = upload_images_to_azure_blob_storage(self, list_img)
            else:
                if list_img:
                    directory = self.directory + sku
                    for url_pic in list_img:
                        trial_image = 0
                        while trial_image < 10:
                            try:
                                headers_image = {
                                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                                    'accept-language': 'en-GB,en;q=0.9',
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

                                res = Request(url_pic, headers=headers_image, dont_filter=True)
                                res = yield res
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
            domain, domain_url = self.extract_domain_domain_url(response.url)
            time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            size_dimension = []
            color = ""
            color_model = response.css(".product-detail-info>p::text").get()
            if color_model:
                color = color_model.split("|")[0]
            else:
                color_model = response.css(".product-detail-color-selector>p::text").get()
                if color_model:
                    color = color_model.split("|")[0]

            gender = ''
            all_script_tags = response.css('script').getall()
            for script_tag in all_script_tags:
                if 'zara.enhancements = {};zara.analyticsData' in script_tag:
                    json_data_str = script_tag.split('zara.analyticsData = ')[1].split(';</script>')[0].rstrip(';')
                    json_data = json.loads(json_data_str)
                    section = json_data.get('section')
                    if "WOMAN" in section:
                        gender = "woman"
                    elif "KID" in section:
                        gender = "kids"
                    elif "MAN" in section:
                        gender = "man"
                    else:
                        gender = "woman"
                    break
            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['collection_name'] = ""
            item['brand'] = "zara"
            item['manufacturer'] = self.name
            item['product_badge'] = ""
            item['gender'] = gender
            item['sku'] = sku
            item['mpn'] = sku
            item['sku_color'] = color
            item['main_material'] = main_material
            item['secondary_material'] = ""
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimension
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response, sku_link):
        sku_title = ''
        sku_long_description = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        if script_tag_content:
            for content in script_tag_content:
                try:
                    json_data = json.loads(content)
                    if isinstance(json_data, dict):
                        if "description" in json_data:
                            sku_title = json_data['name']
                            sku_long_description = json_data['description']
                    elif isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict) and "description" in item:
                                sku_title = item['name']
                                sku_long_description = item['description']
                except Exception as e:
                    print("Error in collect_content_information:", e)

        soup = BeautifulSoup(sku_long_description, "html.parser")
        sku_long_description = soup.get_text()
        return {
            "sku_link": sku_link,
            "sku_title": sku_title,
            "sku_short_description": sku_long_description,
            "sku_long_description": sku_long_description
        }


    def collect_specification_info(self, resp, country_code, url_country_code, components):
        availability = ''
        split_url = ''
        json_price = ''
        currency = ''
        specification_url = resp.url
        if specification_url:
            split_url = specification_url.split('&')[0]

        size_available = []
        size_selector = resp.css('li.size-selector-sizes-size--enabled')
        for size_select in size_selector:
            size_status = size_select.css('button::attr(data-qa-action)').get()
            if "size-out-of-stock" in size_status:
                continue
            else:
                size_availability = size_select.css('div.size-selector-sizes-size__label::text').get()
                size_available.append(size_availability)
        script_tag_content = resp.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            specification = json_data[0]
            json_price = specification["offers"].get("price")
            currency = specification["offers"].get("priceCurrency")
            availability = specification["offers"].get("availability")

        sale_price = self.extract_price_info(json_price)
        price = resp.css('.product-detail-view__side-bar span.price__amount-old span::text').get()
        price_str = resp.css('.money-amount.price-formatted__price-amount>span::text').get()

        if price:
            base_price = self.extract_price_info(price)
        elif price_str:
            base_price = self.extract_price_info(price_str)
        else:
            base_price = sale_price
        if availability:
            product_availability = self.check_product_availability(availability)
        elif len(size_available) > 0:
            product_availability = self.check_product_availability('instock')
        else:
            product_availability = self.check_product_availability('Out of stock')
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]
        list_of_shipping = []
        shipping_lead_time = ''
        for component in components:
            if component['datatype'] == 'bulletList':
                for item in component['items']:
                    if item['datatype'] == 'listItem':
                        shipping_value = item['text']['value']
                        list_of_shipping.append(shipping_value)

        shipping_expenses = ' '.join(list_of_shipping)
        for key in list_of_shipping:
            split_value = key.split(' - ')
            if len(split_value) >= 2:
                shipping_lead_time_joined = split_value[0]
                shipping_lead_time = f'{shipping_lead_time}{shipping_lead_time_joined}.'

        return {
            "lang": country_code,
            "domain_country_code": country_code,
            "currency": currency,
            "base_price": base_price if base_price else sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "zara",
            "condition": "NEW",
            "reviews_rating_value": "NA",
            "reviews_number": "NA",
            "size_available": size_available,
            "sku_link": split_url
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
            elif "limitedavailability" in availability_value or "lowavailability" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Out of stock"
                return "No", out_of_stock_text
        except Exception as e:
            logging.error(f"Error processing in availability: {e}")

