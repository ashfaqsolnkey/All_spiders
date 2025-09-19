import scrapy
from scrapy import Request
from inline_requests import inline_requests
from scrapy.http import TextResponse
from scrapy.utils.project import get_project_settings
from PIL import Image
from itertools import cycle
import time, datetime, re, tldextract, uuid, logging, os, requests, json, cloudscraper, asyncio, aiohttp
from bclowd_spider.items import ProductItem
from urllib.parse import urljoin
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

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


async def get_page(session, url, proxy_cycle):
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
        task = asyncio.create_task(get_page(session, url, proxy_cycle))
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


class coach(scrapy.Spider):
    name = "Coach"
    all_target_urls = []
    sku_mapping = {}
    base_url = "https://www.coach.com/"
    handle_httpstatus_list = [404, 400, 429, 403, 500, 430]
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

    start_urls = "https://www.coach.com/"
    spec_mapping = '[{"countryName": "us", "lang" : "en", "codeUrl" : "en_US"},{"countryName": "es", "lang" : "es", "codeUrl" : "es_ES"}, {"countryName": "uk", "lang" : "en", "codeUrl" : ""}]'

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
            headers=self.headers,
        )

    @inline_requests
    def country_base_url(self, response):
        # country_mappings_json = json.loads(self.spec_mapping)
        # for country_mapping_json in country_mappings_json:
        #     country_code = country_mapping_json.get("countryName")
        #     proxy = next(self.proxy_cycle)
        #     session = requests.Session()
        #     if "us" in country_code:
        #         link = "https://www.coach.com/"
        #     else:
        #         link = "https://"+country_code+".coach.com/"
        #     scraper = cloudscraper.create_scraper(browser={'platform': 'windows', 'browser': 'chrome', 'mobile': False},
        #                                           sess=session)
        #     country_resp = scraper.get(link, headers=self.headers, proxies={'http': proxy, 'https': proxy})
        #     if country_resp.status_code == 200:
        #         list_product_response = TextResponse(url='', body=country_resp.text, encoding='utf-8')
        #         self.get_target_urls(list_product_response, link)
        # us_url = ['https://www.coach.com/api/get-shop/women/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/the-coach-originals?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/collections/tabby?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/shoulder-bags-hobos?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/crossbody-bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/totes-carryalls?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/satchels-top-handles?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/clutches?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/handbags/backpacks?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/wallets-wristlets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/wallets-wristlets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/wallets-wristlets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/wallets-wristlets/small-wallets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/wallets-wristlets/large-wallets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/wallets-wristlets/wristlets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/wallets-wristlets/card-cases?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/shoes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes/flats?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes/sneakers?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes/boots-booties?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes/heels?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/shoes/sandals?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/accessories?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/jewelry?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/watches?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/belts?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/eyewear?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/fragrance?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/hats-scarves-gloves?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/product-care?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/accessories/tech-travel?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/ready-to-wear?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/ready-to-wear/jackets-outerwear?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/ready-to-wear/tops?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/ready-to-wear/bottoms?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/ready-to-wear/dresses?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/sale/womens-sale/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/for-her/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/customization/for-her/all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/bags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/bags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/bags/backpacks?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/bags/messenger-crossbody?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/bags/totes-duffles?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/bags/briefcases?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/wallets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/wallets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/wallets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/wallets/card-cases?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/wallets/billfolds?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/wallets/large-wallets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/shoes/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/shoes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/shoes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/shoes/sneakers?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/shoes/loafers-drivers?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/shoes/boots?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/shoes/sandals-slides?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/accessories?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/watches?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/belts?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/view-all?filterCategory=Jewelry?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/hats-scarves-gloves?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/fragrance?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/sunglasses?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/tech-travel?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/accessories/product-care?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/ready-to-wear?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/ready-to-wear/jackets-outerwear?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/men/ready-to-wear/tops-bottoms?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/sale/mens-sale/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/for-him/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/customization/for-him/all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/spring-collection?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/on-your-own-time?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/shop-by?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/womens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/mens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/on-your-own-time?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/top-25?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/bestsellers?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coach-reloved?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coach-reloved?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coach-reloved/new-arrivals?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/explore-sustainable-materials?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coach-reloved/explore-coach-cares?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/collections/tabby?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/collections/tabby?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/collections/new-york-collection?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/the-coach-originals?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/collections/rogue?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/disney-x-coach?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/trending-now?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/new/featured/trending-now?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/women/edits/matching-styles?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/view-all?gender=Women?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/view-all?gender=Men?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/gifts/gift-services/gift-cards?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/sale/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/made-to-order-tabby?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/made-to-order-tabby?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/customization/made-to-order-rogue/design-your-rogue?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/customization/for-her/all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/view-all?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/new?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/accessories?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/clothes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/alter-ego-collection?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/coachtopia-loop?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/gifts?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/new-bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/totes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/shoulder-bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/crossbody-bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/mini-bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/backpacks?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/coachtopia-loop?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/bags/ergo-bags?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/alter-ego-collection?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/accessories?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/accessories?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/accessories/new-accessories?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/wallets/view-all-wallets?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/accessories/bag-charms-and-stickers?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/accessories/bag-straps?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/accessories/hats?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/shoes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/clothes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/all/clothes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/clothes/new-clothes?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/clothes/tops?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/clothes/bottoms?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia/the-road-to-circularity?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia/community-action?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia/how-to-coachtopia-1?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/about?__v__=9TN5D6GskzKf1aJIC-y5E', 'https://www.coach.com/api/get-shop/coachtopia/stores?__v__=9TN5D6GskzKf1aJIC-y5E']
        filtered_urls = ["https://www.coach.com/api/get-shop/women/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/the-coach-originals?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/collections/tabby?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/shoulder-bags-hobos?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/crossbody-bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/totes-carryalls?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/satchels-top-handles?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/clutches?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/handbags/backpacks?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/wallets-wristlets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/wallets-wristlets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/wallets-wristlets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/wallets-wristlets/small-wallets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/wallets-wristlets/large-wallets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/wallets-wristlets/wristlets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/wallets-wristlets/card-cases?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/shoes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes/flats?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes/sneakers?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes/boots-booties?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes/heels?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/shoes/sandals?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/accessories?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/jewelry?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/watches?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/belts?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/eyewear?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/fragrance?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/hats-scarves-gloves?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/product-care?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/accessories/tech-travel?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/ready-to-wear?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/ready-to-wear/jackets-outerwear?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/ready-to-wear/tops?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/ready-to-wear/bottoms?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/ready-to-wear/dresses?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/sale/womens-sale/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/for-her/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/customization/for-her/all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/bags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/bags/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/bags/backpacks?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/bags/messenger-crossbody?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/bags/totes-duffles?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/bags/briefcases?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/wallets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/wallets/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/wallets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/wallets/card-cases?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/wallets/billfolds?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/wallets/large-wallets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/shoes/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/shoes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/shoes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/shoes/sneakers?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/shoes/loafers-drivers?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/shoes/boots?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/shoes/sandals-slides?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/accessories?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/watches?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/belts?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/view-all?filterCategory=Jewelry?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/bag-accessories-keychains?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/hats-scarves-gloves?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/fragrance?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/sunglasses?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/tech-travel?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/accessories/product-care?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/ready-to-wear/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/ready-to-wear?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/ready-to-wear/jackets-outerwear?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/men/ready-to-wear/tops-bottoms?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/sale/mens-sale/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/for-him/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/customization/for-him/all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/spring-collection?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/on-your-own-time?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/shop-by?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/womens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/mens-new-arrivals/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/on-your-own-time?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/top-25?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/bestsellers?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coach-reloved?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coach-reloved?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coach-reloved/new-arrivals?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/explore-sustainable-materials?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coach-reloved/explore-coach-cares?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/collections/tabby?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/collections/tabby?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/collections/new-york-collection?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/the-coach-originals?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/collections/rogue?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/disney-x-coach?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/trending-now?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/new/featured/trending-now?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/women/edits/matching-styles?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/view-all?gender=Women?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/view-all?gender=Men?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/gifts/gift-services/gift-cards?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/sale/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/made-to-order-tabby?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/made-to-order-tabby?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/customization/made-to-order-rogue/design-your-rogue?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/customization/for-her/all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/view-all?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/new?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/accessories?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/clothes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/alter-ego-collection?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/coachtopia-loop?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/gifts?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/new-bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/totes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/shoulder-bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/crossbody-bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/mini-bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/backpacks?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/coachtopia-loop?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/bags/ergo-bags?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/alter-ego-collection?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/accessories?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/accessories?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/accessories/new-accessories?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/wallets/view-all-wallets?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/accessories/bag-charms-and-stickers?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/accessories/bag-straps?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/accessories/hats?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/shoes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/clothes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/all/clothes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/clothes/new-clothes?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/clothes/tops?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/clothes/bottoms?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia/the-road-to-circularity?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia/community-action?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/the-world-of-coachtopia/how-to-coachtopia-1?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://www.coach.com/api/get-shop/coachtopia/stores?__v__=9TN5D6GskzKf1aJIC-y5E",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/bolsos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/pequenos-articulos-de-piel?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/confeccion?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/calzado?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/accesorios?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/bolsos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/carteras?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/confeccion?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/calzado?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-hombre/accesorios?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/a-su-propio-ritmo?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/la-edicion-de-primavera?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/inspirate/ediciones-y-colecciones/a-la-ultima-tela-vaquera-vintage?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/inspirate/ediciones-y-colecciones/guia-de-regalos-para-el-dia-de-la-madre?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/superventas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/comprar-por/ediciones-y-colecciones?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/inspirate/ediciones-y-colecciones/a-la-ultima-tela-vaquera-vintage?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/inspirate/ediciones-y-colecciones/estilo-neoyorquino?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/inspirate/ediciones-y-colecciones/the-coach-originals?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/inspirate/ediciones-y-colecciones/guia-de-regalos-para-el-dia-de-la-madre?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/nuevo/novedades-para-mujer/superventas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/comprar-por/diario?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/comprar-por/diario/workwear?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/comprar-por/diario/fin-de-semana?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-de-hombro?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-cruzados?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-satchel?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-tote?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-de-mano?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/mochilas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-de-la-firma?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/pequenos-articulos-de-piel/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/pequenos-articulos-de-piel/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/pequenos-articulos-de-piel/carteras?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/pequenos-articulos-de-piel/tarjeteros?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/pequenos-articulos-de-piel/carteras-bandolera?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/pequenos-articulos-de-piel/bolsos-pouch?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/joyeria?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/cinturones?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/relojes?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/sombreros-panuelos-y-guantes?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/charms-para-bolso-y-llaveros?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/tecnologia-y-viajes?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/gafas-de-sol?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/accesorios-y-joyas/perfume?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/abrigos-y-chaquetas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/jerseis-y-sudaderas-con-capucha?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/piezas-superiores-y-camisetas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/vestidos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/confeccion/piezas-inferiores?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/mocasin?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/calzado-plano?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/botas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/tacones?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/sandalias?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/zapatillas-deportivas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/mochilas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/bolsos-tote-y-duffle?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/bolsos-messenger?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/maletines?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/carteras-y-tarjeteros/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/carteras-y-tarjeteros/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/carteras-y-tarjeteros/tarjeteros?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/carteras-y-tarjeteros/carteras?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/confeccion/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/confeccion/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/confeccion/abrigos-y-chaquetas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/confeccion/partes-superiores-e-inferiores?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/zapatillas-deportivas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/informal?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/botas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/cinturones?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/gafas-de-sol?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/tecnologia-y-viajes?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/relojes?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/sombreros-panuelos-y-guantes?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/accesorios/perfume?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/trajes-para-hombre?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/comprar-por/trajes-para-hombre/workwear?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/comprar-por/trajes-para-hombre/fin-de-semana?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-de-hombro?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-cruzados?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-satchel?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-tote?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-de-mano?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/bolsos/bolsos-de-la-firma?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/mochilas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/bolsos-tote-y-duffle?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/bolsos-messenger?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/bolsos/maletines?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/tabby?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/tabby?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/bolso-tabby/tabby-de-cadena?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/coleccion/tabby/tabby-acolchado?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/coleccion/tabby/bolso-de-hombro-tabby?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/coleccion/tabby/soft-tabby?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/tabby?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/brooklyn?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/lana?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/juliet?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/bolsos/coleccion/sauce?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/mocasin?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/calzado-plano?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/botas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/tacones?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/sandalias?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mujer/calzado/zapatillas-deportivas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/ver-todos?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/zapatillas-deportivas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/informal?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/hombre/calzado/botas?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mundo-de-coach/pasarela-primavera-2025?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mundo-de-coach/a-su-propio-ritmo?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mundo-de-coach/desfile-de-otono-2025?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/mundo-de-coach/pasarela-primavera-2025?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://es.coach.com/api/get-shop/oculto/el-valor-de-la-autenticidad?__v__=XSKQZc9KHa6yCXSgst1Z0",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/sacs?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/petits-articles-de-maroquinerie?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/pret-a-porter?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/chaussures?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/accessoires?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/sacs?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/portefeuilles?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/pret-a-porter?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/chaussures?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-homme/accessoires?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/a-votre-propre-rythme?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/la-collection-printemps?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/soyez-inspires/editions-et-collections/tendance%C2%A0-denim?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/best-sellers?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/trier-par/editions-et-collections?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/soyez-inspires/editions-et-collections/tendance%C2%A0-denim?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/soyez-inspires/editions-et-collections/modele-new-yorkais?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/soyez-inspires/editions-et-collections/the-coach-originals?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/nouveautes/nouveautes-femme/best-sellers?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/trier-par/tous-les-jours?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/trier-par/tous-les-jours/vetements-de-travail?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/trier-par/tous-les-jours/week-end?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-epaule?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-a-bandouliere?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacoches?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/cabas?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/pochettes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-a-dos?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-exclusifs?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/petits-articles-de-maroquinerie/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/petits-articles-de-maroquinerie/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/petits-articles-de-maroquinerie/portefeuilles?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/petits-articles-de-maroquinerie/porte-cartes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/petits-articles-de-maroquinerie/portefeuilles-a-bandouliere?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/petits-articles-de-maroquinerie/wristlets?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/joaillerie?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/ceintures?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/montres?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/bonnets-echarpes-et-gants?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/breloques-de-sacs-et-porte-cles?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/appareils-electroniques-et-voyage?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/lunettes-de-soleil?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/accessoires-et-bijoux/parfum?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/manteaux-et-vestes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/pulls-et-sweats-a-capuche?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/hauts-et-t-shirts?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/robes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/pret-a-porter/bas?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/mocassins?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/chaussures-plates?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/bottes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/chaussures-a-talons?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/sandales?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/tennis?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/sacs-a-dos?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/cabas-et-sacs-duffle?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/sacs-messenger?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/porte-documents?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/portefeuilles-et-porte-cartes/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/portefeuilles-et-porte-cartes/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/portefeuilles-et-porte-cartes/porte-cartes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/portefeuilles-et-porte-cartes/portefeuilles?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/pret-a-porter/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/pret-a-porter/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/pret-a-porter/manteaux-et-vestes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/pret-a-porter/hauts-et-bas?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/tennis?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/casual?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/bottes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/ceintures?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/lunettes-de-soleil?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/appareils-electroniques-et-voyage?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/montres?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/bonnets-echarpes-et-gants?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/accessoires/parfum?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/editions-homme?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/trier-par/editions-homme/vetements-de-travail?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/trier-par/editions-homme/week-end?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-epaule?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-a-bandouliere?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacoches?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/cabas?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/pochettes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/sacs/sacs-exclusifs?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/sacs-a-dos?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/cabas-et-sacs-duffle?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/sacs-messenger?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/sacs/porte-documents?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/tabby?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/tabby?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/sac-tabby/tabby-chaine?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/collection/tabby/tabby-matelasse?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/collection/tabby/sac-epaule-tabby?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/collection/tabby/soft-tabby?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/tabby?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/brooklyn?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/lana?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/juliet?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/sacs/collection/willow?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/mocassins?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/chaussures-plates?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/bottes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/chaussures-a-talons?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/sandales?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/femme/chaussures/tennis?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/afficher-tout?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/tennis?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/casual?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/homme/chaussures/bottes?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/le-monde-de-coach/defile-printemps%C2%A02025?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/le-monde-de-coach/a-votre-propre-rythme?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/le-monde-de-coach/defile-automne%C2%A02025?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/le-monde-de-coach/defile-printemps%C2%A02025?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://fr.coach.com/api/get-shop/masque/le-courage-d%E2%80%99etre-soi-meme?__v__=N4RHXQDSdAGRB6oDB_96r",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/kleine-lederaccessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/kleidung?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/schuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-damen/accessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/portemonnaies?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/kleidung?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/schuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/neuheiten-fur-herren/accessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/nach-ihrem-eigenen-rhythmus?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/im-trend-vintage-denim?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/der-fruhlings-edit?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/bestseller?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/im-trend-vintage-denim?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/new-york-style?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/the-coach-originals?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/wochenende-in-der-stadt?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/buro-looks?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/geschenke/fur-sie/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/lassen-sie-sich-inspirieren/bestseller?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/schultertaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/umhangetaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/satchels?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/tote-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/clutch-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/rucksacke?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/signature-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleine-lederaccessoires/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleine-lederaccessoires/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleine-lederaccessoires/portemonnaies?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleine-lederaccessoires/kartenetuis?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleine-lederaccessoires/umhangetaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleine-lederaccessoires/taschen-mit-handschlaufe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/schmuck?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/gurtel?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/uhren?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/hute-mutzen-schals-und-handschuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/taschenanhanger-und-schlusselanhanger?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/elektronik-und-reise?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/sonnenbrillen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/accessoires-und-schmuck/duft?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/mantel-und-jacken?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/pullover-und-hoodies?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/oberteile-und-t-shirts?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/kleider?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/kleidung/unterteile?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/loafers?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/flache-schuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/stiefel?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/high-heels?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/sandalen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/sneaker?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/rucksacke?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/totes-und-reisetaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/aktentaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/kuriertaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/portemonnaies-und-kartenetuis/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/portemonnaies-und-kartenetuis/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/portemonnaies-und-kartenetuis/portemonnaies?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/portemonnaies-und-kartenetuis/kartenetuis?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/kleidung/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/kleidung/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/kleidung/mantel-und-jacken?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/kleidung/oberteile-und-unterteile?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/sneaker?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/casual?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/stiefel?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/gurtel?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/sonnenbrillen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/elektronik-und-reise?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/uhren?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/hute-mutzen-schals-und-handschuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/accessoires/duft?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/schultertaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/umhangetaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/satchels?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/tote-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/clutch-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/taschen/signature-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/rucksacke?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/totes-und-reisetaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/kuriertaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/taschen/aktentaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/tabby?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/tabby?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/tabby/tabby-mit-kette?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/kollektion/tabby/gesteppte-tabby?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/kollektion/tabby/tabby-schultertasche?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/kollektion/tabby/soft-tabby?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/tabby?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/brooklyn?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/lana?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/juliet?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/weide?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/taschen/kollektion/gotham?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/loafers?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/flache-schuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/stiefel?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/high-heels?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/sandalen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/damen/schuhe/sneaker?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/sneaker?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/casual?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/herren/schuhe/stiefel?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coach-welt/runway-fruhjahr%C2%A02025?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coach-welt/nach-ihrem-eigenen-rhythmus?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coach-welt/herbst%C2%A02025-runway?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coach-welt/runway-fruhjahr%C2%A02025?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/versteckt/courage-to-be-real?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/neu/kooperationen/kultartikel-von-coach?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/alle-anzeigen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/neu?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/kleidung?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/accessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen/neue-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen/ergo-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen/schultertaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen/umhangetaschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen/totes?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/taschen/mini-taschen?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/accessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/accessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/accessoires/neue-accessoires?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/kleidung?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/alle/kleidung?__v__=Pkh5WJ59qf-gjm5fD6Evt",
                         "https://de.coach.com/api/get-shop/coachtopia/kleidung/neue-kleidung?__v__=Pkh5WJ59qf-gjm5fD6Evt"]
        for url in filtered_urls:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) Gecko/20100101 Firefox/110.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            page_counter = 1
            total_page = None
            request = scrapy.Request(url, headers=headers, dont_filter=True)
            resp = yield request
            if resp.status == 200:
                self.parse(resp, page_counter, url, total_page)
            else:
                self.log(f"Received Response for URL: {resp.status}")

        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url, 'sku': sku_id}
            )

    def get_target_urls(self, response, base_url):
        script_tag = response.css('script#__NEXT_DATA__::text').get()
        if script_tag:
            try:
                json_data = json.loads(script_tag)
                buildId = json_data.get("buildId")
                menu_data = json_data['props']['pageProps']['menuData']
                for key in menu_data:
                    if isinstance(menu_data[key], dict) and 'url' in menu_data[key]:
                        url = urljoin(response.url, menu_data[key]['url'])
                        if "shop" in url:
                            split_url = url.split("shop/")[1]
                            link = f"/api/get-shop/{split_url}?__v__={buildId}"
                            absolute_url = urljoin(base_url, link)
                            self.all_target_urls.append(absolute_url)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to decode JSON: {e}")
        else:
            self.logger.error("Script tag with __NEXT_DATA__ not found.")

    def parse(self, response, page_counter, link, total_page):
        all_products = []
        json_data = ''
        if not response.text.strip():
            self.logger.error(f"Empty response from URL: {link}")
            return
        try:
            json_data = json.loads(response.text)
            if json_data and "error" not in json_data:
                try:
                    total_page = json_data.get('pageData', {}).get('totalPages', 0)
                    all_products = json_data['pageData']['products']
                    for product in all_products:
                        try:
                            sku_id = product.get("masterId")
                            product_url = product.get("url")
                            absolute_url = urljoin(link, "/api" + product_url)
                            self.get_all_sku_mapping(absolute_url, sku_id)
                        except json.JSONDecodeError as e:
                            self.logger.error(f"Failed to decode JSON: {e}")
                except Exception as e:
                    print(" Exception in parse :", e)
        except json.JSONDecodeError as e:
            print("JSON parsing error:", e)

        # if all_products and len(all_products) > 2 and int(page_counter) <= int(total_page):
        if int(page_counter) <= int(total_page):
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
                        self.parse(product_response, counter, link, total_page)

            except Exception as e:
                self.logger.error(f"Error while paginating: {e}")

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
        list_img = set()
        color = ''
        brand = ''
        main_material = ''

        url_parts = product_url.split(".com")[1]
        try:
            json_data = json.loads(response.text)
            details = json_data['pageData']
            if 'imageGroups' in details and details['imageGroups']:
                image_group = details['imageGroups'][0]
                for image in image_group['images']:
                    src = image.get('src')
                    color = image.get('title')
                    list_img.add(src)
            brand = details.get('brand')
            selectedVariantGroupData = details['selectedVariantGroupData']
            if selectedVariantGroupData and 'materialName' in selectedVariantGroupData:
                main_material = selectedVariantGroupData.get('materialName')
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON: {e}")
        size_dimension = []
        content = {}
        specification = {}
        lang = '[{"countryName": "es", "lang" : "es"}, {"countryName": "us", "lang" : "en"}]'
        json_data = json.loads(lang)
        for item in json_data:
            language = item.get('lang')
            countryName = item.get('countryName')
            try:
                if "us" in countryName:
                    country_url = f"https://www.coach.com{url_parts}"
                else:
                    country_url = f"https://{countryName}.coach.com{url_parts}"
                req = scrapy.Request(country_url, headers=self.headers, dont_filter=True)
                content_response = yield req
                if content_response.status == 404:
                    self.log(f"Received 404 Response for URL: {content_response.url}")
                elif content_response.status in [301, 302]:
                    try:
                        redirected_url = content_response.headers.get('Location').decode('utf-8')
                        url = response.urljoin(redirected_url)
                        content_retry_req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                        content_retry_resp = yield content_retry_req
                        content_info = self.collect_content_information(content_retry_resp)
                        content[language] = {
                            "sku_link": url,
                            "sku_title": content_info["sku_title"],
                            "sku_short_description": content_info["short_description"],
                            "sku_long_description": content_info["sku_long_description"]
                        }
                    except Exception as e:
                        print("Error in content: ", e)
                else:
                    content_info = self.collect_content_information(content_response)
                    content[language] = {
                        "sku_link": country_url,
                        "sku_title": content_info["sku_title"],
                        "sku_short_description": content_info["sku_short_description"],
                        "sku_long_description": content_info["sku_long_description"]
                    }

            except Exception as e:
                print("Error in content: ", e)

        json_data = json.loads(self.spec_mapping)
        for item in json_data:
            table_rows = ''
            countryName = item.get('countryName')
            language = item.get('lang')
            try:
                shipping_api = f"https://uk.coach.com//support/shipping-details"
                req = scrapy.Request(shipping_api, headers=self.headers, dont_filter=True)
                shipping_resp = yield req
                if shipping_resp.status == 200:
                    table_rows = shipping_resp.css('tr')[1:]
            except Exception as e:
                logging.error(f"Error processing Shipping: {e}")
            try:
                if countryName == ['au', '']:
                    country_url = f"https://www.coach{countryName}.com{url_parts}"
                elif "us" in countryName:
                    country_url = f"https://www.coach.com{url_parts}"

                else:
                    country_url = f"https://{countryName}.coach.com{url_parts}"
                req = scrapy.Request(country_url, headers=self.headers, dont_filter=True)
                country_resp = yield req
                if country_resp.status == 200:
                    specification_info = self.collect_specification_info(country_resp, table_rows, language,
                                                                         country_url, countryName)
                    if specification_info:
                        specification[countryName.lower()] = specification_info
                elif country_resp.status in [301, 302]:
                    redirected_url = country_resp.headers.get(b'Location').decode('utf-8')
                    url = response.urljoin(redirected_url)
                    req = scrapy.Request(url, headers=self.headers, dont_filter=True)
                    country_resp = yield req
                    if country_resp.status == 200:
                        specification_info = self.collect_specification_info(country_resp, table_rows, language,
                                                                             country_url, countryName)
                        if specification_info:
                            specification[countryName.lower()] = specification_info
                else:
                    self.log(f"Received 404 Response for URL: {country_resp.url}")
            except json.JSONDecodeError as e:
                self.log(f'Error decoding JSON: {e}')
                return

        is_production = get_project_settings().get("IS_PRODUCTION")
        product_images_info = []
        if is_production:
            product_images_info = upload_images_to_azure_blob_storage(
                self, list_img
            )
        else:
            if list_img:
                directory = self.directory + sku + "/"
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
                        image_path = os.path.join(directory, filename)
                        with open(
                                os.path.join(directory, filename), "wb"
                        ) as img_file:
                            img_file.write(res.body)
                        product_images_info.append(image_path)
                    except Exception as e:
                        logging.error(f"Error processing image: {e}")

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        secondary_material = ''
        collection_name = ''
        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = collection_name
        item['brand'] = brand
        item['manufacturer'] = self.name
        item['product_badge'] = ''
        item['sku'] = sku
        item['sku_color'] = color
        item['main_material'] = main_material
        item['secondary_material'] = ' '.join(secondary_material)
        item['image_url'] = product_images_info
        item['size_dimensions'] = size_dimension
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        title = ''
        sku_long_description_text = ''
        sku_short_description = ''
        try:
            json_data = json.loads(response.text)
            details = json_data['pageData']
            title = details.get('name')
            sku_long_description = details.get('longDescription')
            sku_short_description = details.get('shortDescription')
            if sku_long_description:
                sku_long_description_clean = re.sub(r"<[^>]+>", "", sku_long_description).strip()
                sku_long_description_text = sku_short_description + sku_long_description_clean
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON: {e}")

        return {
            "sku_title": title,
            "sku_short_description": sku_short_description,
            "sku_long_description": sku_long_description_text
        }

    def collect_specification_info(self, country_resp, table_rows, language, country_url, countryName):
        sizes = []
        availability = ''
        inventoryStock = ''
        rating = ''
        review_count = ''
        sale_price = ''
        currency_code = ''
        shipping_expenses = ''
        shipping_lead_time = ''
        try:
            json_data = json.loads(country_resp.text)
            details = json_data['pageData']
            price = details['prices'].get('currentPrice')
            sale_price = str(price)
            inventoryStock = details['inventory'].get('stockLevel')
            currency_code = details['pickedProps'].get('currency')
            selectedVariantGroupData = details['selectedVariantGroupData']
            if selectedVariantGroupData and "offers" in selectedVariantGroupData:
                availability = selectedVariantGroupData["offers"].get("availability")
                rating = selectedVariantGroupData['customAttributes'].get('c_avgRatingEmplifi')
                review_count = selectedVariantGroupData['customAttributes'].get('c_revCountEmplifi')
                variation_attributes = details['selectedVariantGroupData'].get('variationAttributes')
                for attribute in variation_attributes:
                    if attribute['id'] == 'size':
                        for size in attribute['values']:
                            if size['orderable']:
                                sizes.append(size['name'])
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON: {e}")
        if sale_price in [None, "None", "null", ""]:
            return
        for row in table_rows:
            shipping_expenses = row.css('td:nth-child(2)::text').get().strip()
            shipping_lead_time = row.css('td:nth-child(3)::text').get().strip()

        product_availability = self.check_product_availability(availability)
        availability_status = product_availability[0]
        out_of_stock_text = product_availability[1]

        return {
            "lang": language.lower(),
            "domain_country_code": countryName.lower(),
            "currency": currency_code,
            "base_price": sale_price if sale_price else 0.0,
            "sales_price": sale_price if sale_price else 0.0,
            "active_price": sale_price if sale_price else 0.0,
            "stock_quantity": inventoryStock,
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time,
            "shipping_expenses": shipping_expenses,
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": rating,
            "reviews_number": review_count,
            "size_available": sizes,
            "sku_link": country_url
        }

    def check_product_availability(self, availability):
        try:
            availability_value = availability.lower()
            if "instock" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "instoreonly" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            elif "limitedavailability" in availability_value:
                out_of_stock_text = "AVAILABLE"
                return "Yes", out_of_stock_text
            else:
                out_of_stock_text = "Product Out of Stock"
                return "No", out_of_stock_text
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return