import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from itertools import cycle
import aiohttp,asyncio
from scrapy.http import Request, TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


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


class Shopdorsey(scrapy.Spider):
    name = "shopdorsey"
    all_target_urls = []
    sku_mapping = {}
    start_urls = "https://www.shopdorsey.com/"
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://www.shopdorsey.com"
    handle_httpstatus_list = [430, 403, 404, 302, 301]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    directory = get_project_settings().get("FILE_PATH")
    if not os.path.exists(directory):
        os.makedirs(directory)
    spec_mapping = '[{"countryCode": "ve","Country_Name":"Venezuela","currencyCode":"VEF"},{"countryCode": "pe","Country_Name":"Peru","currencyCode":"PEN"},{"countryCode": "uy","Country_Name":"Uruguay","currencyCode":"USD"},{"countryCode": "sa", "Country_Name":"Saudi Arabia","currencyCode":"SAR"},{"countryCode": "qa","Country_Name":"Qatar","currencyCode":"QAR"},{"countryCode": "at","Country_Name":"Austria","currencyCode":"EUR"},{"countryCode": "be", "Country_Name":"Belgium","currencyCode":"EUR"},{"countryCode": "ua","Country_Name":"Ukraine","currencyCode":"UAH"},{"countryCode": "il", "Country_Name":"Israel","currencyCode":"ILS"},{"countryCode": "gr","Country_Name":"Greece","currencyCode":"EUR"},{"countryCode": "cz","Country_Name":"Czechia","currencyCode":"CZK"},{"countryCode": "se","Country_Name":"Sweden","currencyCode":"SEK"},{"countryCode": "ch","Country_Name":"Switzerland","currencyCode":"CHF"},{"countryCode": "lu","Country_Name":"Poland","currencyCode":"EUR"},{"countryCode": "pt", "Country_Name":"Portugal","currencyCode":"EUR"},{"countryCode": "dk","Country_Name":"Denmark","currencyCode":"DKK"},{"countryCode": "nl","Country_Name":"Netherlands","currencyCode":"EUR"}, {"countryCode": "ru","Country_Name":"Russia","currencyCode":"RUB"}, {"countryCode": "vn","Country_Name":"Vietnam","currencyCode":"VND"},{"countryCode": "th","Country_Name":"Thailand","currencyCode":"THB"},{"countryCode": "kr", "Country_Name":"South Korea","currencyCode":"KRW"},{"countryCode": "ph","Country_Name":"Philippines","currencyCode":"PHP"},{"countryCode": "my","Country_Name":"Malaysia","currencyCode":"MYR"},{"countryCode": "jp","Country_Name":"Japan","currencyCode":"JPY"},{"countryCode": "id","Country_Name":"Indonesia","currencyCode":"RP"},{"countryCode": "sg","Country_Name":"Singapore","currencyCode":"USD"},{"countryCode": "hk","Country_Name":"Hong Kong","currencyCode":"USD"},{"countryCode": "ma","Country_Name":"Morocco","currencyCode":"DH"},{"countryCode": "cn","Country_Name":"China","currencyCode":"CNY"},{"countryCode":"AED","countryName":"United Arab Emirates","currencyCode":"DHS","currencySymbol":"DHS"},{"countryCode":"DE","countryName":"Albania","currencyCode":"Lek","currencySymbol":"Lek"},{"countryCode":"IT","countryName":"Italy","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"ES","countryName":"Spain","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"us","countryName":"United States","currencyCode":"USD","currencySymbol":"$"},{"countryCode":"PT","countryName":"Portugal","currencyCode":"EUR","currencySymbol":"€"},{"countryCode":"GB","countryName":"United Kingdom","currencyCode":"GBP","currencySymbol":"£"},{"countryCode":"FR","countryName":"France","currencyCode":"EUR","currencySymbol":"€"}]'

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
            callback=self.main_page,
            headers=rotate_headers())

    @inline_requests
    def main_page(self, response):
        url = f'https://www.shopdorsey.com/collections.json?limit=250'
        page = 1
        try:
            country_request = scrapy.Request(url, headers=self.headers, dont_filter=True)
            target_response = yield country_request
            if target_response.status == 200:
                self.get_target_urls(target_response, url, page)
            else:
                self.log(f"Received Response for URL: {target_response.status_code}")
        except Exception as e:
            self.log(f"Received all_target_urls Response: {e}")

        target_urls_list = list(set(self.all_target_urls))
        for link in target_urls_list:
            if link:
                try:
                    updated_link = f'{link}/products.json?limit=250'
                    page_counter = 1
                    req = scrapy.Request(updated_link, headers=rotate_headers(), dont_filter=True)
                    product_response = yield req
                    if product_response.status == 200:
                        self.parse(product_response, updated_link, page_counter)
                    else:
                        self.log(f"Received Response for URL: {product_response.status}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {updated_link}: {e}")

        logging.info(f'Total Sku of Shopdorsey : {len(self.sku_mapping)}')
        for sku_id, product_info in self.sku_mapping.items():
            product_url = product_info.get('product_url')
            materials = product_info.get('materials')
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'material_str': materials, 'sku_id' : sku_id}
            )

    def get_target_urls(self, response, link, page_counter):
        collections_data = response.json()
        all_collections = collections_data.get('collections')
        for collection in collections_data.get('collections'):
            collection_title = collection['title']
            collection_handle = collection['handle']
            self.log(f"Processing collection: {collection_title} (Handle: {collection_handle})")
            products_url = f'https://www.shopdorsey.com/collections/{collection_handle}'
            if "returns" not in products_url and "ship" not in products_url and "gift-card" not in products_url and "order" not in products_url and "pages" not in products_url and "ready" not in products_url and "body" not in products_url:
                self.all_target_urls.append(products_url)
        if all_collections is not None and len(all_collections) > 0:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}&page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))
                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.get_target_urls(product_response, link, counter)

            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")
        else:
            print("No more products found. Stopping pagination.")
            self.logger.info("No more products found. Stopping pagination.")

    def find_sku_by_variant_id(self, response):
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data:
                    sku = json_data.get("sku")
                    return sku
            except Exception as e:
                print("Error in find_sku_by_variant_id:", e)

    def parse(self, response, link, page_counter):
        sku_id = ''
        products_data = json.loads(response.text)
        all_products = products_data.get('products')
        for product in products_data.get('products'):
            product_handle = product['handle']
            variants = product.get('variants')
            options = product.get('options')
            metal_position = None
            metal_key = ''
            metal_keywords = ['Metal', 'Material']
            metal_set = set()
            for index, option in enumerate(options, start=1):
                if option["name"] in metal_keywords:
                    metal_position = index
                    break
            materials = ''
            if metal_position:
                metal_key = f"option{metal_position}"
                for variant in variants:
                    option = variant.get(metal_key)
                    id = variant.get("id")
                    sku_str = variant.get("sku")
                    if '-' in sku_str:
                        sku_id = sku_str.rsplit("-", 1)[0]
                    if option not in metal_set:
                        metal_set.add(option)
                        materials = option
                        product_url = f'/products/{product_handle}?variant={id}'
                        self.get_all_sku_mapping(product_url, sku_id, materials)

            else:
                if variants:
                    variant = variants[0]
                    sku_id = variant.get('sku')
                    product_url = f'/products/{product_handle}'
                    self.get_all_sku_mapping(product_url, sku_id, materials)

        if all_products is not None and len(all_products) > 30:
            try:
                counter = int(page_counter) + 1
                next_page_url = f'{link}&page={counter}'
                print(f"Next Page URL: {next_page_url}")
                self.logger.info(f"Next Page URL: {next_page_url}")

                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([next_page_url], self.proxy_cycle, self.headers))

                for result in results:
                    if result:
                        product_response = TextResponse(url=next_page_url, body=result, encoding='utf-8')
                        self.parse(product_response, link, counter)

            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")
        else:
            print("No more products found. Stopping pagination.")
            self.logger.info("No more products found. Stopping pagination.")

    def get_all_sku_mapping(self, product_url, sku_id, materials):
        try:
            if product_url and "/en" in product_url:
                existing_url = self.sku_mapping.get(sku_id)
                if existing_url and "/en" not in existing_url:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'materials': materials}
                elif sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'materials': materials}
            elif product_url and "/en" not in product_url:
                if sku_id not in self.sku_mapping:
                    self.sku_mapping[sku_id] = {'product_url': product_url, 'materials': materials}
        except Exception as e:
            self.log(f"Error in all_sku_mapping : {e}")

    @inline_requests
    def parse_product(self, response, product_url, material_str, sku_id):
        content = {}
        specification = {}
        brand = ''
        color = ''
        size_dimensions = []
        stone = ''
        ProductVariants = response.css("div.ProductForm__Variants>.ProductForm__Option.ProductForm__Option--labelled")
        for ProductFormVariants in ProductVariants:
            product_lable_name = ProductFormVariants.css("span.ProductForm__Label::text").get().strip()
            if "metal" in product_lable_name.lower():
                material = ProductFormVariants.css("ul.SizeSwatchList.HorizontalList.HorizontalList--spacingTight>li.HorizontalList__Item>label.SizeSwatch.utility::text").getall()
                if material:
                    materials = ' , '.join(material).strip()
            elif "material" in product_lable_name.lower():
                material = ProductFormVariants.css("ul.SizeSwatchList.HorizontalList.HorizontalList--spacingTight>li.HorizontalList__Item>label.SizeSwatch.utility::text").get()
                if material:
                    materials = material.strip()
            elif "stone" in product_lable_name.lower():
                stone = ProductFormVariants.css("ul.SizeSwatchList.HorizontalList.HorizontalList--spacingTight>li.HorizontalList__Item>label.SizeSwatch.utility::text").get()

        colors = response.css(".ColorSwatchList.HorizontalList.HorizontalList--spacingTight > li.HorizontalList__Item > a::text").getall()
        if colors:
            color = ' '.join(color.strip() for color in colors)
        sku_long_description = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data:
                    # sku_id = json_data.get("sku")
                    brand = json_data.get("brand").get("name")
                    sku_long_description = json_data.get("description")

            except Exception as e:
                print("Error in collect_specification_info:", e)

        patterns = {
            "Size": r"Size:\s*(.+)",
            "Stone Color": r"Stone Color:\s*(.+)",
            "Band Width": r"Band Width:\s*(.+)",
            "Stone Clarity": r"Stone Clarity:\s*(.+)",
            "Stone Size": r"Stone Size:\s*(.+)",
            "Chain Length": r"Chain Length:\s*(.+)",
            "Closure": r"Closure:\s*(.+)",
            "Stone Shape": r"Stone Shape:\s*(.+)",
            "Stone Type": r"Stone Type:\s*(.+)",
            "Top to bottom length": r"Top to bottom length:\s*(.+)",
            "Medium": r"Medium:\s*(.+)",
            "Large": r"Large:\s*(.+)"

        }

        for key, pattern in patterns.items():
            match = re.search(pattern, sku_long_description)
            if match:
                size_dimensions.append(key+":" +match.group(1).strip())

        list_img = response.css("div.Product__SlideItem.Product__SlideItem--image.Carousel__Cell>.AspectRatio.AspectRatio--withFallback>img::attr(src)").getall()
        content_info = self.collect_content_information(response, materials)
        if content_info:
            content["en"] = {
                "sku_link": response.url,
                "sku_title": content_info["sku_title"],
                "sku_short_description": content_info["sku_short_description"],
                "sku_long_description": content_info["sku_long_description"]
            }

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode')
            currencyCode = item.get("currencyCode")
            url = f'{self.base_url}{product_url}?lang=en&country={country_code.upper()}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 200:
                specification_info = self.collect_specification_info(resp, sku_id, country_code, currencyCode)
                if specification_info:
                    specification[country_code.lower()] = specification_info
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = Request(url, headers=self.headers, dont_filter=True)
                country_resp = yield req
                if country_resp.status == 200:
                    specification_info = self.collect_specification_info(country_resp, sku_id, country_code, currencyCode)
                    if specification_info:
                        specification[country_code.lower()] = specification_info
            else:
                self.log(f"RECEIVED 404 Response for URL: {resp.url}")

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

        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        domain, domain_url = self.extract_domain_domain_url(response.url)
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = brand
        item['product_badge'] = ''
        item['collection_name'] = ''
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = color
        item['main_material'] = material_str
        item['secondary_material'] = stone
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response, materials):
        sku_title = ''
        sku_short_description = ''
        sku_long_descriptions = ''
        sku_title = response.css('h1.ProductMeta__Title::text').get()
        sku_short_description = response.css('div.Rte > p::text').get()
        try:
            if not sku_short_description:
                sku_short_description = response.css('div.Rte > p > span::text').get()
            first_div = response.xpath('(//div[@class="ProductMeta__AccordionDescription"])[1]')
            description_paragraphs = first_div.css('p::text').getall()
            sku_long_description = " ".join(desc.strip() for desc in description_paragraphs if desc.strip())
            sku_long_descriptions = f"{sku_short_description}{sku_long_description} {materials}"

        except Exception as e:
            self.log(f'Error content_information data not correct{e}')
        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_descriptions
        }


    def collect_specification_info(self, response, sku_id, country_code, currency_code):
        base_price = ''
        availability = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        active_price = ''
        size_available = []
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_content in script_tag_content:
            try:
                json_data = json.loads(script_content)
                if "offers" in json_data:
                    offers = json_data["offers"]
                    for offer in offers:
                        if "sku" in offer and sku_id in offer["sku"]:
                            price = offer.get("price")
                            base_price = str(price)
                            availability = offer.get("availability")
                            break

            except Exception as e:
                print("Error in collect_specification_info:", e)
        ProductVariants = response.css("div.ProductForm__Variants>.ProductForm__Option.ProductForm__Option--labelled")
        try:
            for ProductFormVariants in ProductVariants:
                product_lable_name = ProductFormVariants.css("span.ProductForm__Label::text").get().strip()
                if "size" in product_lable_name.lower():
                    sizes = ProductFormVariants.css(
                        ".SizeSwatchList.HorizontalList.HorizontalList--spacingTight>li.HorizontalList__Item>label.SizeSwatch.utility::text").getall()
                    for size in sizes:
                        size_available.append(size.strip())

            shipping_lead_times_list = []
            Product_metas = response.css("div.ProductMeta__AccordionField")
            for Product_meta in Product_metas:
                product_lable_name = Product_meta.css("div.ProductMeta__AccordionTitle::text").get()

                if product_lable_name and "shipping and returns" in product_lable_name.lower():
                    shipping_texts = Product_meta.css("div.ProductMeta__AccordionDescription > p::text").getall()

                    shipping_lead_times_list.extend(text.strip() for text in shipping_texts if text.strip())

            if shipping_lead_times_list:
                shipping_lead_time = " ".join(shipping_lead_times_list)
                print(f"Shipping Information: {shipping_lead_time}")
            else:
                print("No shipping information found.")
        except Exception as e:
            print("Exception in shipping_lead_time",e)

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": "en",
            "domain_country_code": country_code.lower(),
            "currency": currency_code if currency_code else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": active_price if active_price else base_price,
            "active_price": active_price if active_price else base_price,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            "marketplace_retailer_name": 'shopdorsey',
            "condition": "NEW",
            "reviews_rating_value": 0.0,  # Use a default value, adjust as needed
            "reviews_number": 0,  # Use a default value, adjust as needed
            "size_available": size_available if size_available else [],
            "sku_link": response.url if response.url else 'NA',
        }

    def check_product_availability(self, availability):
        try:
            if availability:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "NOT AVAILABLE IN STORES"
                return "No", out_of_stock_text
        except Exception as e:
            return "No" "NOT AVAILABLE IN STORES"

