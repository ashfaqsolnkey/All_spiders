from itertools import cycle
from urllib.parse import urljoin
import cloudscraper
import scrapy
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from PIL import Image
import time, datetime, re, tldextract, uuid, logging, os, requests,json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class AgathaSpider(scrapy.Spider):
    name = "agatha"
    sku_mapping = {}
    target_urls = []
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://www.agatha."
    REDIRECT_ENABLED = True
    handle_httpstatus_list = [430, 500, 403, 404, 301, 302]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    directory = get_project_settings().get("FILE_PATH")
    spec_mapping = '[{"countryCode": "gb", "url_countryCode": "com/en_GB", "currencyCode": "EUR", "language":"en"}, {"countryCode": "fr", "url_countryCode": "fr/fr_FR", "currencyCode": "EUR", "language":"fr"}, {"countryCode": "es", "url_countryCode": "es/es_ES", "currencyCode": "EUR", "language":"es"}]'

    if not os.path.exists(directory):
        os.makedirs(directory)

    logs_path = os.path.join(directory, today + "_" + name + ".log")
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    start_urls = "https://www.agathaparis.com/en_GB"

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
        baseUrl = 'https://www.agathaparis.'
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            try:
                proxy = next(self.proxy_cycle)
                country_code = item.get('countryCode')
                url_country_code = item.get('url_countryCode')
                if 'gb' == country_code:
                    country_url = f'{baseUrl}{url_country_code}'
                else:
                    country_url = f'{self.base_url}{url_country_code}'
                country_response = requests.get(country_url, headers=rotate_headers())
                target_response = TextResponse(url='', body=country_response.text, encoding='utf-8')
                self.get_target_urls(target_response, country_url)
            except Exception as e:
                self.log(f"Error occurred while processing URL {country_url}: {e}")

        for link in self.all_target_urls:
            try:
                proxy = next(self.proxy_cycle)
                url = response.urljoin(link)
                resp = requests.get(url, headers=rotate_headers())
                if resp.status_code == 200:
                    list_product_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                    self.parse(list_product_response,url)
                else:
                    self.log(f"Received Response for URL: {resp.status_code}")
            except Exception as e:
                self.log(f"Error occurred while processing URL {link}: {e}")

        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url}
            )

    def get_target_urls(self, response, base_url):
        target_urls = response.css('.c-subdropdown__list>li>a::attr(href)').getall()
        target_urls_list = list(set(target_urls))
        for link in target_urls_list:
            if link not in self.all_target_urls:
                absolute_url = urljoin(base_url, link)
                self.all_target_urls.append(absolute_url)

    def parse(self, response, base_url):
        productUrls = response.css('.c-product-tile')
        for product_element in productUrls:
            product_url = product_element.css('.c-product-tile__name-link::attr(href)').get()
            absolute_url = urljoin(base_url, product_url)
            sku_id = product_element.css('::attr(data-pid)').get()
            self.get_all_sku_mapping(absolute_url, sku_id)

        next_page_button = response.css('button.c-btn-primary[data-action="show-more"]')
        if next_page_button:
            next_page_url = next_page_button.attrib.get('data-url')
            if next_page_url:
                try:
                    proxy = next(self.proxy_cycle)
                    next_page_resp = requests.get(next_page_url, headers=rotate_headers())
                    if next_page_resp.status_code == 200:
                        product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                        self.parse(product_response, next_page_url)
                except Exception as e:
                    self.log(f"Error next_page: {e}")

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
    def parse_product(self, response, product_url):
        if response.status in [301, 302]:
            redirected_url = response.headers.get('Location').decode('utf-8')
            url = response.urljoin(redirected_url)
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                headers=rotate_headers(),
                dont_filter=True,
                cb_kwargs={'product_url': product_url}
            )
            return

        list_img = []
        image_urls = response.css('div.picture-container picture  img.lazyload::attr(data-src)').getall()
        img_image_url = response.css('div.picture-container picture img::attr(src)').get()
        list_img.append(img_image_url)
        for image in image_urls:
            list_img.append(image)
        productUrls = product_url.split('/')
        url_without_code = "/".join(productUrls[4:])
        content = {}
        specification = {}
        sku_id = ''
        brand = ''
        baseUrl = 'https://www.agathaparis.'
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    sku_id = json_data.get('sku')
                    break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON Offers: {e}")

        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode')
                currency_code = item.get('currencyCode')
                url_country_code = item.get('url_countryCode')
                language = item.get('language')
                if country_code == 'gb':
                    country_product_url = f'{baseUrl}{url_country_code}/{url_without_code}'
                else:
                    country_product_url = f'{self.base_url}{url_country_code}/{url_without_code}'
                country_req = scrapy.Request(country_product_url, headers=rotate_headers(), dont_filter=True)
                country_resp = yield country_req
                if country_resp.status == 404:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
                elif country_resp.status in [301, 302]:
                    redirected_url = country_resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    try:
                        proxy = next(self.proxy_cycle)
                        scraper = cloudscraper.create_scraper()
                        country_response = scraper.get(url)
                        resp = TextResponse(url='', body=country_response.text, encoding='utf-8')
                        content_info_content = self.collect_content_information(resp)
                        content_info_specification = self.collect_specification_info(resp, country_code, url_country_code, country_product_url)
                    except Exception as e:
                        self.log(f"Error occurred while processing URL {url}: {e}")

                    if not content_info_specification.get("base_price") or "sku_title" not in content_info_content:
                        self.log(f"SKU title or base price not available for country '{country_code}' at URL: {country_product_url}")
                    else:
                        specification_info = self.collect_specification_info(resp, country_code, currency_code,  country_product_url)
                        specification[country_code] = specification_info
                        content[language] = {
                            "sku_link": f'{country_product_url}',
                            "sku_title": content_info_content["sku_title"],
                            "sku_short_description": content_info_content["sku_short_description"],
                            "sku_long_description": content_info_content["sku_long_description"]
                        }
                else:
                    specification_info = self.collect_specification_info(country_resp, country_code, currency_code, country_product_url)
                    specification[country_code] = specification_info
                    content_info = self.collect_content_information(country_resp)
                    content[language] = {
                        "sku_link": f'{country_product_url}',
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }

        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')

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
                            res = requests.get(url_pic)
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
        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        product_badge = response.css('.c-sticker-generic-4::text').get() or ''

        size_dimensions = []
        product_color = ''
        main_material = ''
        secondary_material = []
        product_details = response.css(".c-product__attributes__list>.c-product__attributes__item")
        dim_list = ["Weight", "Width", "Length", "Height", "Depth", "Diameter", "Longitud", "Poids"]
        sec_material = ["Metal", "Stone", "Métal"]
        for attribute in product_details:
            label = attribute.css('.c-product__attributes__label::text').get().strip()
            value = attribute.css('.c-product__attributes__value::text').get().strip()
            if any(dim_label in label for dim_label in dim_list):
                size_dimensions.append(f"{label} : {value}")
            elif label == "Material":
                main_material = value
            elif label in sec_material:
                secondary_material.append(f" {value}")
            elif label == "Color":
                product_color = value
            elif label == "Couleur":
                product_color = value
        secondary_materials = ''.join(secondary_material)
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = "Agatha"
        item['domain_url'] = domain_url
        item['brand'] = "Agatha Paris"
        item['product_badge'] = product_badge
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = secondary_materials
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        sku_title = ''
        sku_short_description = ''
        sku_long_description = ''
        if script_tag_content:
            try:
                json_data = json.loads(script_tag_content)
                if isinstance(json_data, dict):
                    sku_title = json_data.get('name') or ''
                    sku_short_description = json_data.get('description') or ''
            except json.JSONDecodeError:
                print("Error: JSON content is not valid")
        attribute_items = response.css("li.c-product__attributes__item")
        attributes = {}
        for item in attribute_items:
            label = item.css("span.c-product__attributes__label::text").get()
            value = item.css("span.c-product__attributes__value::text").get()
            attributes[label.strip()] = value.strip()

        attributes_string = '\n'.join([f"{key}: {value}" for key, value in attributes.items()])
        sku_long_description = f"{sku_short_description} {attributes_string}"

        return {
            "sku_title": sku_title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description,
        }

    def collect_specification_info(self, response, country_code, url_country_code, country_product_url):
        sale_price = ''
        currency_code = ''
        availability = ''
        base_price = response.css('.c-price__strike::text').get()
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    price = json_data['offers'].get("price")
                    sale_price = "{:.2f}".format(float(price))
                    currency_code = json_data['offers'].get("priceCurrency")
                    availability = json_data['offers'].get("availability")
                    break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON Offers: {e}")
        if base_price is not None and len(base_price) > 1:
            numeric_price = base_price.strip()
            base_price = numeric_price.replace('€', '')
        else:
            base_price = sale_price

        shipping_info = response.css('.pdp-info-content>ul>li::text').getall()
        shipping_lead_time = []
        shipping_expenses = ''
        seur_expense = ''
        colissimo_expense = ''
        chronopost_expense = ''
        sending_expense = ''
        point_relais_expense = ''
        shipping_lead_time_string = ''
        try:
            for text in shipping_info:
                match = re.match(r'(.+?) (\d{1,2}h)', text)
                if match:
                    shipping_lead_time.append(match.group())
                elif 'SEUR' in text:
                    shipping_lead_time.append(text)
            for info in shipping_info:
                if 'SEUR' in info:
                    seur_expense = 'SEUR'+info
                elif 'Colissimo en 48h' in info:
                    colissimo_expense = 'Colissimo en 48h '+info.split(' ')[3]
                elif 'Chronopost en 24h' in info:
                    chronopost_expense = 'Chronopost en 24h '+info.split(' ')[3]
                elif 'Point relais' in info:
                    point_relais_expense = 'Point relais'+info.split(' ')[2]
                elif 'SENDING' in info:
                    sending_expense = info
            shipping_expenses = ', '.join(
                filter(None, [seur_expense, colissimo_expense, chronopost_expense, point_relais_expense, sending_expense]))
        except Exception as e:
            print(e)
        for lead_time in shipping_lead_time:
            shipping_lead_time_string += lead_time + ","  # Append each lead time followed by a space
        shipping_lead_time_string = shipping_lead_time_string.strip()
        size = response.css('.c-product__attributes__label:contains(Size) + .c-product__attributes__value::text').get()
        sizes = size.strip() if size else ''

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": country_code,
            "domain_country_code": country_code,
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": '',
            "reviews_number": '',
            "shipping_lead_time": shipping_lead_time_string,
            "shipping_expenses": shipping_expenses,
            "size_availability": sizes,
            "sku_link": country_product_url
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
