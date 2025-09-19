import scrapy
from inline_requests import inline_requests
from scrapy import Request
from urllib.parse import urlencode
from itertools import cycle
from scrapy.utils.project import get_project_settings
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

class SuarezSpider(scrapy.Spider):
    name = "suarez"
    products = []
    all_target_urls = []
    sku_mapping = {}
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://int.joyeriasuarez.com"
    handle_httpstatus_list = [430, 403, 443, 404]
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    start_urls = "https://int.joyeriasuarez.com/en/home"

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
        )

    @inline_requests
    def country_base_url(self, response):
        fetched_urls = response.css('link[rel="alternate"]::attr(href)').getall()
        en_urls = [url for url in fetched_urls if "en" in url]
        country_urls_list = list(set(en_urls))
        for url in country_urls_list:
            req = Request(url, headers= self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            else:
                self.get_target_urls(resp)
        params = {'sz': 9999}
        for link in self.all_target_urls:
            product_url = response.urljoin(link)
            if '?' in product_url:
                url = product_url + '&' + urlencode(params)
            else:
                url = product_url + '?' + urlencode(params)
            request = scrapy.Request(url, headers=self.headers, dont_filter=True)
            resp = yield request
            if resp.status == 200:
                self.parse(resp)
            else:
                self.log(f"Received Response for URL: {resp.status}")
        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url}
            )

    def get_target_urls(self, response):
        if response:
            target_url = response.css("li.dropdown-item.suarez-submenu_item.dropdown>a::attr(href)").getall()
            filtered_urls = response.css('li.content-asset-menu.third-submenu>a::attr(href)').getall()
            product_urls = [url for url in filtered_urls if url != "javascript:void(0);" and not url.startswith('https://')]
            combined_urls = list(set(target_url + product_urls))
            for link in combined_urls:
                if link not in self.all_target_urls and "universe" not in link and "Search-Results" not in link and "cufflinks" not in link:
                    self.all_target_urls.append(link)

    def parse(self, response):
        sku_id = ''
        product_elements = response.css('div.product-content-tiles')
        for product_ele in product_elements:
            product_url = product_ele.css('.pdp-link a::attr(href)').get()
            product_element = product_ele.css('div.product[data-pid]')
            if product_element:
                sku_id = product_element.attrib['data-pid']
            self.get_all_sku_mapping(product_url, sku_id)

    def get_all_sku_mapping(self, product_url, sku_id):
        if product_url and "/en" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if not existing_url or "/en" not in existing_url:
                self.sku_mapping[sku_id] = product_url
        elif product_url and "en/" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url

    @inline_requests
    def parse_product(self, response, product_url):
        url_without_language = ''
        url_parts = product_url.split("/")
        if '/en/' in product_url:
            url_without_language = "/".join(url_parts[2:])
        else:
            url_without_language = "/".join(url_parts[2:])
        specification = {}
        content = {}
        sku_id = ''
        main_material = ''
        mpn = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            sku_id = json_data.get('sku')
            sku_title = json_data.get("name")
            mpn = json_data.get('mpn')
        else:
            sku_id = response.css('.product-id ::text').get()
            sku_title = response.css('.product-name::text').get()

        jewelry_materials = ["10K Yellow Gold", "14K Yellow Gold", "18K Yellow Gold","10K Rose Gold", "14K Rose Gold", "18K Rose Gold","10K White Gold", "14K White Gold", "18K White Gold","24K Gold", "Gold", "Silver", "Platinum", "Palladium","Titanium", "Stainless Steel", "Copper", "Brass", "Bronze","Rhodium", "Sterling Silver", "Pearl", "Diamond", "Ruby","Sapphire", "Emerald", "Amethyst", "Topaz", "Opal","Aquamarine", "Garnet", "Citrine", "Peridot", "Tourmaline","Tanzanite", "Jade", "Onyx", "Turquoise", "Coral", "Amber","Lapis Lazuli", "Quartz", "Moonstone", "Morganite", "Agate","Hematite", "Malachite", "Mother of Pearl", "Shell", "Ivory","Resin", "Wood", "Leather", "Enamel", "Glass", "Crystal","Obsidian", "Zircon", "Cubic Zirconia", "Rutile", "Labradorite", "Rhodolite", "Spinel", "Alexandrite"]
        for jewelry_material in jewelry_materials:
            if jewelry_material.lower() in sku_title.lower():
                main_material = jewelry_material

        content_info = self.collect_content_information(response)
        content['en'] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        url = f'{self.base_url}/es_US/{url_without_language}'
        req = Request(url, headers=rotate_headers(), dont_filter=True)
        resp = yield req
        content_info = self.collect_content_information(resp)
        content['es'] = {
            "sku_link": resp.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        spec_mapping = '[{"countryCode": "us", "url_countryCode": "en","currencyCode": "EUR"},{"countryCode": "ch", "url_countryCode": "en_CH","currencyCode": "EUR"},{"countryCode": "gb", "url_countryCode": "en_GB","currencyCode": "EUR"},{"countryCode": "ar", "url_countryCode": "en_AR","currencyCode": "EUR"},{"countryCode": "in", "url_countryCode": "en_IN","currencyCode": "EUR"},{"countryCode": "jp", "url_countryCode": "en_JP","currencyCode": "EUR"},{"countryCode": "my", "url_countryCode": "en_MY","currencyCode": "EUR"},{"countryCode": "nz", "url_countryCode": "en_NZ","currencyCode": "EUR"},{"countryCode": "pe", "url_countryCode": "en_PE","currencyCode": "EUR"},{"countryCode": "qa", "url_countryCode": "en_QA","currencyCode": "EUR"},{"countryCode": "kr", "url_countryCode": "en_KR","currencyCode": "EUR"},{"countryCode": "za", "url_countryCode": "en_ZA","currencyCode": "EUR"},{"countryCode": "sa", "url_countryCode": "en_SA","currencyCode": "EUR"},{"countryCode": "th", "url_countryCode": "en_TH","currencyCode": "EUR"},{"countryCode": "tw", "url_countryCode": "en_TW","currencyCode": "EUR"},{"countryCode": "uy", "url_countryCode": "en_UY","currencyCode": "EUR"},{"countryCode": "ae", "url_countryCode": "en_AE","currencyCode": "EUR"},{"countryCode": "ve", "url_countryCode": "en_VE","currencyCode": "EUR"},{"countryCode": "ma", "url_countryCode": "en_MA","currencyCode": "EUR"},{"countryCode": "cn", "url_countryCode": "en_CN","currencyCode": "EUR"},{"countryCode": "co", "url_countryCode": "en_CO","currencyCode": "EUR"},{"countryCode": "au", "url_countryCode": "en_AU","currencyCode": "EUR"},{"countryCode": "es", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "pt", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "fr", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "at", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "be", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "ca", "url_countryCode": "en_CA","currencyCode": "EUR"},{"countryCode": "cl", "url_countryCode": "en_CL","currencyCode": "EUR"},{"countryCode": "cz", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "de", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "dk", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "gr", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "ie", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "it", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "nl", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "no", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "pl", "url_countryCode": "es/en_US","currencyCode": "EUR"},{"countryCode": "se", "url_countryCode": "es/en_US","currencyCode": "EUR"}]'
        try:
            json_data = json.loads(spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode').lower()
                currency_code = item.get('currencyCode')
                url_countryCode = item.get('url_countryCode')
                if url_countryCode == "es/en_US":
                    new_url = "https://www.joyeriasuarez.com"
                    url = f'{new_url}/{url_countryCode}/{url_without_language}'
                    req = Request(url, headers=rotate_headers(),  dont_filter=True)
                    update = yield req
                    specification_info = self.collect_specification_info(update, country_code, currency_code, url)
                    specification[country_code] = specification_info
                else:
                    url = f'{self.base_url}/{url_countryCode}/{url_without_language}'
                    req = Request(url, headers=rotate_headers(), dont_filter=True)
                    update = yield req
                    specification_info = self.collect_specification_info(update, country_code, currency_code, url)
                    specification[country_code] = specification_info

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return
        size_dimension = []
        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        colection_name = response.css('.colection-name>p>a>span::text').get()
        color = response.css('.attribute-values>span>strong::text').get()
        key = response.css('.attribute-values.quilates span ::text').get()
        if key:
            key_filter = key.replace(':', " ")
            value = response.css('.attribute-values.quilates strong::text').get()
            value_filter = value.replace(',', '.')
            dimension = f'{key_filter}:{value_filter}'
            size_dimension.append(dimension)

        attributes = {}
        attribute_elements = response.css('ul.arisua-attributes li')
        for element in attribute_elements:
            label = element.css('span.label::text').get().strip()
            value = element.css('strong::text').get().strip()
            attributes[label] = value
        secondary_material = attributes.get("piedra principal:")

        list_img = []
        image_urls = response.css('.product-carousel img::attr(src)').extract()
        for image_url in image_urls:
            list_img.append(image_url)
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
                            res = requests.get(url_pic, proxies = {'http': proxy, 'https': proxy})
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

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = colection_name
        item['brand'] = self.name
        item['product_badge'] = ''
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['mpn'] = mpn
        item['sku_color'] = color
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, resp):
        long_description = ''
        sku_title = resp.css('.product-name::text').get()
        full_description = resp.css('div.long-description::text').get()
        if full_description:
            long_description = full_description.strip()
        attributes = {}
        attribute_elements = resp.css('ul.arisua-attributes li')
        for element in attribute_elements:
            label = element.css('span.label::text').get()
            value = element.css('strong::text').get()
            attributes[label.strip()] = value.strip()

        attributes_string = '\n'.join([f"{key}: {value}" for key, value in attributes.items()])
        sku_long_description = f"{long_description} {attributes_string}"
        return {
                "sku_title": sku_title,
                "short_description": long_description,
                "sku_long_description": sku_long_description
            }

    def collect_specification_info(self, resp, country_code, currency_code, url):
        availability_status = ''
        out_of_stock_text = ''
        content = resp.css('#attributes>div>div.content-asset>p::text').get()
        content_ul = resp.css('#attributes>div>div.content-asset>ul>li::text').getall()
        shipping_lead_time = content + " " + " ".join(content_ul)
        shipping_expenses = resp.css('span.ml-3 a::text').get()
        size_1 = resp.css('option[data-available="true"]::text').getall()
        size_available = [item.strip() for item in size_1]
        script_tag_content = resp.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            active_price = json_data["offers"].get("price")
            currency_code = json_data["offers"].get("priceCurrency")
            availability = json_data["offers"].get("availability")
            product_availability = self.check_product_availability(availability)
            availability_status = product_availability[0]
            out_of_stock_text = product_availability[1]
        else:
            active_price = resp.css('span.sales > span.value::attr(content)').get()
            currency_code = 'EUR'
            if not size_available:
                button = resp.css('.button-group.col-12.p-0 button.add-to-cart.btn.btn-primary[disabled]')
                if button:
                    availability_status = 'No'
                    out_of_stock_text = "Product Out of Stock"
                else:
                    availability_status = 'Yes'
                    out_of_stock_text = "AVAILABLE"
        base_price = resp.css('span.strike-through.list > span.value::attr(content)').get() or active_price

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": active_price,
            "active_price": active_price,
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": self.name,
            "condition": "NEW",
            "reviews_rating_value": 0.00,
            "reviews_number": 0.00,
            "size_available": size_available,
            "sku_link": url
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
