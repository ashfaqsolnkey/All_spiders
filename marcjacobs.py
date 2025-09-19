import scrapy
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper, asyncio, aiohttp
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
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


async def get_page(session, url, proxy_cycle):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=headers, timeout=320) as response:
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
        task = asyncio.create_task(get_page(session, url, proxy_cycle))
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
            continue
        except aiohttp.client.ClientConnectionError:
            error_msg = 'ClientConnectionError'
            print(error_msg)
            continue


class marcjacobs(scrapy.Spider):
    name = "marcjacobs"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.marcjacobs.com"
    handle_httpstatus_list = [404, 403, 500, 430]
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

    start_urls = "https://www.marcjacobs.com/"
    spec_mapping = '[{"countryName": "au", "country_code": "au-en", "codeUrl": "en_AU"},{"countryName": "us", "country_code": "us-en", "codeUrl": "en_US"},{"countryName": "uk", "country_code": "gb-en", "codeUrl": "en_GB"},{"countryName": "es", "country_code": "es-es", "codeUrl": "en_ES"}, {"countryName": "ae", "country_code": "ae-en", "codeUrl": "en_AE"}, {"countryName": "th", "country_code": "th-en", "codeUrl": "en_TH"}, {"countryName": "tw", "country_code": "tw-en", "codeUrl": "en_TW"}, {"countryName": "ch", "country_code": "ch-en", "codeUrl": "en_CH"}, {"countryName": "se", "country_code": "se-en", "codeUrl": "en_SE"}, {"countryName": "si", "country_code": "si-en", "codeUrl": "en_SI"}, {"countryName": "sg", "country_code": "sg-en", "codeUrl": "en_SG"}, {"countryName": "sa", "country_code": "sa-en", "codeUrl": "en_SA"}, {"countryName": "ro", "country_code": "ro-en", "codeUrl": "en_RO"}, {"countryName": "qa", "country_code": "qa-en", "codeUrl": "en_QA"}, {"countryName": "pt", "country_code": "pt-en", "codeUrl": "en_PT"}, {"countryName": "pl", "country_code": "pl-en", "codeUrl": "en_pl"}, {"countryName": "ph", "country_code": "ph-en", "codeUrl": "en_PH"}, {"countryName": "nz", "country_code": "nz-en", "codeUrl": "en_NZ"}, {"countryName": "nl", "country_code": "nl-en", "codeUrl": "en_NL"}, {"countryName": "mx", "country_code": "mx-en", "codeUrl": "en_MX"}, {"countryName": "my", "country_code": "my-en", "codeUrl": "en_MY"}, {"countryName": "lt", "country_code": "lt-en", "codeUrl": "en_LT"}, {"countryName": "jp", "country_code": "jp", "codeUrl": "ja_JP"}, {"countryName": "it", "country_code": "it-en", "codeUrl": "en_IT"}, {"countryName": "il", "country_code": "il-en", "codeUrl": "en_IL"}, {"countryName": "hk", "country_code": "hk-en", "codeUrl": "en_HK"}, {"countryName": "gr", "country_code": "gr-en", "codeUrl": "en_GR"}, {"countryName": "de", "country_code": "de-de", "codeUrl": "en_DE"}, {"countryName": "dk", "country_code": "dk-en", "codeUrl": "en_DK"}, {"countryName": "cn", "country_code": "cn-en", "codeUrl": "en_CN"}, {"countryName": "ca", "country_code": "ca-en", "codeUrl": "en_CA"}, {"countryName": "be", "country_code": "be-en", "codeUrl": "en_BE"}, {"countryName": "at", "country_code": "at-en", "codeUrl": "en_AT"}]'

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url

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
            country_code = item.get('country_code')
            url = f'{self.base_url}/{country_code}/home'
            req = yield Request(url, headers=self.headers, dont_filter=True)
            self.get_target_urls(req)

        filtered_urls = list(set(self.all_target_urls))
        for url in filtered_urls:
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
                cb_kwargs={'product_url': product_url, 'sku': sku_id}
            )

    def get_target_urls(self, response):
        target_urls = response.css('a.lvl2-link::attr(href)').extract()
        try:
            for link in target_urls:
                try:
                    if link not in self.all_target_urls:
                        url = urljoin(response.url, link)
                        self.all_target_urls.append(url)
                except Exception as e:
                    print(f"Error processing URL {link}: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def parse(self, response):
        products = response.css(".prod-l-g.js-cat-prod-grid>div>div.p-tile")
        if products:
            for item in products:
                try:
                    product = item.css("div.tile-info>a::attr(href)").get()
                    proxy = next(self.proxy_cycle)
                    url = f"{self.base_url}{product}"
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(url, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                    if resp.status_code == 200:
                        url_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                        sku_id = url_response.css('span.nosto_sku>span.id::text').get()
                        self.get_all_sku_mapping(url, sku_id)
                    else:
                        print(f"No product in parse {response} ")
                except Exception as e:
                    self.log(f"Error occured parse fn{e}")

        next_page_link = response.css('.show-more-tiles::attr(data-url)').get()
        if next_page_link:
            try:
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_link], self.proxy_cycle, headers))

                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_link, body=result, encoding='utf-8')
                        self.parse(product_response)
            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")

    def get_all_sku_mapping(self, product_url, sku_id):
        if "en/" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "en/" not in existing_url:
                self.sku_mapping[sku_id] = product_url
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url
        elif "en/" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url

    @inline_requests
    def parse_product(self, response, product_url, sku):
        product = product_url.split('/')[-1]
        brand = ''
        size_dimension = []
        main_material = ''
        content = {}
        specification = {}
        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        promotions = response.css("article.swiper-slide div::text").getall()
        promotions = [promo.strip() for promo in promotions if promo.strip()]
        shipping_text = None
        for promo in promotions:
            if "shipping" in promo.lower():
                shipping_text = promo
                break

        lang = '[{"countryName": "es-es", "lang" : "es"}, {"countryName": "cn-zh", "lang" : "zh"}, {"countryName": "fr-fr", "lang" : "fr"}, {"countryName": "de-de", "lang" : "de"}, {"countryName": "ja_JP", "lang" : "jp"}]'
        json_data = json.loads(lang)
        for item in json_data:
            country_code = item.get('countryName')
            language = item.get('lang')
            try:
                if country_code == 'ja_JP':
                    country_url = f"{'https://www.marcjacobs.jp'}/{country_code}/{product}"
                else:
                    country_url = f"{self.base_url}/{country_code}/{product}"

                req = Request(country_url, headers=self.headers, dont_filter=True)
                content_response = yield req
                if content_response.status == 404:
                    self.log(f"Received 404 Response for URL: {content_response.url}")
                elif content_response.status in [301, 302]:
                    try:
                        # redirected_url = content_response.headers.get('Location').decode('utf-8')
                        # url = response.urljoin(redirected_url)
                        content_retry_req = scrapy.Request(country_url, headers=self.headers,dont_filter=True)
                        content_retry_resp = yield content_retry_req
                        content_info = self.collect_content_information(content_retry_resp)
                        if content_info:
                            content[language] = {
                                "sku_link": country_url,
                                "sku_title": content_info["sku_title"],
                                "sku_short_description": content_info["short_description"],
                                "sku_long_description": content_info["sku_long_description"]
                            }
                    except Exception as e:
                        print(e)
                else:
                    content_info = self.collect_content_information(content_response)
                    if content_info:
                        content[language] = {
                            "sku_link": country_url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["sku_short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }

            except Exception as e:
                print(e)

        json_data = json.loads(self.spec_mapping)
        product_id = product_url.split('/')[-1].split('-')[0]
        for item in json_data:
            country_code = item.get('country_code')
            code_url = item.get('codeUrl')
            country_name = item.get('countryName')
            try:
                country_url = f"{self.base_url}/{country_code}/{product}"
                api_url = f'https://www.marcjacobs.com/on/demandware.store/Sites-mjsfra-Site/{code_url}/Product-Variation?&pid={product_id}&local={code_url}'
                proxy = next(self.proxy_cycle)
                session = requests.Session()
                scraper = cloudscraper.create_scraper(browser={'platform': 'windows', 'browser': 'chrome', 'mobile': False}, sess=session)
                country_resp = scraper.get(api_url, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                if country_resp.status_code == 404:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
                elif country_resp.status_code in [301, 302]:
                    try:
                        # redirected_url = country_resp.headers.get('Location').decode('utf-8')
                        # url = response.urljoin(redirected_url)
                        proxy = next(self.proxy_cycle)
                        session = requests.Session()
                        scraper = cloudscraper.create_scraper(
                            browser={'platform': 'windows', 'browser': 'chrome', 'mobile': False}, sess=session)
                        requests_api = scraper.get(api_url, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                        if requests_api.status_code == 200:
                            list_product_response = TextResponse(url='', body=requests_api.text, encoding='utf-8')

                            json_data = list_product_response.json()
                            if not main_material:
                                product_details = json_data['product'].get('custom')
                                main_material = product_details.get('material')
                                productDetailTitle1 = product_details.get('productDetailTitle1')
                                productDetailContent1 = product_details.get('productDetailContent1')
                                if productDetailTitle1 == "Dimensions":
                                    size_dimension = productDetailContent1
                            specification_info = self.collect_specification_info(list_product_response, country_code, country_url,shipping_text)
                            if specification_info:
                                specification[country_name.lower()] = specification_info
                    except Exception as e:
                        print(e)
                else:
                    list_product_response = TextResponse(url='', body=country_resp.text, encoding='utf-8')

                    json_data = list_product_response.json()
                    if not main_material:
                        product_details = json_data['product'].get('custom')
                        main_material = product_details.get('material')
                        productDetailTitle1 = product_details.get('productDetailTitle1')
                        productDetailContent1 = product_details.get('productDetailContent1')
                        if productDetailTitle1 == "Dimensions":
                            size_dimension = productDetailContent1

                    specification_info = self.collect_specification_info(list_product_response, country_code, country_url, shipping_text)
                    if specification_info:
                        specification[country_name.lower()] = specification_info

            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

        list_img = set()
        picture_sources = response.css('.image.js-imagezoom.ally-pdpzoom>source::attr(srcset)').getall()
        for pictures in picture_sources:
            list_img.add(pictures)

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

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        secondary_material = ''
        color = response.css('div.color-selected::text').get()
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = 'Marc Jacobs'
        item['manufacturer'] = self.name
        item['product_badge'] = ''
        item['sku'] = sku
        item['sku_color'] = color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        title = ''
        sku_short_description = ''
        sku_long_description = response.css('ul.accordion-sub-menu.productDescription-item-body li::text').getall()
        script_tag = response.css('script[type="application/ld+json"]::text').get()
        try:
            if script_tag:
                json_data = json.loads(script_tag)
                title = json_data.get("name")
                sku_short_description = json_data.get("description")
            else:
                self.log("No script tag found with type 'application/ld+json'")
        except Exception as e:
            self.log(f"error occured {e}")

        return {
            "sku_title": title,
            "sku_short_description": sku_short_description,
            "sku_long_description":  ' '.join(sku_long_description)
        }

    def collect_specification_info(self, country_resp, country_code, country_url, shipping_text):
        sizes = ''
        json_data = country_resp.json()
        locale = json_data['locale']
        lang_code = locale.split('_')[0]
        currentCountry = json_data['currentCountry']
        price = json_data['product'].get('price')
        sale_prices = price.get('sales', {}).get('value')
        if sale_prices is None:
            return
        else:
            sale_price = str(sale_prices)
        base_price = sale_price
        currency_code = price.get('sales').get('currency')
        variation_attributes = json_data['product'].get('variationAttributes', [])
        for attribute in variation_attributes:
            if attribute.get('attributeId') == 'size':
                sizes = [value.get('displayValue') for value in attribute.get('values', []) if value.get('selectable')]
        rating = json_data['product'].get('rating')
        product_details = json_data['product'].get('custom')
        inventoryStock = product_details.get('inventoryStock')

        availability = json_data['product'].get('availability', {})
        availability_status = availability.get('inStock') == 1
        stock_text = "In Stock" if availability_status else "Out of Stock"
        return {
            "lang": lang_code.lower(),
            "domain_country_code": currentCountry.lower(),
            "currency": currency_code,
            "base_price": base_price ,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": inventoryStock,
            "availability": availability_status,
            "availability_message": stock_text,
            "shipping_lead_time": '2-4 business days.',
            "shipping_expenses": shipping_text,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": rating,
            "reviews_number": ' ',
            "size_available": sizes,
            "sku_link": country_url
        }
