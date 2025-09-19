import scrapy
from urllib.parse import urlencode
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
from scrapy.linkextractors import LinkExtractor
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
from scrapy.http import HtmlResponse
from scrapy.selector import Selector
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers
import http.cookies

class Chanel(scrapy.Spider):
    name = "chanel"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.chanel.com"
    handle_httpstatus_list = [404, 403, 500, 430]
    today = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
    # proxies_list = get_project_settings().get('ROTATING_PROXY_LIST')
    # proxy_cycle = cycle(proxies_list)

    directory = get_project_settings().get("FILE_PATH")
    if not os.path.exists(directory):
        os.makedirs(directory)
    logs_path = directory + today + "_" + name + ".log"
    logging.basicConfig(
        filename=logs_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    start_urls = "https://www.chanel.com/gb/"
    # remove at-de 3rd from spec-Map
    spec_mapping= '[{"countryName" : "United States" , "codeUrl":"us", "countryCode" :"US", "currencyCode":"USD" ,"lang":"en-US", "cookie":"US-en_US" }, {"countryName" : "Spain" , "codeUrl":"es", "countryCode" :"ES", "currencyCode":"EUR", "lang":"es-ES", "cookie":"ES-es_ES"}, {"countryName" : "Canada" ,"codeUrl": "ca-en", "countryCode" :"CA", "currencyCode":"CAD", "lang":"en-CA" , "cookie":"CA-en_CA-en_CA"},{"countryName" : "Austria" , "codeUrl":"at" , "countryCode" :"AT", "currencyCode":"EUR", "lang":"de-AT", "cookie":"AT-de_DE"},{"countryName" : "Finland" , "codeUrl":"fi" , "countryCode" :"FI", "currencyCode":"EUR", "lang":"en-FI" , "cookie":"FI-en_GB"},{"countryName" : "Hungary"  , "codeUrl":"hu", "countryCode" :"HU", "currencyCode":"HUF", "lang":"en-HU", "cookie":"HU-en_GB"} ]' #,{"countryName" : "Netherlands" , "codeUrl":"nl-NL", "countryCode" :"NL", "currencyCode":"EUR" ,"lang":"nl-NL"}, {"countryName" : "Slovenia" , "codeUrl":"si" , "countryCode" :"SL", "currencyCode":"EUR" ,"lang":"en-SI"},{"countryName" : "United Kingdom" , "codeUrl":"gb", "countryCode" :"GB", "currencyCode":"GBP", "lang":"en-GB"}, {"countryName" : "Belgium" , "codeUrl":"be-fr", "countryCode" :"BE", "currencyCode":"EUR" ,"lang":"fr-BE"}, {"countryName" : "France" , "codeUrl":"fr", "countryCode" :"FR", "currencyCode":"EUR" ,"lang":"fr-CA"},{"countryName" : "Ireland" , "codeUrl":"ie", "countryCode" :"IR", "currencyCode":"EUR","lang":"en-ie"}, {"countryName" : "Poland" , "codeUrl":"pl", "countryCode" :"PL", "currencyCode":"PLN" ,"lang":"pl-PL"}, {"countryName" : "Czech Republic" , "codeUrl":"cz", "countryCode" :"CZ", "currencyCode":"CZK" ,"lang":"cs"},{"countryName" : "Germany" , "codeUrl":"de" , "countryCode" :"DE", "currencyCode":"EUR" ,"lang":"de-DE"},{"countryName" : "Italy" , "codeUrl":"it" , "countryCode" :"IT", "currencyCode":"EUR" ,"lang":"it-IT"},{"countryName" : "Portugal" , "codeUrl":"pt", "countryCode" :"PT", "currencyCode":"EUR" ,"lang":"pt-PT"},{"countryName" : "Sweden" , "codeUrl":"se", "countryCode" :"SE", "currencyCode":"SEK" ,"lang":"sv-SE"},{"countryName" : "Denmark" , "codeUrl":"dk" , "countryCode" :"DK", "currencyCode":"DKK" ,"lang":"da-DK"},{"countryName" : "Greece" , "codeUrl":"gr" , "countryCode" :"GR", "currencyCode":"EUR" ,"lang":"en-GR"}, {"countryName" : "Luxembourg"  , "codeUrl":"lu-fr" , "countryCode" :"LU", "currencyCode":"EUR" ,"lang":"lu-FR"}, {"countryName" : "Romania" , "codeUrl":"ro", "countryCode" :"RO", "currencyCode":"RON" ,"lang":"en-RO"},{"countryName" : "Switzerland" , "codeUrl":"ch" , "countryCode" :"CH", "currencyCode":"CHF" ,"lang":"ch-FR"}, {"countryName" : "Australia" , "codeUrl":"au", "countryCode" :"AU", "currencyCode":"AUD" ,"lang":"en-AU"}, {"countryName" : "India"  , "codeUrl":"in", "countryCode" :"IN", "currencyCode":"INR" ,"lang":"en-IN"},{"countryName" : "Singapore" , "codeUrl":"sg" , "countryCode" :"SG", "currencyCode":"SGD" ,"lang":"en-SG"}, {"countryName" : "Hong Kong" , "codeUrl":"hk-en", "countryCode" :"HK", "currencyCode":"HKD" ,"lang":"en-HK"},{"countryName" : "Japan" , "codeUrl":"jp", "countryCode" :"JP", "currencyCode":"JPY" ,"lang":"ja-J"},{"countryName" : "Thailand" , "codeUrl":"th", "countryCode" :"TH", "currencyCode":"THB" ,"lang":"th-TH"},{"countryName" : "Korea Republic of" , "codeUrl":"kr", "countryCode" :"KR", "currencyCode":"KRW" ,"lang":"ko-KR"},{"countryName" : "Malaysia" , "codeUrl":"my" , "countryCode" :"MY", "currencyCode":"MYR" ,"lang":"en-MY"},{"countryName" : "Taiwan Region" , "codeUrl":"tw" , "countryCode" :"TW", "currencyCode":"TWD" ,"lang":"zh-TW"},{"countryName" : "South Africa" , "codeUrl":"za" , "countryCode" :"ZA", "currencyCode":"ZAR" ,"lang":"en-ZA"}]'

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'referer': 'none',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    def extract_domain_domain_url(self, real_url):
        extracted = tldextract.extract(real_url)
        domain_without_tld = extracted.domain
        domain = domain_without_tld
        domain_url = extracted.registered_domain
        return domain, domain_url
    #   "lang": "ES-es_ES",  #  lang=GB-en_GB

    def start_requests(self):
        yield scrapy.Request(
            self.start_urls,
            callback=self.country_base_url,
            headers=self.headers
        )
    @inline_requests
    def country_base_url(self, response):
        print(f'response {response}')
        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            code_url = item.get('codeUrl')
            url = f'https://www.chanel.com/{code_url}/'
            # proxy = next(self.proxy_cycle)
            country_response = requests.get(url, headers=self.headers) #, proxies={'http': proxy, 'https': proxy})
            resp = TextResponse(url=url, body=country_response.text, encoding='utf-8')
            self.get_target_urls(resp)

        json_data = json.loads(self.spec_mapping)
        country_lang = [item.get('cookie') for item in json_data]

        link_list =['https://www.chanel.com/us/fine-jewelry/rings/c/3x1x2/', 'https://www.chanel.com/us/fashion/collection/chanel-coco-beach-2024/', 'https://www.chanel.com/us/fashion/collection/metiers-art-2023-24/', 'https://www.chanel.com/us/fashion/collection/spring-summer-2024/', 'https://www.chanel.com/us/fashion/collection/spring-summer-2024-pre-collection/', 'https://www.chanel.com/us/fashion/collection/the-iconic-handbag-the-campaign/', 'https://www.chanel.com/us/fashion/ready-to-wear/', 'https://www.chanel.com/us/fashion/handbags/c/1x1x1/']
        filtered_urls = list(set(self.all_target_urls))
        cookies = ''
        headers =''
        for url in link_list:
            spl_url = url.split('.com/')[1].split('/')[0]
            for lang_code in country_lang:
                if spl_url.lower() in lang_code.lower():
                    headers = {
                        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'accept-language': 'en-GB,en;q=0.9',
                        'cache-control': 'no-cache',
                        'cookie': f'lang={lang_code}; country={spl_url.upper()};',
                        'pragma': 'no-cache',
                        'priority': 'u=0, i',
                        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"macOS"',
                        'sec-fetch-dest': 'document',
                        'sec-fetch-mode': 'navigate',
                        'sec-fetch-site': 'same-origin',
                        'sec-fetch-user': '?1',
                        'upgrade-insecure-requests': '1',
                        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
                    }
                    break
            url_response = requests.get(url, headers=headers) #, proxies={'http': proxy, 'https': proxy})
            resp = TextResponse(url='', body=url_response.text, encoding='utf-8')
            if resp.status == 200:
                self.parse(resp)
        print(f"skus ==> {len(self.sku_mapping)}")
        for sku_id, product_data in self.sku_mapping.items():
            product_url = product_data.get('product_url')
            # product_url = '/us/fine-jewelry/p/J11786/coco-crush-ring/'
            # sku_id = 'J11786'
            badge = product_data.get('badge', '')
            url = response.urljoin(product_url)
            spl_url = product_url.split('/')[1].split('/')[0]
            headers = ''
            for lang_code in country_lang:
                if spl_url.lower() in lang_code.lower():
                    headers = {
                        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'accept-language': 'en-GB,en;q=0.9',
                        'cache-control': 'no-cache',
                        'cookie': f'lang={lang_code}; country={spl_url.upper()};',
                        'pragma': 'no-cache',
                        'priority': 'u=0, i',
                        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"macOS"',
                        'sec-fetch-dest': 'document',
                        'sec-fetch-mode': 'navigate',
                        'sec-fetch-site': 'same-origin',
                        'sec-fetch-user': '?1',
                        'upgrade-insecure-requests': '1',
                        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
                    }
                    break
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=headers,
                cb_kwargs={'product_url': product_url, 'sku': sku_id, "badge": badge, 'sku_header':headers}
            )
            time.sleep(1)

    def get_target_urls(self, response):
        target_urls = response.css('ul.header__primary__links>li>a::attr(href)').extract()
        link_list = response.css('div.header__columns>div>div>ul.header__category__links>li>a::attr(href)').extract()
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
        print(f"response url === {response}")
        try:
            products = response.css('div.txt-product')
            if products is not None:
                try:
                    for product in products:
                        if products:
                            product_url = product.css("p>a::attr(href)").get()
                            badge = product.css('p.flag::text').get()
                            sku_id = product.css("a>span.is-sr-only::text").get()
                            if sku_id:
                                sku_id = sku_id.split(". ")[1]
                                self.get_all_sku_mapping(product_url, sku_id, badge)
                        else:
                            self.log("no product found ------------------------------>>>")
                            continue
                except Exception as e:
                    self.log(f"Error parsing : {e}")
        except Exception as e:
            self.log(f"Error occured parse fn{e}")
        # try:
        #     next_page_link = response.css('a.is-secondary.is-loadmore::attr(href)').get()
        #     print(f"Next page {next_page_link}")
        #     if next_page_link:
        #         next_page_url = f'https://www.chanel.com{next_page_link}'
        #         resp = Request(next_page_url, headers=self.headers, cookies=self.cookies_dict, dont_filter=True)
        #         next_page_resp = yield resp
        #         if next_page_resp.status_code == 200:
        #             self.parse(next_page_resp)
        # except Exception as e:
        #     self.log(f"pagingation {e}")

    def get_all_sku_mapping(self, product_url, sku_id, badge):
            if sku_id not in self.sku_mapping:
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}
            else:
                if isinstance(self.sku_mapping[sku_id], str):
                    self.sku_mapping[sku_id] = self.sku_mapping[sku_id]
                self.sku_mapping[sku_id] = {'product_url': product_url, 'badge': badge}

    @inline_requests
    def parse_product(self, response, product_url, sku, badge, sku_header):
        content = {}
        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": response.url,
            "sku_title": content_info["sku_title"],
            "sku_short_description": content_info["sku_short_description"],
            "sku_long_description": content_info["sku_long_description"]
        }
        specification = {}
        s_product_url = ''
        if product_url:
            s_product_url = product_url.split('/', 2)[2:]
        s_product_url = ''.join(s_product_url)
        try:
            json_data = json.loads(self.spec_mapping)
            for item in json_data:
                country_code = item.get('countryCode')
                cookie_lang = item.get('cookie')
                code_url = item.get('codeUrl')
                lang = item.get('lang')
                if 'en' in lang:
                    lang = 'en'
                elif '-' in lang:
                    lang = lang.split('-')[1]
                else:
                    lang = lang
                logging.info(f'Processing: {lang}')
                headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'accept-language': 'en-GB,en;q=0.9',
                    'cache-control': 'no-cache',
                    'cookie': f'lang={cookie_lang}; country={country_code};',
                    'pragma': 'no-cache',
                    'priority': 'u=0, i',
                    'referer': 'none',
                    'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1',
                    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
                }
                url = f"{self.base_url}/{code_url}/{s_product_url}"
                cookies = {
                    'lang': f'{cookie_lang}',
                    'country': f'{country_code}'
                }
                # proxy = next(self.proxy_cycle)
                lang_req = requests.get(url, headers=headers) #, proxies={'http': proxy,'https': proxy})
                lang_resp = TextResponse(url=url, body=lang_req.text, encoding='utf-8')
                if lang_resp.status == 403:
                    self.log(f"Received 403 Response for URL: {lang_resp.url}")
                elif lang_resp.status == 200:
                    content_info = self.collect_content_information(lang_resp)
                    content[lang] = {
                        "sku_link": url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }
                    specification_info = self.collect_specification_info(lang_resp, country_code, code_url, sku,headers)
                    specification[country_code] = specification_info
                elif lang_resp.status in [301, 302]:
                    redirected_url = lang_resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = Request(url, headers=self.headers, cookies=cookies, dont_filter=True)
                    redirected_url_resp = yield req
                    if redirected_url_resp.status == 200:
                        content_info = self.collect_content_information(redirected_url_resp)
                        content[lang] = {
                            "sku_link": url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["sku_short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
                        specification_info = self.collect_specification_info(redirected_url_resp, country_code, code_url, sku, headers)
                        specification[country_code] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {req.url}")
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return

        list_img = []
        picture_sources = response.css('button.slide-item.carousel__zoom>img')
        for pictures in picture_sources:
            pic_list = pictures.css("::attr(srcset)").getall()
            if not pic_list:
                continue
            else:
                picture = ''
                try:
                    pic_urls = ''.join(pic_list)
                    pict_list = re.findall(r'https.*?\.jpg',pic_urls)
                    picture = pict_list.pop()
                    list_img.append(picture)
                except Exception as e:
                    print(f"error {e}")
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
                            # proxy = next(self.proxy_cycle)
                            res = requests.get(url_pic,headers=sku_header) #, proxies={'http': proxy, 'https': proxy})
                            self.log(f"res img {res}")
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
        product_details = response.css('div.product-details__option')
        keys_to_match = ["Length", "Width", "Size","Diameters","Diameter","Thickness", "Weight","Height", "Heel"]
        for key in keys_to_match:
            if product_details:
                for item in product_details:
                    itemkey = item.css('div>span::text').get()
                    if itemkey:
                        value = item.css('p::text').get()
                        if key.lower() in itemkey.lower():
                            size_dimension.append(f'{key}: {value}')
        product_color = ''
        main_material = ''
        script_tag = response.css("script[type='application/ld+json']::text").extract()
        for script_data in script_tag:
            try:
                script_data = json.loads(script_data)
                if "material" in script_data:
                    main_material = script_data["material"]
                    product_color = script_data["color"]
                    break
            except Exception as e:
                print(f'Error processing script : {e}')
        all_script_tags = response.css('script::text').extract()
        for script_tag in all_script_tags:
            if '    dataLayerGA = {productList:{}}' in script_tag:
                print(script_tag)

        collection_name = response.css('span.Text_root__GCOQp.Text_heading2__vEE5O::text').get()
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_name
        item['brand'] = 'CHANEL'
        item['manufacturer'] = self.name
        item['product_badge'] = badge
        item['sku'] = sku
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        title = ''
        description = ''
        script_tags = response.css('script[type="application/ld+json"]::text').getall()
        for script_tag in script_tags:
            try:
                json_data = json.loads(script_tag)
                if "description" in json_data:
                    title = json_data['name']
                    description = json_data['description']
                    break
            except Exception as e:
                self.log(f"error occured {e}")
        sku_short_description = description
        sku_long_description = description
        return {
            "sku_title": title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, code_url, sku_id, headers):
        sale_price = resp.css("div.product-details__price-block>div>p.product-details__price::text").get()
        if sale_price:
            sale_price = sale_price.strip()
        item_url = resp.url
        currency_code = ''
        base_price = ''
        b_price = resp.css(
            "div#price-template--14296394235947__main> div> div> div.price__regular> span.price-item--regular::text").get()
        if b_price is not None:
            base_price = b_price.strip() #self.extract_price_info(b_price)
        else:
            base_price = sale_price
        shipping_time = resp.css("div.customer-support-msg").extract()
        size_available =[]
        size_url = f'https://www.chanel.com/{code_url}/p/showWfjSizeSelectionPanel?sku={sku_id}'
        # proxy = next(self.proxy_cycle)
        resp = requests.get(size_url,headers=headers) #, proxies={'http': proxy, 'https': proxy})

        print(resp.status_code)
        if resp.status_code == 200:
           if resp.text:
               html = resp.text
               selector = Selector(text=html)
               sizes = selector.css("ul.pbs-cncbox-choice-slider-content>li>button::text").extract()
               if sizes:
                 for size in sizes:
                    size_available.append(size.strip())
        availability = f'https://www.chanel.com/{code_url}/yapi/product/availability?codes={sku_id}'
        # proxy = next(self.proxy_cycle)
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(availability,headers=headers)# , proxies={'http': proxy, 'https': proxy})
        stock_value = ''
        if resp.status_code == 200:
            url_response = resp.text  # TextResponse(url='', body=resp.text, encoding='utf-8')
            parsed_response = json.loads(url_response)
            stock_value = parsed_response['stocks'][sku_id]
        product_availability = self.check_product_availability(stock_value)
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
            "shipping_lead_time": shipping_time,
            "shipping_expenses": "shipping_charge",
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": ' ',
            "reviews_number": ' ',
            "size_available": size_available,
            "sku_link": item_url
        }

    # def extract_price_info(self, price_string):
    #     match = re.search(r"([^\d]*)([\d.,]+)", price_string)
    #     if match:
    #         currency_symbol, numerical_value = match.groups()
    #         pattern = r'\,\d{3}(?![\d,])'
    #         match = re.search(pattern, numerical_value)
    #         if match:
    #             numerical_value = numerical_value.replace(",", "")
    #         pattern = r'\.\d{3}(?![\d.])'
    #         match = re.search(pattern, numerical_value)
    #         if match:
    #             numerical_value = numerical_value.replace(".", "")
    #         numerical_value = numerical_value.replace(",", ".")
    #         if '.' not in numerical_value:
    #             numerical_value = numerical_value + ".00"
    #         return numerical_value
    #     else:
    #         return None

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "IN_STOCK" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "LimitedAvailability" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "OUT_STOCK"
                return "No", out_of_stock_text
        except Exception as e:
            return "No"


