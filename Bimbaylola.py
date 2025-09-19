from PIL import Image
from scrapy.utils.project import get_project_settings
from scrapy.selector import Selector
from inline_requests import inline_requests
from urllib.parse import urlencode, urljoin
from itertools import cycle
import aiohttp
import asyncio
from scrapy.http import Request, TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests, json, scrapy
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


async def get_page(session, url, proxy_cycle, bimba_headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=bimba_headers) as response:

                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1

    return None


async def get_all(session, urls, proxy_cycle, bimba_headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle, bimba_headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, bimba_headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=bimba_headers, timeout=timeout) as session:
                data = await get_all(session, urls, proxy_cycle, bimba_headers)
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


class Bimbaylola(scrapy.Spider):
    name = "bimbaylola"
    sku_mapping = {}
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    spec_mapping = '[{"countryCode": "mx", "url_countryCode": "mx_en"},{"countryCode": "cl", "url_countryCode": "cl_es"},{"countryCode": "at", "url_countryCode": "eu_en"},{"countryCode": "be", "url_countryCode": "be_en"},{"countryCode": "bg", "url_countryCode": "eu_en"},{"countryCode": "fr", "url_countryCode": "fr_en"}, {"countryCode": "cy", "url_countryCode": "eu_en"},{"countryCode": "cz", "url_countryCode": "eu_en"},{"countryCode": "dk", "url_countryCode": "eu_en"},{"countryCode": "ec", "url_countryCode": "ec_en"},{"countryCode": "sk", "url_countryCode": "eu_en"},{"countryCode": "fl", "url_countryCode": "eu_en"},{"countryCode": "de", "url_countryCode": "de_en"},{"countryCode": "gr", "url_countryCode": "eu_en"},{"countryCode": "hu", "url_countryCode": "eu_en"},{"countryCode": "ie", "url_countryCode": "eu_en"},{"countryCode": "it", "url_countryCode": "it_en"},{"countryCode": "kr", "url_countryCode": "kr_en"},{"countryCode": "lv", "url_countryCode": "eu_en"},{"countryCode": "lt", "url_countryCode": "eu_en"},{"countryCode": "lt", "url_countryCode": "eu_en"},{"countryCode": "lu", "url_countryCode": "eu_en"},{"countryCode": "mt", "url_countryCode": "eu_en"},{"countryCode": "mc", "url_countryCode": "eu_en"},{"countryCode": "nl", "url_countryCode": "nl_en"},{"countryCode": "pa", "url_countryCode": "pa_en"},{"countryCode": "pe", "url_countryCode": "pe_es"},{"countryCode": "pl", "url_countryCode": "pl_en"},{"countryCode": "pt", "url_countryCode": "pt_en"},{"countryCode": "gb", "url_countryCode": "gb_en"},{"countryCode": "pr", "url_countryCode": "pr_en"},{"countryCode": "us", "url_countryCode": "us_en"},{"countryCode": "se", "url_countryCode": "eu_en"},{"countryCode": "ic", "url_countryCode": "ic_es"},{"countryCode": "es", "url_countryCode": "es_en"},{"countryCode": "ro", "url_countryCode": "eu_en"},{"countryCode": "sl", "url_countryCode": "eu_en"}]'

    bimba_headers = headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }

    base_url = "https://www.bimbaylola.com"
    handle_httpstatus_list = [430, 403, 404, 307]
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

    start_urls = "https://www.bimbaylola.com"

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url

    def start_requests(self):
        try:
            yield scrapy.Request(
                self.start_urls,
                callback=self.country_base_url,
                headers=rotate_headers(),
            )
        except Exception as e:
            self.log(e)

    @inline_requests
    def country_base_url(self, response):
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode').lower()
            language_code = item.get('url_countryCode').lower()
            url_country_code = country_code
            if country_code in ["mx", "cl", "sg"]:
                url = f"https://www.bimbaylola.{url_country_code}/{language_code}/"
            else:
                url = f'{self.base_url}/{language_code}/'
            country_response = scrapy.Request(url, headers=self.headers, dont_filter=True)
            target_response = yield country_response
            self.get_target_urls(target_response)

        params = {'start': 0, 'sz': 9999}
        filtered_urls = list(set(self.all_target_urls))
        for link in filtered_urls:
            try:
                if '/cl_es' in link:
                    base_url = 'https://www.bimbaylola.cl'
                    category_url = urljoin(base_url, link)

                elif '/sg_en' in link:
                    base_url = 'https://www.bimbaylola.sg'
                    category_url = urljoin(base_url, link)

                elif '/mx_en' in link:
                    base_url = 'https://www.bimbaylola.mx'
                    category_url = urljoin(base_url, link)
                else:
                    category_url = response.urljoin(link)
                url = category_url + '?' + urlencode(params)

                try:
                    loop = asyncio.get_event_loop()
                    results = loop.run_until_complete(main([url], self.proxy_cycle, self.bimba_headers))
                    for result in results:
                        if result:
                            target_response = TextResponse(url=url, body=result, encoding='utf-8')
                            self.parse(target_response)
                except Exception as e:
                    self.log(f"Error next_page: {e}")
            except Exception as e:
                self.log(f"Error occurred while processing URL {link}: {e}")

        for sku_id, product_url in self.sku_mapping.items():
            if '/cl_es' in product_url:
                base_url = 'https://www.bimbaylola.cl'
                url = urljoin(base_url, product_url)

            elif '/sg_en' in product_url:
                base_url = 'https://www.bimbaylola.sg'
                url = urljoin(base_url, product_url)
            elif '/mx_en' in product_url:
                base_url = 'https://www.bimbaylola.mx'
                url = urljoin(base_url, product_url)
            else:
                url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=rotate_headers(),
                cb_kwargs={'product_url': product_url}
            )

    def get_target_urls(self, response):
        if response:
            target_urls = response.css('.the-menu__wrapper ul li a::attr(href)').getall()
            target_urls_list = list(set(target_urls))
            for link in target_urls_list:
                if link not in self.all_target_urls:
                    self.all_target_urls.append(link)

    def parse(self, response):
        product_elements = response.css('.base-product-grid__item')
        for product_element in product_elements:
            product_url = product_element.css('.base-product-tile-image a::attr(href)').get()
            sku_id = product_element.css('meta[itemprop="sku"]::attr(content)').get()
            self.get_all_sku_mapping(product_url, sku_id)

    def get_all_sku_mapping(self, product_url, sku_id):
        if product_url and "_en/" in product_url:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "_en/" not in existing_url:
                self.sku_mapping[sku_id] = product_url
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url
        elif product_url and "_en/" not in product_url:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = product_url

    @inline_requests
    def parse_product(self, response, product_url):
        url_parts = product_url.split("/")
        url_without_language = "/".join(url_parts[2:])
        content = {}
        specification = {}
        delivery_data = ''
        list_img = []
        color = ''
        mpn = ''
        sku_id = ''
        brand = ''
        size_dimension = []
        main_material = ''
        secondary_material = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            mpn = json_data.get("mpn")
            brand = json_data["brand"]
            sku_id = json_data.get('sku')
            image = json_data.get("image")
            for img in image:
                list_img.append(img)
        all_script_tags = response.css('script').getall()
        for script_tag in all_script_tags:
            if "vuedata.Cart = {" in script_tag:
                script_tag_content = script_tag.strip().split("vuedata.TheProductDetails.product =")[1].split("};")[
                                         0] + "}"
                json_data = json.loads(script_tag_content)
                attributes = json_data.get("attributes")
                attribute = attributes[0]['attributes']
                composition_text = next(
                    (attr['value'][0] for attr in attribute if attr['label'] == 'Composition Text'), None)
                values = []
                if "<br/>" in composition_text:
                    materials = composition_text.split("<br/>")
                    for data_material in materials:
                        label, value = data_material.split(": ")
                        values.append(value)
                    main_material = values[0]
                    secondary_material = values[1]
                else:
                    main_material = composition_text.split(":")[1]
                approximate_measurements_value = None
                for item in attributes:
                    for attribute in item.get("attributes", []):
                        if attribute["label"] == 'Special relevant info, used in PDP':
                            approximate_measurements_value = attribute["value"][0].split(": ")[1].strip()
                        elif attribute["label"] == 'Model info, used in PDP':
                            approximate_measurements = attribute["value"][0]
                            approximate_measurements_value = "".join(approximate_measurements.split(". ", 1)[1:])
                if approximate_measurements_value is not None:
                    size_dimension.append(f'Measurement : {approximate_measurements_value}')
                else:
                    size_dimension = []
                variationAttributes = json_data['variationAttributes']
                for variationAttribute in variationAttributes:
                    id = variationAttribute['id']
                    if 'color' in id:
                        color = variationAttribute['values'][0].get("displayValue")
                break

        languages = ["us_en", "be_en", "fr_fr", "de_de", "nl_nl", "pl_pl", "pt_pt", "es_es", "es_gl", "es_ca", "mx_en",
                     "cl_es", "sg_en"]
        for language in languages:
            logging.info(f'Processing: {language}')
            if language == "mx_en":
                url = f'https://www.bimbaylola.mx/{language}/{url_without_language}'
            elif language == "cl_es":
                url = f'https://www.bimbaylola.cl/{language}/{url_without_language}'
            elif language == "sg_en":
                url = f'https://www.bimbaylola.sg/{language}/{url_without_language}'
            else:
                url = f'{self.base_url}/{language}/{url_without_language}'
            req = Request(url, headers=rotate_headers(), dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            elif resp.status in [301, 302]:
                redirected_url = resp.headers.get('Location').decode('utf-8')
                url = response.urljoin(redirected_url)

                country_response = scrapy.Request(url, headers=rotate_headers(),
                                                  dont_filter=True)
                redirected_resp = yield country_response
                if redirected_resp.status == 200:
                    content_info = self.collect_content_information(resp)
                    content[language.split("_")[1]] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
            else:
                content_info = self.collect_content_information(resp)
                content[language.split("_")[1]] = {
                    "sku_link": url,
                    "sku_title": content_info["sku_title"],
                    "sku_short_description": content_info["short_description"],
                    "sku_long_description": content_info["sku_long_description"]
                }

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode').lower()
            url_country_code = item.get('url_countryCode')
            if country_code in ["mx", "cl", "sg"]:
                delivery_api = f"https://www.bimbaylola.{country_code}/{url_country_code}/content?id=deliveryAndReturns"
            else:
                delivery_api = f"https://www.bimbaylola.com/{url_country_code}/content?id=deliveryAndReturns"
            delivery_req = scrapy.Request(delivery_api, headers=rotate_headers(), dont_filter=True)
            delivery_resp = yield delivery_req
            if delivery_resp.status == 200:
                delivery_data = json.loads(delivery_resp.text)
            else:
                self.log(f"Received {delivery_resp.status} Response for URL: {delivery_resp.url}")
            if country_code in ["mx", "cl", "sg"]:
                country_url = f'https://www.bimbaylola.{country_code}/{url_country_code}/{url_without_language}'
            else:
                country_url = f'{self.base_url}/{url_country_code}/{url_without_language}'
            try:
                specification_resp = yield Request(country_url, headers=self.headers, dont_filter=True)
                if specification_resp.status == 200:
                    specification_info = self.collect_specification_info(specification_resp, country_code, delivery_data,
                                                                         url_country_code)
                    specification[country_code] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {country_url}")

            except Exception as e:
                self.log(f"Error next_page: {e}")

        product_images_info = []
        is_production = get_project_settings().get("IS_PRODUCTION")
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

        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        domain, domain_url = self.extract_domain_domain_url(response.url)

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = brand
        item['mpn'] = mpn
        item['product_badge'] = ''
        item['manufacturer'] = self.name
        item['sku'] = sku_id
        item['sku_color'] = color
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, resp):
        sku_long_description = ''
        sku_short_description = ''
        sku_long_description_list = []
        sku_title = ''
        all_script_tags = resp.css('script').getall()
        for script_tag in all_script_tags:
            if "vuedata.Cart = {" in script_tag:
                script_tag_content = script_tag.strip().split("vuedata.TheProductDetails.product =")[1].split("};")[
                                         0] + "}"
                json_data = json.loads(script_tag_content)
                sku_short_description = json_data.get("shortDescription")
                sku_description = json_data["attributes"][0]["attributes"]
                for item in sku_description:
                    sku_long = item["value"][0]
                    sku_long_description_list.append(sku_long)
                sku_title = json_data["productName"]
                sku_long_description = sku_short_description + ' '.join(sku_long_description_list)
                break
        return {
            "sku_title": sku_title,
            "short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, delivery_data, url_country_code):
        currency = ''
        base_price = ''
        availability = ''
        sales_price = ''
        rating = ''
        sizes_list = []
        delivery_text = {}
        delivery_time = {}

        del_content = delivery_data["content"]
        if del_content:
            rep_cont = del_content.split('<li><u>')[1].split('<li><u>')[0].replace('<li>', '').replace('</li>',
                                                                                                       '').replace(
                '<ul>', '').replace('</ul>', '')
            spl_cont1 = rep_cont.split('</u>')[1]
            delivery_data = spl_cont1.split('.')
            keys_list = ['free', 'standard', 'express']

            for key, value in zip(keys_list, delivery_data):
                data = value.split('-')
                text = data[0][:-1]
                str_data = ''.join(text)
                times = value.split(str_data)[1]
                delivery_text[key] = str_data.strip()
                delivery_time[key] = times.strip()
        shipping_lead_time = '\n'.join(f"{key}: {value}" for key, value in delivery_time.items())
        shipping_expenses = '\n'.join(f"{key}: {value}" for key, value in delivery_text.items())

        all_script_tags = resp.css('script').getall()
        for script_tag in all_script_tags:
            if "vuedata.Cart = {" in script_tag:
                script_tag_content = script_tag.strip().split("vuedata.TheProductDetails.product =")[1].split("};")[
                                         0] + "}"
                json_data = json.loads(script_tag_content)
                sales_value = json_data["price"]
                if sales_value:
                    sale_price = sales_value["sales"].get("decimalPrice")
                    sales_price = "{:.2f}".format(float(sale_price))
                base_value = json_data["price"]["list"]
                if base_value is not None:
                    price = base_value.get("value")
                    base_price = "{:.2f}".format(float(price))
                else:
                    base_price = sales_price
                availability = json_data['availability']["messages"][0]
                rating = json_data["rating"]
                currency = json_data["price"]["sales"].get("currency")
                variationAttributes = json_data['variationAttributes']
                for variationAttribute in variationAttributes:
                    id = variationAttribute['id']
                    if 'size' in id:
                        variantList = variationAttribute['values']
                        for size in variantList:
                            sizes = size['displayValue']
                            if sizes and sizes != 'UN':
                                sizes_list.append(sizes)

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]
        return {
            "lang": url_country_code.split("_")[1],
            "domain_country_code": country_code,
            "currency": currency if currency else 'default_currency_code',
            "base_price": base_price if base_price else 0.0,
            "sales_price": sales_price if sales_price else 0.0,
            "active_price": sales_price if sales_price else 0.0,
            "stock_quantity": None,
            "availability": availability_status if availability_status else 'NA',
            "availability_message": out_of_stock_text if out_of_stock_text else 'NA',
            "shipping_lead_time": shipping_lead_time if shipping_lead_time else 'NA',
            "shipping_expenses": shipping_expenses if shipping_expenses else 0.0,
            "marketplace_retailer_name": 'bimbaylola',
            "condition": "NEW",
            "reviews_rating_value": rating,
            "reviews_number": 0,
            "size_available": sizes_list if sizes_list else [],
            "sku_link": resp.url if resp.url else 'NA',
        }

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "in stock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = availability_value
                return "No", out_of_stock_text
        except Exception as e:
            logging.error(f"Error processing image: {e}")
