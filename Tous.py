import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from scrapy.http import Request, TextResponse
from itertools import cycle
import aiohttp
import asyncio
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


async def get_page(session, url, proxy_cycle, tous_headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url,proxy=f"http://{proxy}", headers=tous_headers) as response:

                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1

    return None


async def get_all(session, urls,proxy_cycle, tous_headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle,tous_headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, tous_headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=tous_headers,timeout=timeout) as session:
                data = await get_all(session, urls,proxy_cycle,tous_headers)
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


class Tous(scrapy.Spider):
    name = "Tous"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.tous.com"
    handle_httpstatus_list = [200, 430, 404, 301, 410]
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    # spec_mapping = '[{"countryCode": "us", "url_countryCode": "us-en"},{"countryCode": "es", "url_countryCode": "es-es"}]'

    spec_mapping = '[{"countryCode": "us", "url_countryCode": "us-en"},{"countryCode": "eu", "url_countryCode": "eu-en"},{"countryCode": "sk", "url_countryCode": "sk-sk"}, {"countryCode": "sa", "url_countryCode": "sa-en"},{"countryCode": "pr", "url_countryCode": "pr-en"},{"countryCode": "pt", "url_countryCode": "pt-pt"},{"countryCode": "pl", "url_countryCode": "pl-pl"},{"countryCode": "pe", "url_countryCode": "pe-es"},{"countryCode": "mx", "url_countryCode": "mx-es"},{"countryCode": "jp", "url_countryCode": "jp-en"},{"countryCode": "it", "url_countryCode": "it-it"},{"countryCode": "il", "url_countryCode": "il-iw"},{"countryCode": "gr", "url_countryCode": "gr-el"},{"countryCode": "de", "url_countryCode": "de-de"},{"countryCode": "fr", "url_countryCode": "fr-fr"},{"countryCode": "es", "url_countryCode": "es-es"},{"countryCode": "cz", "url_countryCode": "cz-cs"},{"countryCode": "cr", "url_countryCode": "cr-es"},{"countryCode": "cl", "url_countryCode": "cl-es"},{"countryCode": "bo", "url_countryCode": "bo-es"},{"countryCode": "gb", "url_countryCode": "gb-en"},{"countryCode": "co", "url_countryCode": "co-es"},{"countryCode": "si", "url_countryCode": "eu-en"},{"countryCode": "nl", "url_countryCode": "eu-en"},{"countryCode": "mt", "url_countryCode": "eu-en"},{"countryCode": "lu", "url_countryCode": "eu-en"},{"countryCode": "lt", "url_countryCode": "eu-en"},{"countryCode": "lv", "url_countryCode": "eu-en"},{"countryCode": "ie", "url_countryCode": "eu-en"},{"countryCode": "ee", "url_countryCode": "eu-en"},{"countryCode": "cy", "url_countryCode": "eu-en"},{"countryCode": "be", "url_countryCode": "eu-en"},{"countryCode": "at", "url_countryCode": "eu-en"}]'
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
    start_urls = "https://www.tous.com/us-en/"

    tous_headers = headers = {
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
        'Cookie': 'BLUE_GREEN=1; DEVICE_TYPE=desktop; user-path=%5B%7B%22id%22%3A%22311293540%22%2C%22text%22%3A%22Pendientes%20aro%20de%20plata%20New%20Hav%22%2C%22href%22%3A%22%2Fpendientes-aro-de-plata-new-hav%2Fp%2F311293540%22%2C%22routeName%22%3A%22product%22%7D%5D; userType=anonymousCustomerGroup'
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
            headers=self.tous_headers,
        )

    @inline_requests
    def country_base_url(self, response):
        # country_data = json.loads(self.spec_mapping)
        # for country in country_data:
        #     try:
        #         url_countryCode = country['url_countryCode']
        #         url = 'https://www.tous.com/'+url_countryCode
        #         req = scrapy.Request(url, headers=self.tous_headers, dont_filter=True)
        #         target_response = yield req
        #         if target_response.status == 200:
        #             self.get_target_urls(target_response)
        #         elif target_response.status == 301:
        #             redirected_url = target_response.headers.get(b'Location').decode('utf-8')
        #             url = response.urljoin(redirected_url)
        #             req = scrapy.Request(url, headers=self.tous_headers, dont_filter=True)
        #             target_response = yield req
        #             self.get_target_urls(target_response)
        #     except Exception as e:
        #         print(e)
        all_target_urls = ['https://www.tous.com/rest/v2/tousSite-us/products/search?query=::allCategories:1:&pageSize=40009&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL','https://www.tous.com/rest/v2/tousSite-es/products/search?query=::allCategories:1:&pageSize=40009&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL','https://www.tous.com/rest/v2/tousSite-es/products/search?query=::allCategories:25:&pageSize=3929&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL','https://www.tous.com/rest/v2/tousSite-es/products/search?query=::allCategories:35:&pageSize=3444&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL&GLCurrency=EUR&GLCountry=ES','https://www.tous.com/rest/v2/tousSite-es/products/search?query=::allCategories:2026:&pageSize=2099&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL','https://www.tous.com/rest/v2/tousSite-es/products/search?query=::allCategories:4243:&pageSize=3099&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL', 'https://www.tous.com/rest/v2/tousSite-us/products/search?query=::allCategories:57:&pageSize=3200&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL', 'https://www.tous.com/rest/v2/tousSite-us/products/search?query=::allCategories:3800:&pageSize=2004&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL', 'https://www.tous.com/rest/v2/tousSite-us/products/search?query=::allCategories:35:&pageSize=9999&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL', 'https://www.tous.com/rest/v2/tousSite-us/products/search?query=::allCategories:4100:&pageSize=2004&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL', 'https://www.tous.com/rest/v2/tousSite-us/products/search?query=::allCategories:172:&pageSize=2200&currentPage=0&customerGroupId=anonymousCustomerGroup&sort=BASIC&fields=FULL']
        for link in all_target_urls:
            if link:
                headers = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.9',
                    'cache-control': 'no-cache',
                    'pragma': 'no-cache',
                    'priority': 'u=1, i',
                    'referer': 'https://www.tous.com/us-en/jewelry/c/1',
                    'rest-api-id': 'Maha4mmHxagCF4U4dcZK6MdywVvN2HNr9F7xbBH2s2ty97akdBafEKxwCmyfEQHn',
                    'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'traceparent': '00-5224d65e5f78bb7029d1958a3ea64031-9e42df7c15a51fd6-01',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
                    'x-tous-channel': 'WEB',
                    'Cookie': 'user-path=%5B%7B%22id%22%3A1%2C%22text%22%3A%22Jewelry%22%2C%22href%22%3A%22%2Fjewelry%2Fc%2F1%22%2C%22routeName%22%3A%22category%22%7D%5D; DEVICE_TYPE=desktop; BLUE_GREEN=1; userType=anonymousCustomerGroup; GlobalE_Full_Redirect=false; selector-country=%7B%22countryISO%22%3A%22US%22%2C%22cultureCode%22%3A%22en-US%22%2C%22currencyCode%22%3A%22USD%22%2C%22site%22%3A%22us-en%22%7D; BLUE_GREEN=0; DEVICE_TYPE=desktop; userType=anonymousCustomerGroup'
                }
                try:
                    url = response.urljoin(link)
                    req = Request(url, headers=headers, dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        self.parse(resp)
                    else:
                        self.log(f"Received Response for URL: {resp.status_code}")
                except Exception as e:
                    print(e)
                    self.log(f"Error occurred while processing URL {link}: {e}")

        logging.info(f'Total Sku of Tous : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.tous_headers,
                cb_kwargs={'product_url': product_url}
            )

    def get_target_urls(self, response):
        if response:
            target_urls = response.css('.track-links>ul>li>a::attr(href)').getall()
            target_urls_icon = response.css('.semantic-link>a::attr(href)').getall()
            combined_target_urls = target_urls + target_urls_icon

            if combined_target_urls:
                target_urls_list = list(set(combined_target_urls))
            else:
                target_urls = response.css('.semantic-link a::attr(href)').getall()
                target_urls_list = list(set(target_urls))

            for link in target_urls_list:
                end_url = link.split('/')[-1]
                if link not in self.all_target_urls and link.endswith(end_url) not in self.all_target_urls and "/wsj" not in link and "/we-are-tous" not in link:
                    self.all_target_urls.append(link)

    def parse(self, response):
        sku_id = ''
        json_data = json.loads(response.text)
        all_products = json_data['products']
        for product in all_products:
            try:
                sku_id = product.get("code")
                product_link = product.get("url")
                if "es" in product_link:
                    product_url = "/es-es"+product_link
                else:
                    product_url = "/us-en" + product_link
                self.get_all_sku_mapping(product_url, sku_id)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to decode JSON: {e}")

        # product_elements = response.css("div.d-flex.product-card-grid")
        # for product_ele in product_elements:
        #     product_url = product_ele.css('a.link.product-image-link::attr(href)').get()
        #     product_id = product_ele.css('div[id^="product-"]::attr(id)').get()
        #     if product_id:
        #         sku_id = product_id.split('-')[-1]
        #     self.get_all_sku_mapping(product_url, sku_id)
        #
        # next_page_link = response.css('link[rel="next"]::attr(href)').get()
        # if next_page_link:
        #     try:
        #         loop = asyncio.get_event_loop()
        #         results = loop.run_until_complete(main([next_page_link], self.proxy_cycle, self.tous_headers))
        #         for result in results:
        #             if result:
        #                 next_response = TextResponse(url=next_page_link, body=result, encoding='utf-8')
        #                 self.parse(next_response)
        #     except Exception as e:
        #         self.log(f"Error next_page: {e}")

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
    def parse_product(self, response, product_url):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get(b'Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.tous_headers,
                cb_kwargs={'product_url': product_url}
            )
            return
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

        url_parts = product_url.split("/")
        url_without_language = "/".join(url_parts[2:])
        property_data = {}
        information_data = {}
        size_dimensions = []
        content = {}
        specification = {}
        collection_name = ''
        sku_title = ''
        short_description = ''
        product_color = ''
        brand = ''
        sku_id = ''
        main_material = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            sku_title = json_data.get("name")
            short_description = json_data.get("description")
            main_material = json_data.get("material")
            product_color = json_data.get("color")
            sku_id = json_data.get("sku")
            brand = json_data["brand"].get("name")
        properties = response.css('.variant-container')
        for prop in properties:
            variant_name = prop.css('.variant-name::text').get().strip()
            for property_container in prop.css('.property-container'):
                property_name = property_container.css('.property-name::text').get().strip()
                property_value = property_container.css('.property-value::text').get().strip()
                property_data[property_name] = property_value
                variant_properties = f"{variant_name} {property_name}: {property_value}"
                size_dimensions.append(variant_properties.strip())

        information = response.css('.list .property')
        for prop in information:
            information_name = prop.css('.property-name::text').get().strip()
            information_value = prop.css('.property-value::text').get().strip()
            information_data[information_name] = information_value
        collection = information_data.get("Collection")
        if collection:
            collection_name = collection.strip()
        sku_long_description = f"{short_description}"
        for prop_name, prop_value in property_data.items():
            sku_long_description += f"{prop_name}: {prop_value}"
        for info_name, info_value in information_data.items():
            sku_long_description += f"{info_name}: {info_value}"
        url_language = url_parts[1].split('-')[1]
        content[url_language] = {
            "sku_link": response.url,
            "sku_title": sku_title.strip(),
            "sku_short_description": short_description,
            "sku_long_description": sku_long_description.strip()
        }
        languages = ["es-es", "sa-ar", "pt-pt", "pl-pl", "pe-es", "jp-ja", "sk-sk", "it-it", "il-iw", "gr-el", "de-de", "fr-fr", "es-ca", "cz-cs"]
        for language in languages:
            logging.info(f'Processing: {language}')
            url = f'{self.base_url}/{language}/{url_without_language}'
            req = Request(url, headers=headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                content_info = self.collect_content_information(resp)
                content[language.split("-")[1]] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }

            elif resp.status == 301:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=headers, dont_filter=True)
                resp = yield req
                content_info = self.collect_content_information(resp)
                content[language.split("-")[1]] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            else:
                self.log(f"Received 404 Response for URL: {resp.url}")

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode').lower()
            url_countryCode = item.get("url_countryCode")
            url = f'{self.base_url}/{url_countryCode}/{url_without_language}'
            req = Request(url, headers=headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                specification_info = self.collect_specification_info(resp, country_code, url_countryCode)
                specification[country_code] = specification_info
            elif resp.status == 301:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=headers, dont_filter=True)
                resp = yield req
                specification_info = self.collect_specification_info(resp, country_code, url_countryCode)
                specification[country_code] = specification_info
            else:
                self.log(f"Received 404 Response for URL: {resp.url}")

        list_img = []
        imgs = []
        img_list_1 = response.css('img.w-100::attr(src)').getall()
        img_list_2 = response.css('div.position-relative>div.img.w-100>img::attr(data-src)').getall()
        imgs.extend(img_list_1)
        imgs.extend(img_list_2)
        for img in imgs:
            list_img.append(img)

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

        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        domain, domain_url = self.extract_domain_domain_url(response.url)
        item = ProductItem()
        item["date"] = time_stamp
        item["domain"] = domain
        item["domain_url"] = domain_url
        item["collection_name"] = collection_name
        item["brand"] = brand
        item["manufacturer"] = self.name
        item["sku"] = sku_id
        item["sku_color"] = product_color
        item["main_material"] = main_material
        item["image_url"] = product_images_info
        item["size_dimensions"] = size_dimensions
        item["content"] = content
        item["specification"] = specification
        yield item

    def collect_content_information(self, resp):
        short_description = ''
        sku_title = ''
        long_description = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            sku_title = json_data.get("name")
            short_description = json_data.get("description")
        property_data = {}
        information_data = {}
        properties = resp.css('.variant-container .property-container')
        for prop in properties:
            property_name = prop.css('.property-name::text').get().strip()
            property_value = prop.css('.property-value::text').get().strip()
            property_data[property_name] = property_value

        information = resp.css('.list.property')
        for prop in information:
            information_name = prop.css('.property-name::text').get().strip()
            information_value = prop.css('.property-value::text').get().strip()
            information_data[information_name] = information_value
        sku_long_description = f"{short_description}"
        for prop_name, prop_value in property_data.items():
            sku_long_description += f"{prop_name}: {prop_value}"
        for info_name, info_value in information_data.items():
            sku_long_description += f"{info_name}: {info_value}"
        if sku_long_description:
            long_description = sku_long_description.strip()
        return {
                "sku_title": sku_title.strip(),
                "short_description": short_description,
                "sku_long_description": long_description
            }

    def collect_specification_info(self, response, country_code, url_countryCode):
        product_id = ''
        currency_code = ''
        sale_price = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        out_of_stock_text = ''
        availability_status = ''
        country = url_countryCode.split("-")[0]
        lang = url_countryCode.split("-")[1]
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data:
                    price = json_data["offers"].get("price")
                    sale_price = "{:.2f}".format(float(price))
                    currency_code = json_data["offers"].get("priceCurrency")
                    product_id = json_data.get("sku")
            except Exception as e:
                print("Error in collect_specification_info:", e)

        base_price = ''
        price_string = response.css('div > span.discounted-price::text').get()
        if not price_string:
            base_price = sale_price
        else:
            base_price = self.extract_price_info(price_string)

        shipping_expenses_text = response.css('.collapsable-content')
        shipping_expense = shipping_expenses_text.css('.collapse-title::text').get()
        if shipping_expense:
            shipping_expenses = shipping_expense.strip()
        shipping_lead = response.xpath('//*[@id="product-images"]/div[2]/div/div[2]/div/div/div[2]/div[1]/h3/text()').get()
        if shipping_lead:
            shipping_lead_time = shipping_lead.strip()
        div_element = response.css("div.add-product-to-bag")
        product_available = bool(div_element)
        if product_available == True:
            product_availability = self.check_product_availability(product_available)
            availability_status = product_availability[0]
            out_of_stock_text = product_availability[1]
        else:
            availability = response.css('div.no-stock>div::text').get()
            if len(availability) > 1:
                availability = availability.strip()
                product_availability = self.check_product_availability(availability)
                availability_status = product_availability[0]
                out_of_stock_text = availability
            else:
                availability = response.css("div.px-0>div.no-stock>div>div.button.coming-soon-cta>button>.text-box::text").extract()
                if availability:
                    for avail in availability:
                        if len(avail) > 1:
                            available = avail.strip()
                            product_availability = self.check_product_availability(available)
                            availability_status = product_availability[0]
                            out_of_stock_text = available

        sizes = response.css('#size-selector-desktop>div.sizes-list>button>span::text').getall()
        unique_sizes = set(size.strip() for size in sizes)
        unique_sizes_list = list(unique_sizes)

        product_stock_quantity = ''
        # try:
        #     stock_response = self.get_stock_product(product_id, country, lang, currency_code)
        #     if stock_response.status == 200:
        #         data = stock_response.json()
        #         product_stock_quantity = data["catalog"]["content"][0]["stock"]
        #     else:
        #         logging.error(f"Failed to retrieve stock information. Status code: {stock_response.status}")
        #
        # except Exception as e:
        #     logging.error(f"Error processing stock_response: {e}")
        return {
            "lang": url_countryCode.split('-')[1],
            "domain_country_code": country_code,
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": sale_price if sale_price else 0.0,
            "active_price": sale_price if sale_price else 0.0,
            "stock_quantity": product_stock_quantity,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            # Use a default value, adjust as needed
            "marketplace_retailer_name": 'tous',
            "condition": "NEW",
            "reviews_rating_value": 0.0,  # Use a default value, adjust as needed
            "reviews_number": 0,  # Use a default value, adjust as needed
            "size_available": unique_sizes_list,
            "sku_link": response.url if response.url else 'NA',
        }

    def check_product_availability(self, product_available):
        try:
            availability_value = product_available
            if availability_value == True:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text

            else:
                out_of_stock_text = availability_value
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
            return None

    # def get_stock_product(self, product_id, country, lang, currency_code):
    #     next_response = ''
    #     url = f"https://api.empathy.co/search/v1/query/tous/search?internal=true&query={product_id}&origin=search_box%3Anone&start=0&rows=24&instance=tous&lang={lang}&scope=desktop&currency={currency_code.upper()}&priceTarget=WEBanonymousCustomerGroup&store={country}&isSPA=true"
    #     try:
    #         loop = asyncio.get_event_loop()
    #         results = loop.run_until_complete(main([url], self.proxy_cycle, self.tous_headers))
    #         for result in results:
    #             if result:
    #                 next_response = TextResponse(url=url, body=result, encoding='utf-8')
    #                 # self.parse(next_response)
    #     except Exception as e:
    #         self.log(f"Error next_page: {e}")
    #
    #     # response = requests.request("GET", url)
    #     return next_response





