import scrapy
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class Rentta_go(scrapy.Spider):
    name = "Rentta_go"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.renattandgo.com"
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
    start_urls = "https://www.renattandgo.com/en"
    spec_mapping = '[{"countryName" : "Croatia" ,"codeUrl": "en-eu", "countryCode" :"HR", "shipping_charge":"36,5€","shipping_time":" 4 to 8 business days"}, {"countryName" : "Lithuania" ,"codeUrl": "en-eu", "countryCode" :"lt", "shipping_charge":"36,5€","shipping_time":" 4 to 8 business days"}, {"countryName" : "Latvia" ,"codeUrl": "en-eu", "countryCode" :"LV", "shipping_charge":"","shipping_time":""}, {"countryName" : "Slovakia" ,"codeUrl": "en-eu", "countryCode" :"SK", "shipping_charge":"19,9€","shipping_time":" 4 to 8 business days"}, {"countryName" : "Estonia" ,"codeUrl": "en-eu", "countryCode" :"EE", "shipping_charge":"36,5€","shipping_time":" 4 to 8 business days"},{"countryName" : "Spain" ,"codeUrl": "en", "countryCode" :"ES", "shipping_charge":"3.95€","shipping_time":" 2 to 3 business days"}, {"countryName" : "France" , "codeUrl":"en-fr", "countryCode" :"FR",  "shipping_charge":"14,6€","shipping_time":"4-8 business days" },{"countryName" : "Austria" , "codeUrl":"en-aut" , "countryCode" :"AT",  "shipping_charge":"17,5€","shipping_time":"4-8 business days"},{"countryName" : "Finland" , "codeUrl":"en-eu" , "countryCode" :"FI",  "shipping_charge":"36,5€","shipping_time":"4-8 business days"},{"countryName" : "Hungary"  , "codeUrl":"en-eu", "countryCode" :"HU",  "shipping_charge":"36,5€","shipping_time":"4-8 business days" },{"countryName" : "Netherlands" , "codeUrl":"en-nl", "countryCode" :"NL", "shipping_charge":"17,5€","shipping_time":"4-8 business days"}, {"countryName" : "Slovenia" , "codeUrl":"en-eu" , "countryCode" :"SI", "shipping_charge":"19,9€","shipping_time":"4-8 business days" }, {"countryName" : "Belgium" , "codeUrl":"en-be", "countryCode" :"BE", "shipping_charge":"17,5€","shipping_time":"4-8 business days" }, {"countryName" : "Ireland" , "codeUrl":"en-eu", "countryCode" :"IE", "shipping_charge":"19,9€","shipping_time":"4-8 business days" }, {"countryName" : "Poland" , "codeUrl":"en-eu", "countryCode" :"PL", "shipping_charge":"19,9€","shipping_time":"4-8 business days" }, {"countryName" : "Czech Republic" , "codeUrl":"en-eu", "countryCode" :"CZ",  "shipping_charge":"19,9€","shipping_time":"4-8 business days" },{"countryName" : "Germany" , "codeUrl":"en-eu" , "countryCode" :"DE", "shipping_charge":"14,6€","shipping_time":"4-8 business days"},{"countryName" : "Italy" , "codeUrl":"en-eu" , "countryCode" :"IT", "shipping_charge":"17,5€","shipping_time":"4-8 business days"},{"countryName" : "Portugal" , "codeUrl":"en-pt", "countryCode" :"PT", "shipping_charge":"6,5€","shipping_time":"4-8 business days" },{"countryName" : "Sweden" , "codeUrl":"en-eu", "countryCode" :"SE",  "shipping_charge":"19,9€","shipping_time":"4-8 business days"},{"countryName" : "Denmark" , "codeUrl":"en-eu" , "countryCode" :"DK",  "shipping_charge":"19,9€","shipping_time":"4-8 business days"},{"countryName" : "Greece" , "codeUrl":"en-eu" , "countryCode" :"GR", "shipping_charge":"17,5€","shipping_time":"4-8 business days"}, {"countryName" : "Luxembourg"  , "codeUrl":"en-eu" , "countryCode" :"LU", "shipping_charge":"17,5€","shipping_time":"4-8 business days"}, {"countryName" : "Romania" , "codeUrl":"en-eu", "countryCode" :"RO", "shipping_charge":"36,5€","shipping_time":"4-8 business days"}, {"countryName" : "Cyprus" , "codeUrl":"en-eu", "countryCode" :"CY",  "shipping_charge":"36,5€","shipping_time":"4-8 business days"}, {"countryName" : "Bulgaria" , "codeUrl":"en-eu", "countryCode" :"BG",  "shipping_charge":"36,5€","shipping_time":"4-8 business days"} ]'

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
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
            country_code = item.get('countryCode')
            code_url = item.get('codeUrl')
            url = f'{self.base_url}/{code_url}?country={country_code}'
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
        target_urls = response.css(
            '.menu-drawer__menu-item.first.list-menu__item.link.link--text.focus-inset>a::attr(href)').extract()
        link_list = response.css('div.menu-drawer__inner-submenu>ul>li>a::attr(href)').extract()
        target_urls.extend(link_list)
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
        try:
            products = response.css("li.grid__item.scroll-trigger.animate--slide-in")
            if products:
                for item in products:
                    product = item.css("h2.card__heading.h5>a::attr(href)").get()
                    proxy = next(self.proxy_cycle)
                    url = f"{self.base_url}{product}"
                    scraper = cloudscraper.create_scraper()
                    resp = scraper.get(url, headers=self.headers, proxies={'http': proxy, 'https': proxy})
                    if resp.status_code == 200:
                        url_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                        script_tags = url_response.css('script[type="application/ld+json"]::text').getall()
                        for script_tag in script_tags:
                            try:
                                json_data = json.loads(script_tag)
                                if "sku" in json_data:
                                    sku_id = json_data['sku']
                                    self.get_all_sku_mapping(product, sku_id)
                                    break
                            except Exception as e:
                                self.log(f"error occured {e}")
            else:
                print(f"No product in parse {response} ")
        except Exception as e:
            self.log(f"Error occured parse fn{e}")
        try:
            next_page_link = response.css('div#CollectionPagination>a::attr(href)').get()
            if next_page_link:
                next_page_link = f'{self.base_url}{next_page_link}'
                proxy = next(self.proxy_cycle)
                next_page_resp = requests.get(next_page_link, headers=self.headers,
                                              proxies={'http': proxy, 'https': proxy})
                if next_page_resp.status_code == 200:
                    product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                    self.parse(product_response)

        except Exception as e:
            self.log(f"Pagingation {e}")

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
        gtin8 = ''
        gtin13 = ''
        gender = ''
        content = {}
        specification = {}
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    for offer in json_data["offers"]:
                        gtin13 = offer.get('gtin13')
                        break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON Offers: {e}")
        script_content = response.css('script:contains("window.eyefituShopifyOptions")::text').get()
        if script_content:
            json_data_match = re.search(r'window\.eyefituShopifyOptions\s*=\s*(\{.*?\});', script_content, re.DOTALL)
            if json_data_match:
                try:
                    json_string = json_data_match.group(1)
                    if 'gender' in json_string:
                        gender_value = json_string.split('gender:')[1]
                        gender_str = gender_value.split(',')[0]
                        gender = gender_str.replace('"', '')
                except json.JSONDecodeError as e:
                    self.log(f'JSON decode error: {e}')
            else:
                self.log('JSON data not found in the script.')
        else:
            self.log('Script content not found.')
        s_product_url = product_url.split('/', 2)[2:]
        s_product_url = ''.join(s_product_url)
        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        languages = ["es-eu", "en-eu"]
        for language in languages:
            logging.info(f'Processing: {language}')
            url = f'{self.base_url}/{language}/{s_product_url}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            else:
                content_info = self.collect_content_information(resp)
                content[language.split("-")[0]] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["sku_short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode')
            code_url = item.get('codeUrl')
            shipping_charge = item.get('shipping_charge')
            shipping_time = item.get('shipping_time')
            try:
                country_url = f"{self.base_url}/{code_url}/{s_product_url}?country={country_code}"
                proxy = next(self.proxy_cycle)
                country_req = requests.get(country_url, headers=rotate_headers(),
                                           proxies={'http': proxy, 'https': proxy})
                country_resp = TextResponse(url='', body=country_req.text, encoding='utf-8')
                if country_resp.status == 404:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
                elif country_resp.status in [301, 302]:
                    try:
                        redirected_url = country_resp.headers.get('Location').decode('utf-8')
                        url = response.urljoin(redirected_url)
                        proxy = next(self.proxy_cycle)
                        country_response = requests.get(url, proxies={'http': proxy, 'https': proxy})
                        redirected_resp = TextResponse(url='', body=country_response.text, encoding='utf-8')
                        if redirected_resp.status == 200:
                            specification_info = self.collect_specification_info(redirected_resp, country_code,
                                                                                 shipping_charge, shipping_time)
                            specification[country_code.lower()] = specification_info
                    except Exception as e:
                        print(e)
                else:
                    specification_info = self.collect_specification_info(country_resp, country_code, shipping_charge,
                                                                         shipping_time)
                    specification[country_code.lower()] = specification_info

            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

        list_img = []
        picture_sources = response.css(
            '#Slider-Thumbnails-template--23204485628252__main>li>button>img::attr(src)').getall()
        for pictures in picture_sources:
            list_img.append(f'https:{pictures}')

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku
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
        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        size_dimension = []
        material = []
        main_material = ''
        secondary_material = ''
        collection_name = ''
        color_names = response.css('ul.product__colors-list li.product__colors-item a.product__colors-link::attr(title)').get()
        product_color = color_names.split()[0]
        product_detail = response.css('div.accordion__content.rte>p::text').extract()
        for item in product_detail:
            if "%" in item:
                material.append(item)
        if material and len(material) > 1:
            main_material = material[0]
            secondary_material = material[1:]
        else:
            if material:
                main_material = material[0].strip()
                main_material = main_material.replace('\n', ' ').strip()

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_name
        item['brand'] = 'renatta&go'
        item['manufacturer'] = self.name
        item['product_badge'] = ''
        item['gender'] = gender
        item['sku'] = sku
        item['sku_color'] = product_color
        item['gtin8'] = gtin8
        item['gtin13'] = gtin13
        item['main_material'] = main_material
        item['secondary_material'] = ' '.join(secondary_material)
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        title = ''
        description = []
        script_tags = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tags:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    title = json_data['name']
                    description = json_data['description']
            except Exception as e:
                self.log(f"error occured {e}")
        description_parts = description.split('.')
        product_Detail = []
        for desc in description_parts:
            if 'cm' in desc:
                break
            else:
                product_Detail.append(desc)

        sku_short_description = ''.join(product_Detail)
        sku_long_description = f"{title} {''.join(product_Detail)}"
        return {
            "sku_title": title,
            "sku_short_description": sku_short_description,
            "sku_long_description": ''.join(sku_long_description)
        }

    def collect_specification_info(self, resp, country_code, shipping_charge, shipping_time):
        availability = ''
        sale_price = ''
        price = resp.css('span.unit_price_original::text').extract()
        base_price = ''.join(price)
        item_url = ''
        currency_code = ''
        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    sale_price = json_data['offers'][0]['price']
                    currency_code = json_data['offers'][0]["priceCurrency"]
                    availability = json_data['offers'][0]["availability"]
                    item_url = json_data.get('url')
                    break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON Offers: {e}")
        price_string = str(sale_price)
        sale_price = self.extract_price_info(price_string)
        size_available = resp.css('input[name^="Size-1"]::attr(value)').getall()
        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        stock_text = product_availability[1]

        return {
            "lang": country_code.lower(),
            "domain_country_code": country_code.lower(),
            "currency": currency_code,
            "base_price": base_price if base_price else sale_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": '',
            "availability": availability_status,
            "availability_message": stock_text,
            "shipping_lead_time": shipping_time,
            "shipping_expenses": shipping_charge,
            "marketplace_retailer_name": "Rentta_go",
            "condition": "NEW",
            "reviews_rating_value": ' ',
            "reviews_number": ' ',
            "size_available": size_available,
            "sku_link": item_url
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
                stock_text = "AVAILABLE"
                return "Yes", stock_text
            elif "LimitedAvailability" in availability_value:
                stock_text = "AVAILABLE"
                return "Yes", stock_text
            else:
                stock_text = "Temporarily out of stock"
                return "No", stock_text
        except Exception as e:
            return "No"

