import urllib
from PIL import Image
from urllib.parse import urlencode, urljoin
from scrapy.http import TextResponse, Request
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
from itertools import cycle
import aiohttp
import asyncio
from urllib.parse import quote
import time, datetime, re, tldextract, uuid, logging, os, requests, scrapy, json
from bclowd_spider.items import ProductItem
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers


async def get_page(session, url, proxy_cycle, kendra_headers):
    retry = 0
    while retry <= 5:
        proxy = next(proxy_cycle)
        try:
            async with session.get(url, proxy=f"http://{proxy}", headers=kendra_headers) as response:
                logging.info(f"Response status for {url} with proxy {proxy}: {response.status}")
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            logging.error(f"Error fetching {url} with proxy {proxy}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching {url} with proxy {proxy}: {e}")
        retry += 1

    return None


async def get_all(session, urls,proxy_cycle, kendra_headers):
    tasks = []
    for url in urls:
        task = asyncio.create_task(get_page(session, url, proxy_cycle,kendra_headers))
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results


async def main(urls, proxy_cycle, kendra_headers):
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=160)
            async with aiohttp.ClientSession(headers=kendra_headers, timeout=timeout) as session:
                data = await get_all(session, urls, proxy_cycle, kendra_headers)
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


class KendraSpider(scrapy.Spider):
    name = "kendra"
    target_urls = []
    sku_mapping = {}
    all_target_urls = []
    proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    proxy_cycle = cycle(proxies_list)
    base_url = "www.kendrascott.com"
    handle_httpstatus_list = [430, 500, 403, 404, 410, 400]
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

    spec_mapping = '[{"countryCode": "es", "url_countryCode": "es", "Country_Name": "Spain", "currencyCode": "EUR", "cookiesCode": "es"}, {"countryCode": "us", "url_countryCode": "us", "Country_Name": "United States", "currencyCode": "USD", "cookiesCode": "en-US"}]'
    # spec_mapping = '[{"countryCode": "es", "url_countryCode": "es", "Country_Name": "Spain", "currencyCode": "EUR", "cookiesCode": "es"}, {"countryCode": "us", "url_countryCode": "us", "Country_Name": "United States", "currencyCode": "USD", "cookiesCode": "en-US"}, {"countryCode": "cl", "url_countryCode": "cl", "Country_Name": "Chile", "currencyCode": "CLP"}, {"countryCode": "co", "url_countryCode": "co", "Country_Name": "Colombia", "currencyCode": "COP"}, {"countryCode": "qa", "url_countryCode": "qa", "Country_Name": "Qatar", "currencyCode": "QAR"}, {"countryCode": "mx", "url_countryCode": "mx", "Country_Name": "Mexico", "currencyCode": "MXN"}, {"countryCode": "br", "url_countryCode": "br", "Country_Name": "Brazil", "currencyCode": "USD"}, {"countryCode": "sa", "url_countryCode": "sa", "Country_Name": "Saudi Arabia", "currencyCode": "SAR"}, {"countryCode": "ae", "url_countryCode": "ae", "Country_Name": "United Arab Emirates", "currencyCode": "AED"}, {"countryCode": "us", "url_countryCode": "us", "Country_Name": "United States", "currencyCode": "USD"}, {"countryCode": "bo", "url_countryCode": "bo", "Country_Name": "Bolivia", "currencyCode": "BOB"}, {"countryCode": "pe", "url_countryCode": "pe", "Country_Name": "Peru", "currencyCode": "PEN"}, {"countryCode": "be", "url_countryCode": "be", "Country_Name": "Belgium", "currencyCode": "EUR"}, {"countryCode": "ke", "url_countryCode": "ke", "Country_Name": "Kenya", "currencyCode": "USD"}, {"countryCode": "gr", "url_countryCode": "gr", "Country_Name": "Greece", "currencyCode": "EUR"}, {"countryCode": "cz", "url_countryCode": "cz", "Country_Name": " Czech Republic", "currencyCode": "CZK"}, {"countryCode": "ma", "url_countryCode": "ma", "Country_Name": "Morocco", "currencyCode": "MAD"}, {"countryCode": "cn", "url_countryCode": "cn", "Country_Name": " China", "currencyCode": "CNY"}, {"countryCode": "hk", "url_countryCode": "hk", "Country_Name": "Hong Kong", "currencyCode": "HKD"}, {"countryCode": "sg", "url_countryCode": "sg", "Country_Name": " Singapore", "currencyCode": "SGD"}, {"countryCode": "id", "url_countryCode": "id", "Country_Name": "Indonesia", "currencyCode": "USD"}, {"countryCode": "jp", "url_countryCode": "jp", "Country_Name": "Japan", "currencyCode": "JPY"}, {"countryCode": "my", "url_countryCode": "my", "Country_Name": "Malaysia", "currencyCode": "MYR"}, {"countryCode": "ph", "url_countryCode": "ph", "Country_Name": "Philippines", "currencyCode": "PHP"}, {"countryCode": "kr", "url_countryCode": "kr", "Country_Name": "Korea, Republic of", "currencyCode": "KRW"}, {"countryCode": "tw", "url_countryCode": "tw", "Country_Name": "Taiwan", "currencyCode": "TWD"}, {"countryCode": "th", "url_countryCode": "th", "Country_Name": " Thailand", "currencyCode": "THB"}, {"countryCode": "vn", "url_countryCode": "vn", "Country_Name": "Vietnam", "currencyCode": "USD"}, {"countryCode": "tr", "url_countryCode": "tr", "Country_Name": "Turkey", "currencyCode": "TRY"}, {"countryCode": "de", "url_countryCode": "de", "Country_Name": "Germany", "currencyCode": "EUR"}, {"countryCode": "it", "url_countryCode": "it", "Country_Name": " Italy", "currencyCode": "EUR"}, {"countryCode": "nl", "url_countryCode": "nl", "Country_Name": " Netherlands", "currencyCode": "EUR"}, {"countryCode": "no", "url_countryCode": "no", "Country_Name": "Norway", "currencyCode": "NOK"}, {"countryCode": "dk", "url_countryCode": "dk", "Country_Name": "Denmark", "currencyCode": "DKK"}, {"countryCode": "lu", "url_countryCode": "lu", "Country_Name": "Luxembourg", "currencyCode": "EUR"}, {"countryCode": "pt", "url_countryCode": "pt", "Country_Name": " Portugal", "currencyCode": "EUR"}, {"countryCode": "es", "url_countryCode": "es", "Country_Name": "Spain", "currencyCode": "EUR"}, {"countryCode": "se", "url_countryCode": "se", "Country_Name": "Sweden", "currencyCode": "SEK"}, {"countryCode": "gb", "url_countryCode": "gb", "Country_Name": " United Kingdom", "currencyCode": "GBP"}, {"countryCode": "fr", "url_countryCode": "fr", "Country_Name": "France", "currencyCode": "EUR"}, {"countryCode": "il", "url_countryCode": "il", "Country_Name": " Israel", "currencyCode": "ILS"}, {"countryCode": "ec", "url_countryCode": "ec", "Country_Name": " Ecuador", "currencyCode": "USD"}, {"countryCode": "uy", "url_countryCode": "uy", "Country_Name": " Uruguay", "currencyCode": "UYU"}]'

    start_urls = "https://www.kendrascott.com/"
    kendra_headers = headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
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

    def get_target_urls(self, response):
        target_urls = response.css('.dropdown-item.dropdown>ul>li>a::attr(href)').getall()
        target_urls_list = list(set(target_urls))
        for link in target_urls_list:
            if "vacation-edit.html" not in link and "blog.kendrascott.com" not in link and "fragrance.html" not in link and "game-day.html" not in link and "kendra-scott-founders-market" not in link and "birthstone-guidel" not in link and "about-kendra" not in link and "zodiac-guide" not in link:
                absolute_url = urljoin(response.url, link)
                self.all_target_urls.append(absolute_url)

    @inline_requests
    def main_page(self, response):
        try:
            self.get_target_urls(response)
            params = {'sz': 9999}
            for link in self.all_target_urls:
                if '?' in link:
                    new_link = f"{link}&{urlencode(params)}"
                else:
                    new_link = f"{link}?{urlencode(params)}"
                url = response.urljoin(new_link)
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(main([url], self.proxy_cycle, self.kendra_headers))
                for result in results:
                    if result:
                        next_response = TextResponse(url=url, body=result, encoding='utf-8')
                        self.parse(next_response)
        except Exception as e:
            self.log(f"Error: {e}")

        logging.info(f'Total Sku of kendra : {len(self.sku_mapping)}')
        for sku_id, product_url in self.sku_mapping.items():
            sku_url = ''
            if isinstance(self.sku_mapping[sku_id]['product_urls'], list) and len(
                    self.sku_mapping[sku_id]['product_urls']) > 0:
                sku_url = self.sku_mapping[sku_id]['product_urls'][0]
            url = response.urljoin(sku_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': sku_url, 'sku_id': sku_id},
                dont_filter=True
            )

    def parse(self, response):
        product_elements = response.css('.js-wishlist-track')
        product_urls_list = set(product_elements)
        for product_element in product_urls_list:
            product_url = product_element.css('div > div > a.swatch-main-img.swipe-child-1::attr(href)').get()
            sku_id = product_element.css('::attr(data-pid)').get()
            if 'shop-the-look' not in product_url:
                self.set_all_sku_mapping(product_url, sku_id)

    def set_all_sku_mapping(self, product_url, sku_id):
        if sku_id not in self.sku_mapping:
            self.sku_mapping[sku_id] = {'product_urls': [product_url]}
        else:
            if isinstance(self.sku_mapping[sku_id]['product_urls'], str):
                self.sku_mapping[sku_id]['product_urls'] = [self.sku_mapping[sku_id]['product_urls']]
            if product_url not in self.sku_mapping[sku_id]['product_urls']:
                self.sku_mapping[sku_id]['product_urls'].append(product_url)

    @inline_requests
    def parse_product(self, response, product_url, sku_id):
        content = {}
        mpn = ''
        brand = ''
        specification = {}
        list_img = []
        reviews_number = ''
        reviews_rating_value = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tag_content:
            try:
                json_data = json.loads(script_tag)
                if "offers" in json_data:
                    mpn = json_data.get("mpn")
                    images = json_data.get('image')
                    for image in images:
                        if not image == '':
                            list_img.append(image)
                    brand = json_data["brand"].get("name")
                    break
            except Exception as e:
                print(e)

        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": f'{response.url}',
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        sizes = response.css('button.size-options.selectable::text').getall()
        stripped_sizes = [size.strip() for size in sizes]
        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode')
                currency_code = item.get('currencyCode')
                url_country_code = item.get('url_countryCode')
                cookies_Code = item.get('cookiesCode')
                split_url_by_question_mark = product_url.split("?")
                main_url = split_url_by_question_mark[0]
                country_url = main_url
                api_url = f"https://staticw2.yotpo.com/batch/app_key/uzMxSBGEa5L8oNhLVJkKJgo0vc9g0ehgVFKwDvXe/domain_key/{sku_id}/widget/bottomline"
                payload = {
                    "methods": [
                        {
                            "method": "bottomline",
                            "params": {
                                "pid": sku_id,
                                "link": country_url,
                                "skip_average_score": False,
                                "main_widget_pid": sku_id,
                                "index": 1,
                                "element_id": "2"
                            }
                        }
                    ],
                }
                try:
                    review_req = scrapy.FormRequest(
                        url=api_url,
                        method='POST',
                        body=json.dumps(payload),
                        headers={**self.headers, 'Content-Type': 'application/json'},
                        dont_filter=True)
                    review_response = yield review_req
                    if review_response.status == 200:
                        data = review_response.json()
                        if data:
                            result = data[0].get('result', '')
                            if result:
                                reviews_split = result.split('aria-label="')
                                if len(reviews_split) > 1:
                                    reviews = reviews_split[1].split(' reviews')[0]
                                else:
                                    reviews = None
                                rating_split = result.split('sr-only">')
                                if len(rating_split) > 1:
                                    reviews_rating_value = rating_split[1].split(' ')[0]
                                else:
                                    reviews_rating_value = None

                                reviews_number = reviews if reviews else None
                            else:
                                logging.error("No 'result' key found in the response data.")
                        else:
                            logging.error("Empty response data.")
                    else:
                        logging.error(f"Failed to fetch reviews and ratings for product {sku_id}")
                except IndexError as e:
                    logging.error(f"IndexError: {e}")
                except Exception as e:
                    logging.error(f"Error: {e}")
                cookie_value = f'{{"countryISO":"{country_code.upper()}","cultureCode":"fr","currencyCode":"{currency_code}","apiVersion":"2.1.4"}}'
                encoded_cookie = urllib.parse.quote(cookie_value)  # URL encode it

                cookies = {"GlobalE_Data": encoded_cookie}
                # cookies = 'GlobalE_Data=%7B%22countryISO%22%3A%22' + country_code + '%22%2C%22cultureCode%22%3A%22fr%22%2C%22currencyCode%22%3A%22' + currency_code + '%22%2C%22apiVersion%22%3A%222.1.4%22%7D'
                req = scrapy.Request(product_url, headers=self.headers, cookies=cookies, dont_filter=True)
                country_resp = yield req
                if country_resp.status == 404:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
                else:
                    specification_info = self.collect_specification_info(country_resp, product_url, url_country_code, reviews_rating_value , reviews_number, sku_id, stripped_sizes,currency_code)
                    specification[country_code] = specification_info

        except json.JSONDecodeError as e:
            self.log(f'Error : {e}')
            return
        domain, domain_url = self.extract_domain_domain_url(response.url)
        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku_id + '/'
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
                        image_info = directory + "/" + filename
                        product_images_info.append(image_info)
                    except Exception as e:
                        logging.error(f"Error processing image: {e}")

        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        size_dimensions = []
        size_dimension = response.css('#collapsible-details-1 h3:contains("Size") + p::text').get()
        strap_width = response.css('#collapsible-details-1 h3:contains("Strap Width") + p::text').get()
        strap_length = response.css('#collapsible-details-1 h3:contains("Strap Length") + p::text').get()
        carat_weight = response.css('#collapsible-details-1 h3:contains("Carat Weight") + p::text').get()
        other_dimension = response.css('#collapsible-details-1::text').getall()

        if size_dimension:
            size_dimensions.append("Size: " + size_dimension.strip())
        elif strap_width and strap_length:
            size_dimensions.append("Size Width: " + strap_width.strip())
            size_dimensions.append("Size Length: " + strap_length.strip())
        else:
            other_dimensions = ["Size: " + dimension.strip() for dimension in other_dimension if dimension.strip()]
            if carat_weight:
                other_dimensions.append("Carat Weight: " + carat_weight.strip())
            size_dimensions.extend(other_dimensions)
        product_color = response.css('.color-name span::text').get() or ''
        main_material = response.css('#collapsible-details-1 h3:contains("Metal") + p::text').get()
        secondary_material = response.css('#collapsible-details-1 h3:contains("Material") + p::text').get()
        product_badge = ''
        badge = response.css('.content-asset  >div>p::text').get() or ''
        if badge:
            product_badge = badge.strip()

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['brand'] = brand
        item['product_badge'] = product_badge
        item['manufacturer'] = self.name
        item['mpn'] = mpn
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = secondary_material
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimensions
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        short_Description_text = response.css('#collapsible-description-1::text').get(default="").strip()
        if short_Description_text is not None:
            short_description = short_Description_text
        else:
            short_description = response.css('#collapsible-description-1>p::text').get(default="").strip()
        description_text = response.css('#pro-details > div> h3 ::text, #pro-details > div> p::text').getall()
        descriptions_text = ' '.join(text.strip() for text in description_text)
        sku_long_description = short_description + descriptions_text
        sku_title = response.css('h1.product-name::text').get().strip()
        return {
            "sku_title": sku_title,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, response, product_url, url_country_code, reviews_rating_value, reviews_number, sku_id, stripped_sizes, currency_code):

        sales_price = ''
        availability_status = ''
        out_of_stock_text = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        shipping_url = 'https://www.kendrascott.com/shipping-returns.html'
        try:
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(main([shipping_url], self.proxy_cycle, self.kendra_headers))
            for result in results:
                if result:
                    next_response = TextResponse(url=shipping_url, body=result, encoding='utf-8')
                    shipping_text = next_response.css('.experience-component.experience-loyalty-faqComponent')
                    text = shipping_text.css('li ::text').getall()
                    for i, item in enumerate(text):
                        if "Free on" in item:
                            shipping_value = item.split('.')
                            if len(shipping_value) > 1:
                                shipping_expenses = shipping_value[0]
                                shipping_lead_time = shipping_value[1]
                            break
        except Exception as e:
            self.log(f"Error: {e}")

        script_content = response.css('script::text').re_first(r'pageData\s*=\s*({.*})')

        if script_content:
            page_data = json.loads(script_content)
            price = page_data["ecommerce"]["detail"]["products"][0]["price"]
            # price = page_data["ecommerce"]["detail"]["products"][0]["dimension14"]

        sale_price = response.css('span.sales::attr(data-formatted-price)').get()
        if sale_price:
            sales_price = self.extract_price_info(sale_price)

        price = response.css('span#product-list-price::attr(content)').get()
        if price:
            base_price = self.extract_price_info(price.strip())
        else:
            base_price = sales_price
        check_stock_availability = f'https://www.kendrascott.com/on/demandware.store/Sites-KendraScott-Site/en_US/Product-UpdateAddToCartAvailability?pid={sku_id}'

        try:
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(main([check_stock_availability], self.proxy_cycle, self.kendra_headers))
            for result in results:
                if result:
                    next_response = TextResponse(url=check_stock_availability, body=result, encoding='utf-8')
                    data = next_response.json()
                    product_availability = self.check_product_availability(data)
                    availability_status = product_availability[0]
                    out_of_stock_text = product_availability[1]

        except Exception as e:
            self.log(f"Error : {e}")

        return {
            "lang": "en",
            "domain_country_code": url_country_code,
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sales_price,
            "active_price": sales_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "marketplace_retailer_name": "kendrascott",
            "condition": "NEW",
            "reviews_rating_value": reviews_rating_value,
            "reviews_number": reviews_number,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "size_availability": stripped_sizes,
            "sku_link": product_url
        }

    def check_product_availability(self, check_stock_availability):
        try:
            availability_value = check_stock_availability['product']['availability']['messages'][0]
            if "In Stock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Sold Out"
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
            return None,

