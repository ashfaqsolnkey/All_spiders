import asyncio
import aiohttp
from scrapy import FormRequest
import scrapy
from PIL.Image import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from itertools import cycle
from PIL import Image
from urllib.parse import urlencode, urljoin
from scrapy.http import Request, TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers
conn = aiohttp.TCPConnector()


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


class Tiffiny(scrapy.Spider):
    name = "tiffiny"
    target_urls = []
    sku_mapping = {}
    item_data = {}
    all_target_urls = {}
    all_url = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    country_mapping = '[{"countryCode":"us", "Country_Name":"United States", "currencyCode": "USD", "codeUrl":"com"},{"countryCode": "es","Country_Name": "spain","currencyCode": "USD", "codeUrl" :"es"}]'
    # country_mapping = '[{"countryCode":"us", "Country_Name":"United States", "currencyCode": "USD", "codeUrl":"com"}, {"countryCode": "es","Country_Name": "spain","currencyCode": "USD", "codeUrl" :"es"}, {"countryCode": "cn","Country_Name": "China","currencyCode": "USD", "codeUrl" :"cn"}, {"countryCode": "kr","Country_Name": "Korea","currencyCode": "USD", "codeUrl" :"kr"}, {"countryCode": "sg","Country_Name": "Singapore","currencyCode": "SGD", "codeUrl" :"sg"}, {"countryCode": "ru","Country_Name": "Russia","currencyCode": "USD", "codeUrl" :"ru"}, {"countryCode": "mx","Country_Name": "Mexico","currencyCode": "MXN", "codeUrl" :"com.mx"}, {"countryCode": "uk","Country_Name": "United Kingdom","currencyCode": "EUR", "codeUrl" :"co.uk"}, {"countryCode": "at","Country_Name": "Austria","currencyCode": "USD", "codeUrl" :"com"}, {"countryCode": "fr","Country_Name": "France","currencyCode": "USD" ,"codeUrl" :"fr"}, {"countryCode": "de","Country_Name": "Deutschland","currencyCode": "USD", "codeUrl" :"de"}, {"countryCode": "ie","Country_Name": "Ireland","currencyCode": "USD", "codeUrl" :"ie"}, {"countryCode": "it","Country_Name": "italy","currencyCode": "USD", "codeUrl" :"it"}]'
    base_url = "https://www.tiffany.com"
    start_urls = "https://www.tiffany.es"
    temp_Url = 'https://www.tiffany.'
    handle_httpstatus_list = [404, 400, 500, 430, 401, 500, 302, 301, 403]
    today = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
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
        url = ''
        b_url = self.base_url.split("com")
        json_data = json.loads(self.country_mapping)
        for item in json_data:
            try:
                url_country_code = item.get('codeUrl')
                country_code = item.get('countryCode')
                if 'us' in country_code:
                    url = 'https://www.tiffany.com/content/tiffany-n-co/_jcr_content/servlets/filterMap.filter.en_us.false.1729137600000.js'
                else:
                    url = f'{b_url[0]}{url_country_code}'
                country_request = Request(url, headers=self.headers, dont_filter=True)
                target_response = yield country_request
                self.get_target_urls(target_response)
            except Exception as e:
                print(e)
        parse_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'dnt': '1',
            'origin': 'https://www.tiffany.com',
            'priority': 'u=1, i',
            'referer': 'https://www.tiffany.com/jewelry/shop/bracelets/',
            'sec-ch-ua': '"AVG Secure Browser";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 AVG/129.0.0.0',
            'x-ibm-client-id': 'b9a8bfef128b495f8f17fb3cdeba5555',
            'x-ibm-client-secret': '73805214423d4AaebC96aD5581dbcf0b',
            'Cookie': '_abck=192E8A4B3838C5894800D01DBFA0A467~-1~YAAQRmw/F2Wo686SAQAAuT1m0QxNKzFTQhTsEABXaGfGe/8VmuQuoO621peN1yCX39kfH1UybS/Lrd8/YH5+QpqTTa4efDephCbCfIX2PmCTKZ26b95TSPuv498Ok7kbWwN6nNVp5oyT8cjtBxUh99PCMAugsfR9hHkeTa6xm5Pn0OhRvms8pMJZxx8a1nMWMXotR9mupJBkZjvDB6Wo0AxqGFLfFW1pYf+CYrLL2jQa6+oZbe18nNnPCJ0F/xnLeDdk3QtQRPshYHhQlUyZewvKl7UlDU0yrKczMJPOtDXfWw2dHCwNukqfSHcbpdWvJ1E085RbJOBlZH4a7bmFGiyG/mVtRGLCjvIKNIg6Ee3YIpZNIbP3JIhCqOeWbYqv0Xx0KI58eZkzV9pcmlJG5h6ByB7vZu9JYvjdTXH2rYq+3w0m448DfO7QdcrCp4mfV9GGVe/2Fji4XA==~0~-1~-1; ak_bmsc=DA485CD2CE62AD24F951C76DE2D77605~000000000000000000000000000000~YAAQRmw/FyKC7M6SAQAA73Vm0RkjrJLD+wAjq8gJz2r+qBp+UDqGKA51pAd+HHACGgmxB3pVeYiUVoKti69aqOhnlWzKa7KCx4QYoCcuwCAka+5/1S3zZfCJPJapgtuUKC1ZSUan82lLru6dkEhbO2zoQlzpdaearjtZQOIxw9nTB++5gEzzl39Rrpxeerk8UNHh9Vin+HCQzNtu4OAGym9p8q0X7w0/i7VFpOwr7pIS5Jriom2unuAbKiO+XHNX1GWL7r8LVyhjytjsRcFg/ELheAo90rYrYQoZx/rySyfWntemmiWTbqpea7/euzqQaypxSSfg9i/XDIXK66r5a1hOfp8ILy+HS5iQ; bm_sv=72E2E92E5A67282A35F6C5B27DE61E63~YAAQRmw/F16Gd8+SAQAAL0iQ0RnBxnP62eH7RYyKcvvWX5BvTR0SYWo+M31UlEANAgPYtp1L7iX/+/fvRFmkH+VknCIhjuLjGIm+bWyOuuiBj1f7/Z149wUenVpzIA3m/YaHBCtUi2V7xj7pPJ00B/v38Q1xufk8sm/oOqBysrAgGvpu1yMB8kUP16E0AAbnm1wU7OWHEaEB2Zwa2ITXG9YGoWEW4kRzAz/JDoYvCZTFDfqXXxePsSn1VKHMFTdSqQ==~1; bm_sz=DD0B899E0F54B4A9259988AEAB3578A5~YAAQRmw/FyOC7M6SAQAA73Vm0RnXQTT71j7FA35HZxSt7R6cqhJZbEVbh+G/+R6fRetkVBodxI7rXRsLBdw5YGsIo2AErkITL+np9hUuVZyHwdBUYNnA6YglZ6ix2geib7f4U5sVy2AuDXheU+eaCGJSETPnGk+mPA/61lFoDbLdbeBq/YbLNIyErseUq/UybJqtwJcl9cgiBYk3eEHYdr81RFw+Geed3Fp6u+9k3vcUZWbyYZ0SphB+v2Gt/G25E28GmUL733+2Za5j3ZYgLGUdW8wr7zMXm5zHWdRSgOgRfiAdoDR9HeftOcEu1k6irEb3GO+WgKVVGaPAhfF6HsVMfRG6RrMn+lapRYE=~3225138~4535865; geo-location-cookie=IN'
        }
        for product_url, product_info in self.all_target_urls.items():
            if 'https' in product_url:
                try:
                    product_url = product_info.get('product_url')
                    req = Request(product_url, headers=self.headers, dont_filter=True)
                    resp = yield req
                    if resp.status == 200:
                        self.parse(resp, product_url)
                    else:
                        self.log(f"Received Response for URL: {resp.status_code}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {product_url}: {e}")

            elif "holiday" not in product_url and 'objects' not in product_url and 'online' not in product_url and 'peretti' not in product_url:
                api_url = 'https://www.tiffany.com/ecomproductsearchprocessapi/api/process/v1/productsearch/ecomguidedsearch'
                filter_dimension_id = product_info.get('filterDimensionId')
                filter_category_id = product_info.get('filterCategoryId')
                try:
                    if filter_category_id:
                        dimension_id = int(filter_dimension_id)
                        category_id = int(filter_category_id)
                        payload = {"assortmentID": 101, "sortTypeID": 5, "categoryid": category_id,
                                   "navigationFilters": [dimension_id], "recordsOffsetNumber": 0,
                                   "recordsCountPerPage": 9999, "priceMarketID": "1", "searchModeID": 2, "siteid": 1}
                        json_payload = json.dumps(payload)
                        req = FormRequest(
                            url=api_url,
                            method="POST",
                            headers=parse_headers,
                            body=json_payload,
                        )
                        resp = yield req
                        if resp.status == 403:
                            self.log(f"Received 403 Response for URL: {resp.url}")
                        else:
                            self.fetch_us_data(resp, api_url)

                except Exception as e:
                    self.log(f"Error occurred while processing URL {product_url}: {e}")
        logging.info(f'Total Sku of tiffiny : {len(self.sku_mapping)}')
        for sku_id, product_info in self.sku_mapping.items():
            try:
                product_badge = product_info.get('badge', '')
                product_url = product_info.get('product_url')
                url = response.urljoin(product_url)
                yield Request(
                    url=url,
                    callback=self.parse_product,
                    headers=self.headers,
                    dont_filter=True,
                    cb_kwargs={'product_url': product_url, 'badge': product_badge, 'sku_id': sku_id},
                )

            except Exception as e:
                print(f"exception occured in sku {e}")

    def get_target_urls(self, response):
        if response:
            product_urls = response.css('a.dropdown-link::attr(href)').extract()
            if not product_urls:
                try:
                    tags_map_js = response.text.split('var tagsMap =', 1)[1].split(';', 1)[0]
                    filters_data = json.loads(tags_map_js)
                    for filter_data in filters_data:
                        dimension_id = filter_data.get('filterDimensionId')
                        category_id = filter_data.get('filterCategoryId')
                        url_id = filter_data.get('filterUrlId')
                        excluded_keywords = {
                            "holiday", "setting", "return", "games", "objects", "under",
                            "anniversary", "tiffany", "birthstone", "elsa", "boxes",
                            "tea", "party", "the", "guide", "edit", "love","store",
                            "sunglasses","century","bookmarks-paperweights","by-relation","timeless","flatware"
                        }

                        if category_id and not any(keyword in url_id for keyword in excluded_keywords):
                            self.all_target_urls[url_id] = {
                                'filterDimensionId': dimension_id,
                                'filterCategoryId': category_id
                            }

                except (IndexError, json.JSONDecodeError) as e:
                    self.logger.error(f"Error extracting target URLs: {e}")
            for product_url in product_urls:
                if product_url.endswith('.html'):
                    continue
                else:
                    absolute_url = urljoin(response.url, product_url)
                    self.all_target_urls[absolute_url] = {'product_url': absolute_url}

    def fetch_us_data(self, response, absolute_url):
        try:
            product_data_us = json.loads(response.text)
            if product_data_us:
                products = product_data_us.get('resultDto', {}).get('products', [])
                for product in products:
                    product_url = product.get('canonicalUrl')
                    sku_id = product.get('sku')
                    badge = ''
                    if product_url:
                        product_absolute_url = urljoin(response.url, product_url)
                        self.get_all_sku_mapping(product_absolute_url, sku_id, badge)
        except json.JSONDecodeError as json_err:
            self.logger.error(f"JSON decode error: {json_err}")
        except Exception as e:
            self.logger.error(f"Error in getusData: {e}")

    def parse(self, response, absolute_url):
        try:
            parse_json_data = json.loads(self.country_mapping)
            for item in parse_json_data:
                url_country_code = item.get('codeUrl')
                if 'cn' in url_country_code or 'kr' in url_country_code:
                    continue

                product_elements = response.css('.region.col-6')
                if product_elements:
                    for product in product_elements:
                        product_url = product.css('.image-container a::attr(href)').get()
                        sku_id = product.css('div.product::attr(data-pid)').get()
                        badge = ''
                        if product_url:
                            product_absolute_url = urljoin(response.url, product_url)
                            self.get_all_sku_mapping(product_absolute_url, sku_id, badge)

            next_page = response.css('link[rel="next"]::attr(href)').get()
            if next_page:
                try:
                    next_page_url = urljoin(response.url, next_page)
                    loop = asyncio.get_event_loop()
                    results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))
                    for result in results:
                        if result:
                            next_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                            self.parse(next_response, next_page_url)
                except Exception as e:
                    self.log(f"Error next_page: {e}")

        except json.JSONDecodeError as json_err:
            self.logger.error(f"JSON decode error: {json_err}")
        except Exception as e:
            self.logger.error(f"Error in parse method: {e}")

    def get_all_sku_mapping(self, product_url, sku_id, badge):
        if product_url.endswith('/'):
            new_product_url = product_url
        else:
            new_product_url = f'{product_url}/'

        if sku_id not in self.sku_mapping:
            self.sku_mapping[sku_id] = {'product_url': new_product_url, 'badge': badge}
        else:
            if isinstance(self.sku_mapping[sku_id], str):
                self.sku_mapping[sku_id] = self.sku_mapping[sku_id]
            self.sku_mapping[sku_id] = {'product_url': new_product_url, 'badge': badge}

    @inline_requests
    def parse_product(self, response, product_url, badge, sku_id):
        if response.status in [301, 302, 307]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            retry_url = response.urljoin(redirected_url)
            yield Request(
                retry_url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, 'badge': badge, 'sku_id': sku_id},
            )
            return
        re_split_url = product_url.split("/")
        product_url = "/".join(re_split_url[3:])
        content = {}
        specification = {}
        color = ''
        secMaterial = ''
        description = ''
        sale_price = ''
        material = ''
        secondary_material = ''

        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        if script_tag_content:
            for json_content in script_tag_content:
                json_data = json.loads(json_content)
                try:
                    if 'offers' in json_data:
                        offer = json_data['offers']
                        sale_price = offer.get('price')
                        description = json_data.get("description")
                        color = json_data.get('color')
                        if 'material' in json_data:
                            secMaterial = json_data.get('material')
                            material = secMaterial[0]
                        break
                except Exception as e:
                    self.log(f'json decode error {e}')
        if sale_price:
            if len(secMaterial) > 1:
                secondary_material = secMaterial[1]
            size_dimension = []
            main_material = []
            detail = response.css(
                '.product-description__container_detail_list>li>span.product-description__container_list-content::text').getall()
            list_data = re.split(r'\.(?!\d)', description)
            description = list_data + detail
            lowercase_description = [item.lower() for item in description]
            if lowercase_description is not None:
                material_keywords = {'silver', 'gold', 'platinum', 'cashmere', 'wool', 'silk', 'cuellos', 'skin',
                                     'leather',
                                     'clear', 'steel', 'cotton', 'polyester', 'acrylic', 'ceramics', 'crystal',
                                     'copper'}
                for item in lowercase_description:
                    if any(keyword in item for keyword in material_keywords):
                        main_material.append(item)
                        break

                size_keywords = {'wrists', 'wrist size', 'length', 'weight', 'box size', 'wide', 'ml', 'cm', 'mm'}
                size_dimension.extend(
                    [item for item in lowercase_description if any(keyword in item for keyword in size_keywords)]
                )

            content_info = self.collect_content_information(response)
            if content_info['sku_title']:
                content['es'] = {
                    "sku_link": response.url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"],
                }
            pro_color = ''
            if color:
                pro_color = ''.join(color)

            languages = ['en_en', 'fr_fr', 'it_it', 'ru_ru', 'de_de']
            try:
                for language in languages:
                    logging.info(f'Processing: {language}')
                    s_lang = language.split("_")[0]
                    if s_lang == 'en':
                        content_url = f"{self.temp_Url}com/{product_url}"
                    else:
                        content_url = f"{self.temp_Url}{s_lang}/{product_url}"
                    content_request = Request(content_url, headers=self.headers, dont_filter=True)
                    content_response = yield content_request
                    if content_response.status == 404:
                        self.log(f'request response status {content_response.status}')
                    elif content_response.status == 200:
                        if sku_id in content_request.url:
                            content_info = self.collect_content_information(content_response)
                            lang = language.split("_")[1]
                            if content_info['sku_title']:
                                content[lang] = {
                                    "sku_link": content_url,
                                    "sku_title": content_info["sku_title"],
                                    "sku_short_description": content_info["sku_short_description"],
                                    "sku_long_description": content_info["sku_long_description"],
                                }
                    elif content_response.status in [301, 302]:
                        content_retry_url = content_response.headers.get(b'location').decode('utf-8')
                        content_response_retry_url = content_response.urljoin(content_retry_url)
                        content_retry_req = scrapy.Request(content_response_retry_url, headers=self.headers,
                                                           dont_filter=True)
                        content_retry_resp = yield content_retry_req
                        if content_retry_resp.status == 200:
                            if '?fallback=true' in content_response_retry_url:
                                continue
                            else:
                                content_info = self.collect_content_information(content_retry_resp)
                                lang = language.split("_")[1]
                                if content_info['sku_title']:
                                    content[lang] = {
                                        "sku_link": f'{content_response_retry_url}',
                                        "sku_title": content_info["sku_title"],
                                        "sku_long_description": content_info["sku_long_description"],
                                        "sku_short_description": content_info['sku_short_description']
                                    }
                                else:
                                    continue
                        else:
                            continue
                        time.sleep(1)
                    else:
                        self.log(f"Received {content_response.status}...... Content Response")
            except json.JSONDecodeError as e:
                self.log(f'Error language url fatching url fatching: {e}')

            try:
                b_url = self.base_url.split("com")[0]
                json_data = json.loads(self.country_mapping)
                for item in json_data:
                    country_code = item.get('countryCode').lower()
                    url_country_code = item.get('codeUrl')
                    if url_country_code == 'ca':
                        specific_url = f'https://fr.tiffany.{url_country_code}/{product_url}'
                    else:
                        specific_url = f'{b_url}{url_country_code}/{product_url}'
                    req_country = Request(specific_url, headers=self.headers, dont_filter=True)
                    resp_country = yield req_country
                    if resp_country.status == 404:
                        self.log(f"RECEIVED 404 Response for URL: {resp_country.url}")
                    elif resp_country.status == 200:
                        specification_info = self.collect_specification_info(resp_country, country_code, specific_url)
                        specification[country_code] = specification_info
                    elif resp_country.status in [301, 302]:
                        specific_retry_url = resp_country.headers.get(b'Location').decode('utf-8')
                        specification_url = resp_country.urljoin(specific_retry_url)
                        specification_url_req = Request(specification_url, headers=self.headers, dont_filter=True)
                        specification_url_resp = yield specification_url_req
                        if specification_url_resp.status == 200:
                            if '?fallback=true' in specification_url:
                                continue
                            else:
                                specification_info = self.collect_specification_info(specification_url_resp,
                                                                                     country_code, specification_url)
                                specification[country_code] = specification_info

            except json.JSONDecodeError as e:
                self.log(f'Error specification url fatching: {e}')
                return
            image_urls = []
            script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
            for data in script_tag_content:
                try:
                    json_data = json.loads(data)
                    if "image" in json_data:
                        images = json_data.get("image")
                        if isinstance(images, list):
                            for image in images:
                                image_urls .append(image.get("url"))
                        else:
                            image_urls .append(images)
                        break
                except Exception as e:
                    print("Error in json", e)
            list_img = []
            for relative_url in image_urls:
                base_url = 'https://media.tiffany.com/'
                absolute_url = urljoin(base_url, relative_url)
                list_img.append(absolute_url)

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
                    for url_img in list_img:
                        filename = str(uuid.uuid4()) + ".png"
                        trial_image = 0
                        while trial_image < 10:
                            try:
                                image_req = Request(url_img, headers=self.headers, dont_filter=True)
                                image_res = yield image_req
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
                                img_file.write(image_res.body)
                            image = Image.open(os.path.join(directory, filename))
                            image.save(os.path.join(directory, filename))
                            image_info = os.path.join(directory, filename)
                            product_images_info.append(image_info)

                        except Exception as e:
                            logging.error(f"Error processing image: {e}")

            collection = ''
            domain, domain_url = self.extract_domain_domain_url(response.url)
            time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            product_collection = response.css(".product-description__content_eyebrow>span>span::text").get()
            if product_collection:
                collection = product_collection.strip()
            if material is None:
                material = ' '.join(main_material)
            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['collection_name'] = collection
            item['brand'] = "Tiffiny Co."
            item['manufacturer'] = self.name
            item['product_badge'] = badge
            item['sku'] = sku_id
            item['sku_color'] = pro_color
            item['main_material'] = material
            item['secondary_material'] = secondary_material
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimension
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response):
        sku_title = ''
        sku_short_description = ''
        sku_long_description = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        if script_tag_content:
            for json_content in script_tag_content:
                json_data = json.loads(json_content)
                if 'description' in json_data:
                    sku_short_description = json_data.get('description')
                    sku_title = json_data.get('name')
                    material = json_data.get('material')
                    if material:
                        sku_long_description = f"{sku_short_description} {' '.join(material)}"
                    else:
                        sku_long_description = f"{sku_short_description}"
        else:
            sku_title = response.css('.product-description__content_title>span::text').get()
            sku_short_description = response.css('.product-description__container_long-desc::text').get()
            list_desc = response.css(
                ".product-description__container_detail_list>li>span.product-description__container_list-content::text").getall()
            sku_long_description = f"{sku_short_description} {' '.join(list_desc)}"
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, url):
        size_available = resp.xpath('//*[@id="menu2"]/li[1]/div/a/span').extract()
        currency_codes = ''
        sale_price = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        if script_tag_content:
            for json_content in script_tag_content:
                json_data = json.loads(json_content)
                if 'offers' in json_data:
                    offer = json_data['offers']
                    sale_price = offer.get('price')
                    currency_codes = offer.get('priceCurrency')
                    break
        availability = resp.css('div.product-description__buttons tiffany-pdp-buttons').extract()
        if availability is not None:
            availability_status = "Yes"
            out_of_stock_text = "Available"
        else:
            availability_status = "No"
            out_of_stock_text = "Temporarily out of stock"

        lang = 'en'
        return {
            "lang": lang,
            "domain_country_code": country_code,
            "currency": currency_codes,
            "base_price": sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": '',
            "shipping_expenses": "",
            "marketplace_retailer_name": "tiffiny",
            "condition": "NEW",
            "reviews_rating_value": "",
            "reviews_number": "",
            "size_available": size_available,
            "sku_link": url
        }
