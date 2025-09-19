from itertools import cycle
from urllib.parse import urljoin
import scrapy, asyncio, aiohttp
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from scrapy.http import Request, TextResponse
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests,json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


async def get_page(session, url, proxy_cycle, headers):
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


async def get_all(session, urls, proxy_cycle, headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle, headers=headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                data = await get_all(session, urls, proxy_cycle, headers)
                return data
        except asyncio.TimeoutError:
            error_msg = 'Request timed out'
            print(error_msg)
            continue
        except aiohttp.client.ClientConnectionError:
            error_msg = 'ClientConnectionError'
            print(error_msg)
            continue


class GorjanaSpider(scrapy.Spider):
    name = "gorjana"
    sku_mapping = {}
    target_urls = []
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://www.gorjana.com/"
    REDIRECT_ENABLED = True
    handle_httpstatus_list = [430, 500, 403, 404, 301, 302]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    directory = get_project_settings().get("FILE_PATH")

    if not os.path.exists(directory):
        os.makedirs(directory)

    logs_path = os.path.join(directory, today + "_" + name + ".log")
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    start_urls = "https://www.gorjana.com/"

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
            headers=rotate_headers()
        )

    @inline_requests
    def country_base_url(self, response):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = redirected_url
            yield Request(
                url,
                callback=self.country_base_url,
                headers=self.headers,
                dont_filter=True,
            )
            return
        self.get_target_urls(response)
        collection_id = ""

        for link in self.all_target_urls:
            try:
                product_url = response.urljoin(link)
                request = scrapy.Request(product_url, headers=self.headers, dont_filter=True)
                resp = yield request
                if resp.status == 200:
                    collection_id = resp.css(".nosto_category>span.id::text").get()
                    print(collection_id)
                elif resp.status in [301, 302]:
                    redirect_url = resp.headers.get(b'Location').decode('utf-8')
                    url = resp.urljoin(redirect_url)
                    redirect_req = Request(url, headers=self.headers, dont_filter=True)
                    redirect_resp = yield redirect_req
                    if redirect_resp.status == 200:
                        collection_id = redirect_resp.css(".nosto_category>span.id::text").get()
                        print(collection_id)
                else:
                    self.log(f"Received Response for URL: {resp.status_code}")
            except Exception as e:
                self.log(f"Error occurred while processing URL {link}: {e}")
            if collection_id:
                page_counter = 1
                product_api = f"https://services.mybcapps.com/bc-sf-filter/filter?shop=gorjana.myshopify.com&collection_scope={collection_id}&build_filter_tree=true&page={page_counter}&limit=72&sort=manual&event_type=filter"
                request = scrapy.Request(product_api, headers=self.headers, dont_filter=True)
                resp = yield request
                if resp.status == 200:
                    self.parse(resp, product_api, page_counter, collection_id)
                else:
                    self.log(f"Received Response for URL: {resp.status_code}")

        logging.info(f'Total Sku of Gorjana : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            review_count = self.sku_mapping[sku_id].get('review_count')
            review_ratings = self.sku_mapping[sku_id].get('review_ratings')
            image = self.sku_mapping[sku_id].get('image')
            barcode = self.sku_mapping[sku_id].get('barcode')
            inventory_quantity = self.sku_mapping[sku_id].get('inventory_quantity')
            product_url = self.sku_mapping[sku_id].get('product_url')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                dont_filter=True,
                cb_kwargs={'product_url': product_url, "sku_id": sku_id, 'review_count': review_count, 'review_ratings': review_ratings,'barcode': barcode, 'inventory_quantity': inventory_quantity, 'image': image}
            )

    def get_target_urls(self, response):
        target_urls = response.css('li.link--level3.link--collection_link>a::attr(href)').getall()
        target_urls_list = list(set(target_urls))
        for link in target_urls_list:
            if link not in self.all_target_urls:
                absolute_url = urljoin(self.base_url, link)
                self.all_target_urls.append(absolute_url)

    def parse(self, response, link, page_counter, collection_id):
        json_data = json.loads(response.text)
        products_lists = json_data.get("products")
        for products_list in products_lists:
            try:
                handle = products_list.get("handle")
                product_type = products_list.get("product_type")
                review_count = products_list.get("review_count")
                review_ratings = products_list.get("review_ratings")
                variants = products_list.get("variants")
                for variant in variants:
                    inventory_quantity = variant.get("inventory_quantity")
                    barcode = variant.get("barcode")
                    image = variant.get("image")
                    print(image)
                    variant_id = variant.get("id")
                    sku_id = variant.get("sku")
                    product_url = f"https://www.gorjana.com/collections/{product_type.lower()}/products/{handle}?variant={variant_id}"
                    self.get_all_sku_mapping(product_url, sku_id, review_count, review_ratings, barcode, inventory_quantity, image)
            except Exception as e:
                print("Exception in products_list", e)

        if products_lists:
            try:
                counter = int(page_counter) + 1
                next_page_url = f"https://services.mybcapps.com/bc-sf-filter/filter?shop=gorjana.myshopify.com&collection_scope={collection_id}&build_filter_tree=true&page={counter}&limit=72&sort=manual&event_type=filter"
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))
                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.parse(product_response, link, counter, collection_id)
            except Exception as e:
                print("Exception in Pagination", e)

    def get_all_sku_mapping(self, product_url, sku_id, review_count, review_ratings, barcode, inventory_quantity, image):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'review_count': review_count, 'review_ratings': review_ratings, 'barcode': barcode, 'inventory_quantity': inventory_quantity, 'image': image}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'review_count': review_count, 'review_ratings': review_ratings, 'barcode': barcode, 'inventory_quantity': inventory_quantity, 'image': image}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'review_count': review_count, 'review_ratings': review_ratings, 'barcode': barcode, 'inventory_quantity': inventory_quantity, 'image': image}

    @inline_requests
    def parse_product(self, response, product_url, sku_id, review_count, review_ratings, barcode, inventory_quantity, image):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = redirected_url
            yield Request(
                url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': product_url, "sku_id": sku_id, 'review_count': review_count, 'review_ratings': review_ratings, 'barcode': barcode, 'inventory_quantity': inventory_quantity, 'image': image}
            )
            return

        list_img = []
        if image:
            list_img.append(image)
        else:
            image_url = response.css('.media.media--image>img::attr(src)').get()
            list_img.append(image_url)

        sku_format = ''
        if sku_id:
            sku_format = '-'.join(sku_id.rsplit('-', 1)[:-1])
        image_source = response.css('span.alternate_image_url::text').getall()
        matching_urls = [url for url in image_source if sku_format in url]
        for image_url in matching_urls:
            images = response.urljoin(image_url)
            list_img.append(images)

        content = {}
        specification = {}
        content_info = self.collect_content_information(response)
        content['en'] = {
            "sku_link": f'{product_url}',
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        specification_info = self.collect_specification_info(response, product_url, review_count, review_ratings, inventory_quantity)
        specification['us'] = specification_info
        main_material = response.css('.custom_fields>span.Metal::text').get()
        secondary_material = response.css('.custom_fields>span.Stones::text').getall()
        secondary_materials = ','.join(material.strip() for material in secondary_material)

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku_id + "/"
                for url_img in list_img:
                    trial_image = 0
                    while trial_image < 5:
                        try:
                            req = Request(url_img, headers=self.headers, dont_filter=True)
                            res = yield req
                            if res.status == 302:
                                logging.info(f"Received 302 for URL: {url_img}. Retrying...")
                                trial_image += 1
                                time.sleep(1)
                            elif res.status == 200:
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
        product_badge = response.css('.media-gallery__images-wrapper>.product-badge::text').get() or ''

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = "Gorjana"
        item['product_badge'] = product_badge
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['gtin13'] = barcode
        item['sku_color'] = ''
        item['main_material'] = main_material
        item['secondary_material'] = secondary_materials
        item['image_url'] = product_images_info
        item['size_dimensions'] = ''
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        sku_title = ''
        sku_long_description = ''
        sku_short_description = ''
        details_text = ''
        script_content = response.css('script[type="application/ld+json"]::text').get()
        if script_content:
            try:
                json_data = json.loads(script_content)
                sku_title = json_data.get('name')

            except json.JSONDecodeError:
                self.logger.error('Failed to decode JSON data')
        else:
            self.logger.warning('No JSON-LD script found on the page')

        details = response.css('div[v-if="details"] ul li::text').getall()
        cleaned_details = [detail.strip() for detail in details]
        details_text = ''.join(cleaned_details)

        script_content = response.css('script::text').getall()
        try:
            for script in script_content:
                if 'theme.product.variants' in script:
                    match_short_description = re.search(r'theme\.product\.variants\[\d+\]\.short_description\s*=\s*"([^"]+)"', script)
                    match_description = re.search(r'theme\.product\.variants\[\d+\]\.description\s*=\s*"([^"]+)"', script)
                    if match_short_description:
                        sku_short_description = match_short_description.group(1)
                    if match_description:
                        sku_long_description = match_description.group(1)

            sku_long_description += ' ' + details_text
        except Exception as e:
            print("Exception in collect_content_information", e)

        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, product_url, review_count, review_ratings, inventory_quantity):
        sale_price = ''
        base_price = ''
        currency_code = ''
        availability = ''
        script_content = response.css('script[type="application/ld+json"]::text').get()
        if script_content:
            try:
                json_data = json.loads(script_content)
                price = json_data.get('offers', [{}])[0].get('price')
                sale_price = str(price)
                base_price = sale_price
                currency_code = json_data.get('offers', [{}])[0].get('priceCurrency')
                availability = json_data.get('offers', [{}])[0].get("availability")
            except json.JSONDecodeError:
                self.logger.error('Failed to decode JSON data')
        else:
            self.logger.warning('No JSON-LD script found on the page')

        sized = response.css('span.custom_fields span.Size::text').getall()
        sizes = [size.strip() for size in sized]

        shipping_lead_time = response.css('details.accordion .accordion__content p::text').getall()
        shipping_lead_time_string = ' '.join([text for text in shipping_lead_time if '30 days' in text.lower()])

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": 'US',
            "domain_country_code": 'US',
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": inventory_quantity,
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "marketplace_retailer_name": "gorjana",
            "condition": "NEW",
            "reviews_rating_value": review_ratings,
            "reviews_number": review_count,
            "shipping_lead_time": shipping_lead_time_string,
            "shipping_expenses": '',
            "size_availability": sizes,
            "sku_link": product_url
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