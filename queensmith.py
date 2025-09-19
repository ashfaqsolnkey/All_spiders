from itertools import cycle
import scrapy
from inline_requests import inline_requests
from scrapy import Request
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class Queensmith(scrapy.Spider):
    name = "queensmith"
    base_url = "https://www.queensmith.co.uk"
    sku_mapping = {}
    all_target_urls = []
    main_url = ""
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    handle_httpstatus_list = [430, 403, 443]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    directory = get_project_settings().get("FILE_PATH")

    if not os.path.exists(directory):
        os.makedirs(directory)

    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    start_urls = "https://www.queensmith.co.uk/vashi"

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
            headers=rotate_headers(),
            dont_filter=True
        )

    def country_base_url(self, response):
        fetched_urls = response.css('link[rel="canonical"]::attr(href)').getall()
        country_urls_list = list(set(fetched_urls))
        for url in country_urls_list:
            self.main_url = url
            proxy = next(self.proxy_cycle)
            country_response = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
            target_response = TextResponse(url='', body=country_response.text, encoding='utf-8')
            self.get_target_urls(target_response)

        for link in self.all_target_urls:
            try:
                proxy = next(self.proxy_cycle)
                resp = requests.get(link, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                if resp.status_code == 200:
                    list_product_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                    self.parse(list_product_response)
                else:
                    self.log(f"Received Response for URL: {resp.status_code}")
            except Exception as e:
                self.log(f"Received all_target_urls Response: {e}")

        print(self.sku_mapping)
        for sku_id, product_info in self.sku_mapping.items():
            material = product_info.get('material')
            product_url = product_info.get('product_url')
            yield scrapy.Request(
                url=product_url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url, 'sku_id': sku_id, 'material': material}
            )

    def get_target_urls(self, response):
        add_category = ['rings/engagement-rings', 'rings/wedding-rings', 'jewellery/earrings']
        for category in add_category:
            product_urls_api = f"https://www.queensmith.co.uk/actions/products/{category}"
            self.all_target_urls.append(product_urls_api)

    def parse(self, response):
        product_urls = []
        material = ''
        text_data = response.text
        data = json.loads(text_data)
        json_data = data['products']
        for materials in json_data:
            urls = materials['metals']
            for metal, ring_info in urls.items():
                material = metal
                product_urls.append(ring_info['url'])

        for product_url in product_urls:
            get_sku_url = product_url
            proxy = next(self.proxy_cycle)
            sku_resp = requests.get(get_sku_url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
            if sku_resp.status_code == 200:
                sku_response = TextResponse(url='', body=sku_resp.text, encoding='utf-8')
                sku_id = self.sku_get(sku_response)
                self.get_all_sku_mapping(product_url, sku_id, material)

    def get_all_sku_mapping(self, product_url, sku_id, material):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'material': material}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'material': material}
        elif product_url and "/en" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'material': material}

    def sku_get(self, response):
        sku_script_content = response.css('script[type="application/ld+json"]::text').get()
        try:
            if sku_script_content:
                json_data = json.loads(sku_script_content)
                sku = json_data['@graph'][0]['sku']
                return sku
        except json.JSONDecodeError:
            self.log('Error decoding JSON data')

    @inline_requests
    def parse_product(self, response, product_url, sku_id, material):
        if response.status == 200:
            content = {}
            specification = {}
            item_brand = ''
            mpn = ''
            script_content = response.css('script[type="application/ld+json"]::text').get()
            try:
                if script_content:
                    json_data = json.loads(script_content)
                    items = json_data['@graph'][0]
                    item_brand = items["brand"].get("name")
                    mpn = items['mpn']
            except json.JSONDecodeError:
                self.log('Error decoding JSON data')

            if response.status == 200:
                content_info = self.collect_content_information(response)
                content['en'] = {
                    "sku_link": content_info["sku_link"],
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }
            elif response.status in [301, 302]:
                proxy = next(self.proxy_cycle)
                redirected_url = response.headers.get(b'Location').decode('utf-8')
                url = response.urljoin(redirected_url)
                req = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                resp = TextResponse(url='', body=req.text, encoding='utf-8')
                if resp.status == 200:
                    content_info = self.collect_content_information(resp)
                    content['en'] = {
                        "sku_link": content_info["sku_link"],
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            else:
                self.log(f"RECEIVED 404 Response for URL: {response.url}")
            try:
                country_code = "uk"
                req = Request(product_url, headers=rotate_headers(),  dont_filter=True)
                resp = yield req
                if resp.status == 200:
                    specification_info = self.collect_specification_info(resp, country_code)
                    specification[country_code] = specification_info
                elif resp.status in [301, 302]:
                    proxy = next(self.proxy_cycle)
                    redirected_url = resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = requests.get(url, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
                    country_resp = TextResponse(url='', body=req.text, encoding='utf-8')
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, country_code)
                        specification[country_code.lower()] = specification_info
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

            list_img = []
            list_img_without_http = response.css('.md\:block.w-8\/12 img::attr(src)').getall()
            for images in list_img_without_http:
                img = images.split("?")[0]
                list_img.append(img)

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

            time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            domain, domain_url = self.extract_domain_domain_url(response.url)
            metal_colour = material
            size_dimensions = []
            sizes = response.css('.grid.gap-5.grid-cols-6.pb-20 a::text').getall()
            if sizes:
                for size in sizes:
                    dimensions = size.strip()
                    size_dimensions.append(dimensions)
            else:
                size_dimensions = response.css('a.duration-default.w-32.h-32.relative::attr(title)').getall()

            item = ProductItem()
            item['date'] = time_stamp
            item['domain'] = domain
            item['domain_url'] = domain_url
            item['brand'] = item_brand
            item['mpn'] = mpn
            item['manufacturer'] = self.name
            item['product_badge'] = ''
            item['sku'] = sku_id
            item['sku_color'] = metal_colour
            item['main_material'] = material
            item['secondary_material'] = ''
            item['image_url'] = product_images_info
            item['size_dimensions'] = size_dimensions
            item['content'] = content
            item['specification'] = specification
            yield item

    def collect_content_information(self, response):
        sku_title = ""
        sku_url = ""
        short_description = ""
        sku_long_description = ""
        long_description = ""
        description_strip = response.css('.space-y-10.text-para-small.text-navy div.richtext p::text').getall()
        if description_strip:
            for text in description_strip:
                long_description = "".join(text.strip())
        description_short = response.css('.space-y-10.text-para-small.text-navy div.richtext::text').get(default="")
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            sku_details = json_data['@graph'][0]
            sku_title = sku_details['name']
            sku_url = sku_details['mainEntityOfPage']
            json_description = sku_details['description']
            short_description = json_description.strip() if json_description else ""

            sku_long_description = f"{short_description}{description_short} {long_description}"

        return {
            "sku_title": sku_title,
            "sku_link": sku_url,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, country_code):
        sale_price = ''
        availability = ''
        priceCurrency = ''
        difference_days = ''
        script_content = response.css('script[type="application/ld+json"]::text').get()
        try:
            if script_content:
                json_data = json.loads(script_content)
                sku_details = json_data['@graph'][0]
                priceCurrency = sku_details["offers"].get("priceCurrency")
                sale_price = sku_details["offers"].get("price")
                availability = sku_details["offers"].get("availability")
        except Exception as e:
            logging.error(f"Error processing image: {e}")
        sizes = response.css('.grid.gap-5.grid-cols-7 button::text').getall()
        type_of_category = ''
        days = ''
        leadtime_text = response.css('.sticky.top-120.space-y-20 div[x-data*=leadDate]::attr(x-data)').get()
        text_word = leadtime_text.split(',')
        for split_text in text_word:
            text = split_text.split(':')
            if 'days' in text[0]:
                days = text[1]
            elif 'type' in text[0]:
                type_of_category = re.findall('[a-zA-Z]+', text[1])[0]
        shipping_api = f'https://www.queensmith.co.uk/actions/lead-timer/dates?days={days}&type={type_of_category}'
        proxy = next(self.proxy_cycle)
        shipping_resp = requests.get(shipping_api, headers=rotate_headers(), proxies={'http': proxy, 'https': proxy})
        if shipping_resp.status_code == 200:
            date_str = shipping_resp.text.strip().replace('"', '')
            date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            try:
                date_to_compare = datetime.datetime.strptime(date_str, "%d %B %Y").date()
                today = datetime.datetime.now().date()
                difference_days = date_to_compare - today
            except ValueError as e:
                print(f"Error parsing date: {e}")
        shipping_expenses = ''
        shipping_lead_time = f"{difference_days.days} Days"
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": 'en',
            "domain_country_code": country_code,
            "currency": priceCurrency if priceCurrency else 'default_currency_code',
            "base_price": sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "NA",
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            "condition": "NEW",
            "reviews_rating_value": 'NA',  # Use a default value, adjust as needed
            "reviews_number": 'NA',  # Use a default value, adjust as needed
            "size_available": sizes if sizes else [],
            "sku_link": response.url if response.url else 'NA',
        }

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Product Out of Stock"
                return "No", out_of_stock_text
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return
