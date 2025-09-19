import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from itertools import cycle
from bs4 import BeautifulSoup
from scrapy.http import TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


class Missoma(scrapy.Spider):
    name = "missoma"
    target_urls = []
    all_target_urls = []
    sku_mapping = {}
    spec_mapping = '[{"countryCode": "SA", "url_countryCode": "en-SA","currencyCode": "SAR"}, {"countryCode": "UK", "url_countryCode": "en-GB","currencyCode": "GBP"}, {"countryCode": "AR", "url_countryCode": "en_AR","currencyCode": "ARS"},{"countryCode": "AU", "url_countryCode": "en_AU","currencyCode": "AUD"},{"countryCode": "AT", "url_countryCode": "en_AT","currencyCode": "EUR"},{"countryCode": "BE", "url_countryCode": "en_BE","currencyCode": "EUR"},{"countryCode": "BO", "url_countryCode": "en_BO","currencyCode": "BOB"},{"countryCode": "CA", "url_countryCode": "en_CA","currencyCode": "CAD"},{"countryCode": "KY", "url_countryCode": "en_KY","currencyCode": "KYD"},{"countryCode": "CL", "url_countryCode": "en_CL","currencyCode": "CLP"},{"countryCode": "CN", "url_countryCode": "en_CN","currencyCode": "CNY"},{"countryCode": "CO", "url_countryCode": "en_CO","currencyCode": "COP"},{"countryCode": "FR", "url_countryCode": "en_FR","currencyCode": "EUR"},{"countryCode": "DE", "url_countryCode": "en_DE","currencyCode": "EUR"},{"countryCode": "HK", "url_countryCode": "en_HK","currencyCode": "HKD"},{"countryCode": "IL", "url_countryCode": "en_IL","currencyCode": "ILS"},{"countryCode": "IT", "url_countryCode": "en_IT","currencyCode": "EUR"},{"countryCode": "JP", "url_countryCode": "en_JP","currencyCode": "JPY"},{"countryCode": "MA", "url_countryCode": "en_MA","currencyCode": "MAD"},{"countryCode": "NL", "url_countryCode": "en_NL","currencyCode": "EUR"},{"countryCode": "NZ", "url_countryCode": "en_NZ","currencyCode": "NZD"},{"countryCode": "PL", "url_countryCode": "en_PL","currencyCode": "PLN"},{"countryCode": "PT", "url_countryCode": "en_PT","currencyCode": "EUR"},{"countryCode": "QA", "url_countryCode": "en_QA","currencyCode": "QAR"},{"countryCode": "SG", "url_countryCode": "en_SG","currencyCode": "SGD"},{"countryCode": "ZA", "url_countryCode": "en_ZA","currencyCode": "ZAR"},{"countryCode": "KR", "url_countryCode": "en_KR","currencyCode": "KRW"},{"countryCode": "ES", "url_countryCode": "en_ES","currencyCode": "EUR"},{"countryCode": "SE", "url_countryCode": "en_SE","currencyCode": "SEK"},{"countryCode": "TW", "url_countryCode": "en_TW","currencyCode": "TWD"},{"countryCode": "TR", "url_countryCode": "en_TR","currencyCode": "TRY"},{"countryCode": "AE", "url_countryCode": "en_AE","currencyCode": "AED"},{"countryCode": "US", "url_countryCode": "en_US","currencyCode": "USD"},{"countryCode": "UY", "url_countryCode": "en_UY","currencyCode": "UYU"},{"countryCode": "VE", "url_countryCode": "en_VE","currencyCode": "USD"}]'
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "https://www.missoma.com"
    handle_httpstatus_list = [430, 403, 404, 307, 430]
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

    start_urls = "https://www.missoma.com/sitemap_products_1.xml?from=4427333664871&to=15003957854595"
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
            headers=rotate_headers())

    @inline_requests
    def country_base_url(self, response):
        self.get_target_urls(response)
        filtered_urls = list(set(self.all_target_urls))
        for link in filtered_urls:
            if link:
                try:
                    request = scrapy.Request(link, headers=self.headers, dont_filter=True)
                    resp = yield request
                    if resp.status == 200:
                        self.parse(resp,link)
                    else:
                        self.log(f"Received Response for URL: {resp.status_code}")
                except Exception as e:
                    self.log(f"Error occurred while processing URL {link}: {e}")

        for sku_id, product_info in self.sku_mapping.items():
            url = product_info.get('product_url')
            barcode = product_info.get('barcode')
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                dont_filter=True,
                cb_kwargs={'product_url': url, 'barcode': barcode,'sku_id': sku_id},
            )

    def get_target_urls(self, response):
        soup = BeautifulSoup(response.text, 'xml')
        product_all_urls = soup.find_all('url')
        for url in product_all_urls:
            loc = url.find('loc')
            self.all_target_urls.append(loc.text)

    def parse(self, response, link):
        try:
            script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
            if script_tag_content:
                for script_tag in script_tag_content:
                    try:
                        json_data = json.loads(script_tag)
                        if "offers" in json_data:
                            offers = json_data['offers']
                            for offer in offers:
                                sku_id = offer.get("sku")
                                barcode = offer.get("gtin13")
                                self.get_all_sku_mapping(link, sku_id, barcode)
                    except Exception as ex:
                        print(f"Exc {ex}")
        except json.JSONDecodeError:
            self.logger.error("Failed to decode JSON response from API.")

    def get_all_sku_mapping(self, link, sku_id, barcode):
        if "/en" in link:
            existing_url = self.sku_mapping.get(sku_id)
            if existing_url and "/en" not in existing_url:
                self.sku_mapping[sku_id] = {'product_url': link, 'barcode': barcode}
            elif sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': link, 'barcode': barcode}
        elif "/en" not in link:
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': link, 'barcode': barcode}

    @inline_requests
    def parse_product(self, response, barcode, sku_id, product_url):
        url_without_language = response.url.split('.com')[1]
        content = {}
        specification = {}
        content_info = self.collect_content_information(response)
        content['en'] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            country_code = item.get('countryCode')
            currency_code = item.get('currencyCode')
            url_countryCode = item.get('url_countryCode')
            url = f'{self.base_url}{url_without_language}?country={country_code}&currency={currency_code}'
            api_url = f'{self.base_url}{url_without_language}?country={country_code}&view=get-product-json'
            scraper = cloudscraper.create_scraper()
            country_response = scraper.get(url)
            resp = TextResponse(url='', body=country_response.text, encoding='utf-8')
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            else:
                specification_info = self.collect_specification_info(resp, country_code, url, api_url)
                specification[country_code.lower()] = specification_info

        list_img = []
        picture_sources = response.css(
            'div.product-main__media-container>div.product-main__media-item >.product-main__media-item--inner>img::attr(srcset)').getall()
        for picture in picture_sources:
            _img = picture.split(",")[-1]
            replaced_str = _img.replace("2000w", "")
            img = "https:" + replaced_str.strip()
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

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        main_material = ''
        secondary_material = ""
        dim_details = response.css('main.product-info-popup__main>p::text').extract()
        dim_details_2 = response.css('main.product-info-popup__main>p:nth-of-type(2)').extract()
        p = '<p>'
        p1 = '</p>'
        s = '<span data-mce-fragment="1">'
        s1 = '</span>'
        detail_list = ''.join(dim_details_2)
        p_details = detail_list.replace(p, '').replace(p1 , '').replace(s,'').replace(s1, '').replace('data-mce-fragment="1"', '').replace('<br >', '<br>')
        dimension_detail= p_details.split('<br>')
        if 'Metal' not in dim_details:
            dim_details += dimension_detail

        size_dimension = []
        for item in dim_details:
            if "dimensions" in item.lower():
                size_dimension.append(item)
            elif "height" in item.lower():
                size_dimension.append(item)
            elif "length" in item.lower():
                size_dimension.append(item)
            elif "width" in item.lower():
                size_dimension.append(item)
            elif "weight" in item.lower():
                size_dimension.append(item)
            elif "metal:" in item.lower():
                main_material = item.split(':')[1]
            elif "gemstone:" in item.lower():
                secondary_material = item.split(':')[1]

        product_badge= ''
        badge = response.css('div.product-tags__list>span::text').get()
        if badge:
            product_badge = badge.strip()

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = "Missoma"
        item['manufacturer'] = "Missoma"
        item['product_badge'] = product_badge
        item['gtin13'] = barcode
        item['sku'] = sku_id
        item['sku_color'] = ''
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        sku_title = ''
        sku_short_description = ''
        sku_long_description = response.css('.product-info-popup__main>p::text').getall()
        sku_long_descriptions = ''.join(sku_long_description)
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        if len(script_tag_content) > 1:
            json_data = json.loads(script_tag_content[1])
            sku_title = json_data.get('name')
            sku_short_description = json_data.get('description')
        return {
            "sku_title": sku_title,
            "sku_long_description": sku_long_descriptions,
            "sku_short_description": sku_short_description
        }

    def collect_specification_info(self, resp, country_code, url,api_url):
        currency = ''
        active_price = ''
        availability = ''
        average_rating = ''
        sale_price = ''
        total_review_count = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        stock_quantity = ''
        proxy = next(self.proxy_cycle)
        response = requests.get(api_url, self.headers,  proxies={'http': proxy, 'https': proxy})
        if response.status_code == 200:
            try:
                product_data = json.loads(response.text)
                first_available_variant = product_data.get('first_available_variant', {})
                stock_quantity = first_available_variant.get('inventory_quantity')
                print(f"Inventory Quantity: {stock_quantity}")
            except Exception as e:
                print("Exception in Inventory Quantity", e)

        tr_data = resp.css(".size-guide-popup-rings__table>tr").extract()
        try:
            if tr_data:
                standard_delivery = resp.css(
                    '.size-guide-popup-rings__table>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(2)>td::text').extract()
                next_day_delivery = resp.css(
                    '.size-guide-popup-rings__table>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(3)>td::text').extract()
                same_day_delivery = resp.css(
                    '.size-guide-popup-rings__table>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(4)>td::text').extract()
                premium_delivery = resp.css(
                    '.size-guide-popup-rings__table>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(5)>td::text').extract()
                shipping_lead_time = [f"standard delivery : {''.join(standard_delivery[-1])}", f"next day : {''.join(next_day_delivery[-1])}",
                                      f"same day : {''.join(same_day_delivery[-1])}", f"premium :{''.join(premium_delivery[-1])}"]
                shipping_expenses = [f"standard delivery : {''.join(standard_delivery[2:4])}",
                                     f"next day : {''.join(next_day_delivery[2:4])}", f"same day : {''.join(same_day_delivery[2])}",
                                     f"premium :{''.join(premium_delivery[2])}"]
            else:
                standard_delivery = resp.css(
                    '.size-guide-popup-rings__table>tbody>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(2)>td::text').extract()
                next_day_delivery = resp.css(
                    '.size-guide-popup-rings__table>tbody>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(3)>td::text').extract()
                same_day_delivery = resp.css(
                    '.size-guide-popup-rings__table>tbody>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(4)>td::text').extract()
                premium_delivery = resp.css(
                    '.size-guide-popup-rings__table>tbody>tr.size-guide-popup-rings__table-row.shipping-returns-popup__table-row:nth-child(5)>td::text').extract()
                shipping_lead_time = [f"standard delivery : {''.join(standard_delivery[-1])}", f"next day : {''.join(next_day_delivery[-1])}",
                                      f"same day : {''.join(same_day_delivery[-1])}", f"premium :{''.join(premium_delivery[-1])}"]
                shipping_expenses = [f"standard delivery : {''.join(standard_delivery[2:4])}",
                                     f"next day : {''.join(next_day_delivery[2:4])}", f"same day : {''.join(same_day_delivery[2])}",
                                     f"premium :{''.join(premium_delivery[2])}"]
        except Exception as e:
            print(e)
        shipping_expenses_str = ''
        shipping_lead_time_str = ''
        shipping_expenses = ' '.join(shipping_expenses)
        if shipping_expenses:
            shipping_expenses_str = shipping_expenses.strip()
        shipping_lead_time = ' '.join(shipping_lead_time)
        if shipping_lead_time:
            shipping_lead_time_str = shipping_lead_time.strip()

        script_tag_content = resp.css('script[type="application/ld+json"]::text').getall()
        if script_tag_content:
            for script_tag in script_tag_content:
                try:
                    json_data = json.loads(script_tag)
                    if "offers" in json_data:
                        offers = json_data['offers']
                        for offer in offers:
                            currency = offer.get("priceCurrency")
                            availability = offer.get("availability")
                            sale_price = offer.get("price")
                            productid = offer.get('url')
                            break
                except Exception as ex:
                    print(f"Exc {ex}")
        if sale_price:
            sale_price = str(sale_price)
        base_price_str = resp.css('p.product-info__price>span::text').get()
        if base_price_str:
            base_price = self.extract_price_info(base_price_str)
        else:
            base_price = sale_price
        pro_availability = self.check_product_availability(availability)
        availability_status = pro_availability[0]
        out_of_stock_text = pro_availability[1]
        size_set = set()
        size = []
        for s in resp.css("span.product-sizes-popup__size-value::text").getall():
            s_stripped = s.strip()
            if s_stripped and s_stripped not in size_set:
                size.append(s_stripped)
                size_set.add(s_stripped)

        product_id = resp.css('input[name="product-id"]::attr(value)').get()
        review_api = f'https://api.bazaarvoice.com/data/batch.json?passkey=ca6qQShPSQoyJYunGVUSLr1FkHLvrnvGR7maGXsNcg1FU&apiversion=5.5&displaycode=13571-en_gb&resource.q0=products&filter.q0=id%3Aeq%3A{product_id}&stats.q0=reviews'
        response = requests.get(review_api)
        if response.status_code == 200:
            json_data = response.json()
            review_Statistics = json_data['BatchedResults']['q0']['Results'][0]['ReviewStatistics']
            average_rating = review_Statistics['AverageOverallRating']
            total_review_count = review_Statistics['TotalReviewCount']


        return {
            "lang": "en",
            "domain_country_code": country_code.lower(),
            "currency": currency,
            "base_price": base_price,
            "sales_price": sale_price,
            "active_price": sale_price,
            "stock_quantity": stock_quantity,
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time_str,
            "shipping_expenses": shipping_expenses_str,
            "marketplace_retailer_name": self.name,
            "condition": "NEW",
            "reviews_rating_value": average_rating,
            "reviews_number": total_review_count,
            "size_available": size,
            "sku_link": url
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
            return None,

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


