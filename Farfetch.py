import scrapy
from PIL import Image
from scrapy.utils.project import get_project_settings
from inline_requests import inline_requests
import json, random
from scrapy.http import Request, TextResponse
import time, datetime, re, tldextract, uuid, logging, os, requests
from bclowd_spider.items import ProductItem
from scrapy.linkextractors import LinkExtractor
from bclowd_spider.settings import upload_images_to_azure_blob_storage, rotate_headers

class FarfetchSpider(scrapy.Spider):
    name = "farfetch"
    sku_mapping = {}
    base_url = "https://www.farfetch.com"
    countries = ['https://www.farfetch.com/eg/', 'https://www.farfetch.com/za/', 'https://www.farfetch.com/ke/',
                 'https://www.farfetch.com/ma/', 'https://www.farfetch.com/ng/', 'https://www.farfetch.com/cn/',
                 'https://www.farfetch.com/hk/', 'https://www.farfetch.com/sg/', 'https://www.farfetch.com/in/',
                 'https://www.farfetch.com/id/', 'https://www.farfetch.com/jp/', 'https://www.farfetch.com/my/',
                 'https://www.farfetch.com/ph/', 'https://www.farfetch.com/kr/', 'https://www.farfetch.com/tw/',
                 'https://www.farfetch.com/th/', 'https://www.farfetch.com/vn/', 'https://www.farfetch.com/ru/',
                 'https://www.farfetch.com/tr/', 'https://www.farfetch.com/de/', 'https://www.farfetch.com/ie/',
                 'https://www.farfetch.com/it/', 'https://www.farfetch.com/nl/', 'https://www.farfetch.com/no/',
                 'https://www.farfetch.com/dk/', 'https://www.farfetch.com/pl/', 'https://www.farfetch.com/pt/',
                 'https://www.farfetch.com/es/', 'https://www.farfetch.com/se/', 'https://www.farfetch.com/ch/',
                 'https://www.farfetch.com/uk/', 'https://www.farfetch.com/gr/', 'https://www.farfetch.com/cz/',
                 'https://www.farfetch.com/fr/', 'https://www.farfetch.com/at/', 'https://www.farfetch.com/be/',
                 'https://www.farfetch.com/ua/', 'https://www.farfetch.com/il/', 'https://www.farfetch.com/sa/',
                 'https://www.farfetch.com/qa/', 'https://www.farfetch.com/',    'https://www.farfetch.com/ca/',
                 'https://www.farfetch.com/mx/', 'https://www.farfetch.com/au/', 'https://www.farfetch.com/nz/',
                 'https://www.farfetch.com/bo/', 'https://www.farfetch.com/br/', 'https://www.farfetch.com/cl/',
                 'https://www.farfetch.com/co/', 'https://www.farfetch.com/ec/', 'https://www.farfetch.com/ar/',
                 'https://www.farfetch.com/pe/', 'https://www.farfetch.com/uy/', 'https://www.farfetch.com/ve/']

    all_target_urls = [
        "https://www.farfetch.com/sets/new-in-this-week-eu-men.aspx",
        "https://www.farfetch.com/sets/trend_classic.aspx",
        "https://www.farfetch.com/sets/men/trend-men-edgy.aspx",
        "https://www.farfetch.com/sets/men/street-wear-men.aspx",
        "https://www.farfetch.com/sets/men/trend-men-minimal.aspx",
        "https://www.farfetch.com/sets/trend-edit-eight-men.aspx",
        "https://www.farfetch.com/sets/trend-edit-nine-men.aspx",
        "https://www.farfetch.com/sets/men/denim-edit-man.aspx",
        "https://www.farfetch.com/sets/trend-edit-three.aspx",
        "https://www.farfetch.com/sets/men/trend-edit-six.aspx",
        "https://www.farfetch.com/sets/most-wanted-pieces.aspx",
        "https://www.farfetch.com/sets/new-season-men.aspx",
        "https://www.farfetch.com/shopping/men/alexander-mcqueen/items.aspx",
        "https://www.farfetch.com/shopping/men/balenciaga/items.aspx",
        "https://www.farfetch.com/shopping/men/brunello-cucinelli/items.aspx",
        "https://www.farfetch.com/shopping/men/dolce-gabbana/items.aspx",
        "https://www.farfetch.com/shopping/men/dsquared2/items.aspx",
        "https://www.farfetch.com/shopping/men/gucci/items.aspx",
        "https://www.farfetch.com/shopping/men/kenzo/items.aspx",
        "https://www.farfetch.com/shopping/men/off-white/items.aspx",
        "https://www.farfetch.com/shopping/men/palm-angels/items.aspx",
        "https://www.farfetch.com/shopping/men/tom-ford/items.aspx",
        "https://www.farfetch.com/shopping/men/versace/items.aspx",
        "https://www.farfetch.com/shopping/men/designer-zegna/items.aspx",
        "https://www.farfetch.com/shopping/men/activewear-2/items.aspx",
        "https://www.farfetch.com/shopping/men/coats-2/items.aspx",
        "https://www.farfetch.com/shopping/men/denim-2/items.aspx",
        "https://www.farfetch.com/shopping/men/jackets-2/items.aspx",
        "https://www.farfetch.com/shopping/men/polo-shirts-2/items.aspx",
        "https://www.farfetch.com/shopping/men/pre-owned-2/items.aspx",
        "https://www.farfetch.com/shopping/men/shirts-2/items.aspx",
        "https://www.farfetch.com/shopping/men/shorts-2/items.aspx",
        "https://www.farfetch.com/shopping/men/suits-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sweaters-knitwear-2/items.aspx",
        "https://www.farfetch.com/shopping/men/beachwear-2/items.aspx",
        "https://www.farfetch.com/shopping/men/trousers-2/items.aspx",
        "https://www.farfetch.com/shopping/men/t-shirts-vests-2/items.aspx",
        "https://www.farfetch.com/shopping/men/underwear-socks-2/items.aspx",
        "https://www.farfetch.com/sets/men/new-in-this-week-eu-men.aspx",
        "https://www.farfetch.com/sets/event-dressing-men.aspx",
        "https://www.farfetch.com/sets/men/icons-edit.aspx",
        "https://www.farfetch.com/sets/exclusives-collaborations-men.aspx",
        "https://www.farfetch.com/sets/vacation-men.aspx",
        "https://www.farfetch.com/shopping/men/clothing-2/items.aspx",
        "https://www.farfetch.com/shopping/men/boots-2/items.aspx",
        "https://www.farfetch.com/shopping/men/brogues-2/items.aspx",
        "https://www.farfetch.com/shopping/men/derbies-2/items.aspx",
        "https://www.farfetch.com/shopping/men/espadrilles-2/items.aspx",
        "https://www.farfetch.com/shopping/men/flip-flops-slides-2/items.aspx",
        "https://www.farfetch.com/shopping/men/loafers-2/items.aspx",
        "https://www.farfetch.com/shopping/men/buckled-shoes-2/items.aspx",
        "https://www.farfetch.com/shopping/men/oxfords-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sandals-2/items.aspx",
        "https://www.farfetch.com/shopping/men/trainers-2/items.aspx",
        "https://www.farfetch.com/sets/trend-edit-five.aspx",
        "https://www.farfetch.com/shopping/men/shoes-2/items.aspx",
        "https://www.farfetch.com/shopping/men/trainers-2/items.aspx",
        "https://www.farfetch.com/shopping/men/hi-tops-2/items.aspx",
        "https://www.farfetch.com/shopping/men/low-tops-2/items.aspx",
        "https://www.farfetch.com/shopping/men/performance-trainers-2/items.aspx",
        "https://www.farfetch.com/sets/men/most-wanted-sneakers.aspx",
        "https://www.farfetch.com/sets/men/stadium-goods-men.aspx",
        "https://www.farfetch.com/sets/men/sneakers-exclusives-and-collaborations.aspx",
        "https://www.farfetch.com/sets/men/alexander-mcqueen-oversized-trainer-men.aspx",
        "https://www.farfetch.com/sets/men/balenciaga-speed-trainer-men.aspx",
        "https://www.farfetch.com/sets/men/balenciaga-triple-s-sneakers-men.aspx",
        "https://www.farfetch.com/sets/men/nike-air-force-1-men.aspx",
        "https://www.farfetch.com/shopping/men/jordan/trainers-2/items.aspx",
        "https://www.farfetch.com/sets/men/nike-air-max-97-men.aspx",
        "https://www.farfetch.com/sets/men/nike-dunks.aspx",
        "https://www.farfetch.com/sets/men/off-white-out-of-office.aspx",
        "https://www.farfetch.com/sets/reebok-club-c-trainers.aspx",
        "https://www.farfetch.com/shopping/men/bags-purses-2/items.aspx",
        "https://www.farfetch.com/shopping/men/backpacks-2/items.aspx",
        "https://www.farfetch.com/shopping/men/belt-bags-2/items.aspx",
        "https://www.farfetch.com/shopping/men/clutches-2/items.aspx",
        "https://www.farfetch.com/shopping/men/laptop-briefcases-2/items.aspx",
        "https://www.farfetch.com/shopping/men/luggage-holdalls-2/items.aspx",
        "https://www.farfetch.com/shopping/men/messengers-2/items.aspx",
        "https://www.farfetch.com/shopping/men/shoulder-bags-2/items.aspx",
        "https://www.farfetch.com/shopping/men/totes-2/items.aspx",
        "https://www.farfetch.com/shopping/men/pre-owned-bags-2/items.aspx",
        "https://www.farfetch.com/shopping/men/accessories-all-2/items.aspx",
        "https://www.farfetch.com/shopping/men/belts-2/items.aspx",
        "https://www.farfetch.com/sets/men/menswear-gift-list.aspx",
        "https://www.farfetch.com/shopping/men/gloves-2/items.aspx",
        "https://www.farfetch.com/shopping/men/hats-2/items.aspx",
        "https://www.farfetch.com/shopping/men/phone-computer-gadgets-2/items.aspx",
        "https://www.farfetch.com/shopping/men/scarves-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sunglasses-2/items.aspx",
        "https://www.farfetch.com/shopping/men/ties-2/items.aspx",
        "https://www.farfetch.com/shopping/men/wallets-cardholders-2/items.aspx",
        "https://www.farfetch.com/shopping/men/pre-owned-accessories-2/items.aspx",
        "https://www.farfetch.com/shopping/men/jewellery-2/items.aspx",
        "https://www.farfetch.com/shopping/men/bracelets-2/items.aspx",
        "https://www.farfetch.com/shopping/men/earrings-2/items.aspx",
        "https://www.farfetch.com/shopping/men/necklaces-2/items.aspx",
        "https://www.farfetch.com/shopping/men/rings-2/items.aspx",
        "https://www.farfetch.com/shopping/men/watches-4/items.aspx",
        "https://www.farfetch.com/sets/men/new-in-watches.aspx",
        "https://www.farfetch.com/shopping/men/contemporary-watches-2/items.aspx",
        "https://www.farfetch.com/shopping/men/watches-analog-2/items.aspx",
        "https://www.farfetch.com/shopping/men/watch-accessories-2/items.aspx",
        "https://www.farfetch.com/shopping/men/fine-watches-4/items.aspx",
        "https://www.farfetch.com/shopping/men/fine-watches-aviator-2/items.aspx",
        "https://www.farfetch.com/shopping/men/fine-watches-chronograph-2/items.aspx",
        "https://www.farfetch.com/shopping/men/fine-watches-dress-2/items.aspx",
        "https://www.farfetch.com/shopping/men/fine-watches-sports-2/items.aspx",
        "https://www.farfetch.com/shopping/men/pre-owned-fine-watches-2/items.aspx",
        "https://www.farfetch.com/shopping/men/audemars-piguet/items.aspx",
        "https://www.farfetch.com/shopping/men/bell-ross/fine-watches-4/items.aspx",
        "https://www.farfetch.com/shopping/men/frederique-constant/items.aspx",
        "https://www.farfetch.com/shopping/men/hublot/items.aspx",
        "https://www.farfetch.com/shopping/men/mad-paris/watches-4/items.aspx",
        "https://www.farfetch.com/shopping/men/patek-philippe/items.aspx",
        "https://www.farfetch.com/shopping/men/rolex-pre-owned/items.aspx",
        "https://www.farfetch.com/sets/men/most-wanted-watches.aspx",
        "https://www.farfetch.com/tag/men/pre-order",
        "https://www.farfetch.com/sets/men/trend-watches-investment-pieces.aspx",
        "https://www.farfetch.com/shopping/men/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/audio-tech-accessories-2/items.aspx",
        "https://www.farfetch.com/shopping/men/candles-home-fragrance-2/items.aspx",
        "https://www.farfetch.com/shopping/men/collectibles-2/items.aspx",
        "https://www.farfetch.com/shopping/men/dining-kitchen-2/items.aspx",
        "https://www.farfetch.com/shopping/men/furniture-2/items.aspx",
        "https://www.farfetch.com/shopping/men/home-decor-2/items.aspx",
        "https://www.farfetch.com/shopping/men/pet-accessories-2/items.aspx",
        "https://www.farfetch.com/shopping/men/soft-furninshing-textiles-2/items.aspx",
        "https://www.farfetch.com/shopping/men/stationery-2/items.aspx",
        "https://www.farfetch.com/shopping/men/assouline/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/bang-olufsen-beoplay/items.aspx",
        "https://www.farfetch.com/shopping/men/fornasetti/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/hay/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/designer-kaws/items.aspx",
        "https://www.farfetch.com/shopping/men/medicom-toy/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/off-white/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/designer-pols-potten/items.aspx",
        "https://www.farfetch.com/shopping/men/seletti/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/tom-dixon/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/versace/lifestyle-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/all/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/clothing-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/jackets-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/shirts-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/sweaters-knitwear-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/t-shirts-vests-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/shoes-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/trainers-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/bags-purses-2/items.aspx",
        "https://www.farfetch.com/shopping/men/sale/accessories-all-2/items.aspx",
        "https://www.farfetch.com/sets/new-in-this-week-eu-women.aspx",
        "https://www.farfetch.com/sets/trend-classic.aspx",
        "https://www.farfetch.com/sets/trend-edgy.aspx",
        "https://www.farfetch.com/sets/trend-glamour-icon.aspx",
        "https://www.farfetch.com/sets/women/street-wear-women.aspx",
        "https://www.farfetch.com/sets/women/trend-the-minimalist.aspx",
        "https://www.farfetch.com/sets/women/trend-feminine.aspx",
        "https://www.farfetch.com/sets/women/date-night-looks.aspx",
        "https://www.farfetch.com/shopping/women/totes-1/items.aspx",
        "https://www.farfetch.com/sets/new-season-women.aspx",
        "https://www.farfetch.com/sets/most-wanted.aspx",
        "https://www.farfetch.com/shopping/women/alexander-mcqueen/items.aspx",
        "https://www.farfetch.com/shopping/women/balenciaga/items.aspx",
        "https://www.farfetch.com/shopping/women/balmain/items.aspx",
        "https://www.farfetch.com/shopping/women/burberry/items.aspx",
        "https://www.farfetch.com/shopping/women/dolce-gabbana/items.aspx",
        "https://www.farfetch.com/shopping/women/salvatore-ferragamo/items.aspx",
        "https://www.farfetch.com/shopping/women/gucci/items.aspx",
        "https://www.farfetch.com/shopping/women/jacquemus/items.aspx",
        "https://www.farfetch.com/shopping/women/off-white/items.aspx",
        "https://www.farfetch.com/shopping/women/prada/items.aspx",
        "https://www.farfetch.com/shopping/women/saint-laurent/items.aspx",
        "https://www.farfetch.com/shopping/women/designer-valentino-garavani/items.aspx",
        "https://www.farfetch.com/shopping/women/versace/items.aspx",
        "https://www.farfetch.com/shopping/women/clothing-1/items.aspx",
        "https://www.farfetch.com/shopping/women/activewear-1/items.aspx",
        "https://www.farfetch.com/shopping/women/beachwear-1/items.aspx",
        "https://www.farfetch.com/shopping/women/coats-1/items.aspx",
        "https://www.farfetch.com/shopping/women/denim-1/items.aspx",
        "https://www.farfetch.com/shopping/women/dresses-1/items.aspx",
        "https://www.farfetch.com/shopping/women/jackets-1/items.aspx",
        "https://www.farfetch.com/shopping/women/knitwear-1/items.aspx",
        "https://www.farfetch.com/shopping/women/lingerie-hosiery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/skirts-1/items.aspx",
        "https://www.farfetch.com/shopping/women/skiwear-1/items.aspx",
        "https://www.farfetch.com/shopping/women/tops-1/items.aspx",
        "https://www.farfetch.com/shopping/women/trousers-1/items.aspx",
        "https://www.farfetch.com/sets/the-bridal-edit-women.aspx",
        "https://www.farfetch.com/sets/women/matching-sets.aspx",
        "https://www.farfetch.com/sets/partywear-women.aspx",
        "https://www.farfetch.com/sets/women/edit-essential-women.aspx",
        "https://www.farfetch.com/sets/vacation-women.aspx",
        "https://www.farfetch.com/shopping/women/shoes-1/items.aspx",
        "https://www.farfetch.com/shopping/women/ballerinas-1/items.aspx",
        "https://www.farfetch.com/shopping/women/boots-1/items.aspx",
        "https://www.farfetch.com/shopping/women/espadrilles-1/items.aspx",
        "https://www.farfetch.com/shopping/women/flip-flops-slides-1/items.aspx",
        "https://www.farfetch.com/shopping/women/loafers-1/items.aspx",
        "https://www.farfetch.com/shopping/women/mules-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pumps-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sandals-1/items.aspx",
        "https://www.farfetch.com/shopping/women/trainers-1/items.aspx",
        "https://www.farfetch.com/shopping/women/bags-purses-1/items.aspx",
        "https://www.farfetch.com/shopping/women/backpacks-1/items.aspx",
        "https://www.farfetch.com/shopping/women/beach-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/bucket-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/clutches-1/items.aspx",
        "https://www.farfetch.com/shopping/women/mini-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/satchel-cross-body-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/shoulder-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/totes-1/items.aspx",
        "https://www.farfetch.com/sets/women/iconic-bags-women.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/accessories-all-1/items.aspx",
        "https://www.farfetch.com/shopping/women/belts-1/items.aspx",
        "https://www.farfetch.com/shopping/women/glasses-frames-1/items.aspx",
        "https://www.farfetch.com/shopping/women/gloves-1/items.aspx",
        "https://www.farfetch.com/shopping/women/hair-accessories-1/items.aspx",
        "https://www.farfetch.com/shopping/women/hats-1/items.aspx",
        "https://www.farfetch.com/shopping/women/scarves-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sunglasses-1/items.aspx",
        "https://www.farfetch.com/shopping/women/wallets-purses-1/items.aspx",
        "https://www.farfetch.com/sets/women/womenswear-gift-list.aspx",
        "https://www.farfetch.com/shopping/women/jewellery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/bracelets-1/items.aspx",
        "https://www.farfetch.com/shopping/women/earrings-1/items.aspx",
        "https://www.farfetch.com/shopping/women/necklaces-1/items.aspx",
        "https://www.farfetch.com/shopping/women/rings-1/items.aspx",
        "https://www.farfetch.com/shopping/women/watches-analog-1/items.aspx",
        "https://www.farfetch.com/shopping/women/fine-jewellery-6/items.aspx",
        "https://www.farfetch.com/shopping/women/demi-fine-jewellery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/fine-bracelets-1/items.aspx",
        "https://www.farfetch.com/shopping/women/fine-earrings-1/items.aspx",
        "https://www.farfetch.com/shopping/women/fine-necklaces-1/items.aspx",
        "https://www.farfetch.com/shopping/women/fine-rings-1/items.aspx",
        "https://www.farfetch.com/shopping/women/fine-watches-3/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-fine-jewellery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/chopard/items.aspx",
        "https://www.farfetch.com/shopping/women/designer-david-yurman/items.aspx",
        "https://www.farfetch.com/shopping/women/de-beers/items.aspx",
        "https://www.farfetch.com/shopping/women/rolex-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/tasaki/items.aspx",
        "https://www.farfetch.com/shopping/women/van-cleef-arpels/items.aspx",
        "https://www.farfetch.com/shopping/women/yoko-london/items.aspx",
        "https://www.farfetch.com/shopping/women/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/audio-tech-accessories-1/items.aspx",
        "https://www.farfetch.com/shopping/women/candles-home-fragrance-1/items.aspx",
        "https://www.farfetch.com/shopping/women/collectibles-1/items.aspx",
        "https://www.farfetch.com/shopping/women/dining-kitchen-1/items.aspx",
        "https://www.farfetch.com/shopping/women/furniture-1/items.aspx",
        "https://www.farfetch.com/shopping/women/home-decor-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pet-accessories-1/items.aspx",
        "https://www.farfetch.com/shopping/women/soft-furninshing-textiles-1/items.aspx",
        "https://www.farfetch.com/shopping/women/stationery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/assouline/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/bang-olufsen-beoplay/items.aspx",
        "https://www.farfetch.com/shopping/women/fornasetti/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/gucci/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/designer-kaws/items.aspx",
        "https://www.farfetch.com/shopping/women/medicom-toy/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/designer-missoni-home/items.aspx",
        "https://www.farfetch.com/shopping/women/off-white/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/designer-pols-potten/items.aspx",
        "https://www.farfetch.com/shopping/women/seletti/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/versace/lifestyle-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-accessories-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-bags-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-coats-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-dresses-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-fine-watches-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-fine-jewellery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-jewellery-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-jackets-1/items.aspx",
        "https://www.farfetch.com/shopping/women/pre-owned-watches-1/items.aspx",
        "https://www.farfetch.com/shopping/women/cartier-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/designer-chanel-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/christian-dior-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/fendi-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/goyard-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/hermes-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/louis-vuitton-pre-owned/items.aspx",
        "https://www.farfetch.com/shopping/women/rolex-pre-owned/items.aspx",
        "https://www.farfetch.com/sets/women/chanel-pre-owned-2-55-iconic.aspx",
        "https://www.farfetch.com/sets/women/dior-vintage-saddle-bag.aspx",
        "https://www.farfetch.com/sets/women/lady-dior-bag.aspx",
        "https://www.farfetch.com/sets/women/hermes-birkin-bag-women.aspx",
        "https://www.farfetch.com/sets/women/hermes-kelly-bag.aspx",
        "https://www.farfetch.com/sets/women/louis-vuitton-monogram.aspx",
        "https://www.farfetch.com/shopping/women/sale/all/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/clothing-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/coats-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/dresses-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/tops-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/shoes-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/boots-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/trainers-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/bags-purses-1/items.aspx",
        "https://www.farfetch.com/shopping/women/sale/accessories-all-1/items.aspx",
        "https://www.farfetch.com/sets/kids/new-in-this-week-baby.aspx",
        "https://www.farfetch.com/sets/kids/new-in-this-week-kids.aspx",
        "https://www.farfetch.com/sets/kids/new-in-this-week-teens.aspx",
        "https://www.farfetch.com/sets/kids/best-sellers-kids.aspx",
        "https://www.farfetch.com/sets/kids/best-sneakers-kids.aspx",
        "https://www.farfetch.com/sets/kids/partywear-kids.aspx",
        "https://www.farfetch.com/sets/kids/kids-tracksuits.aspx",
        "https://www.farfetch.com/sets/kids/all-kids-gifts.aspx",
        "https://www.farfetch.com/sets/mini-me.aspx",
        "https://www.farfetch.com/shopping/kids/bonpoint/items.aspx",
        "https://www.farfetch.com/shopping/kids/burberry-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/dolce-gabbana-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/givenchy-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/gucci-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/designer-jordan-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/marni-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/moschino-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/stella-mccartney-kids/items.aspx",
        "https://www.farfetch.com/shopping/kids/young-versace/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-girl-accessories-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-girl-shoes-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-girl-clothing-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/babywear-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/coats-9/items.aspx",
        "https://www.farfetch.com/shopping/kids/dresses-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/jackets-9/items.aspx",
        "https://www.farfetch.com/shopping/kids/shorts-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/skirts-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/swimwear-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/tops-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/tracksuits-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/trousers-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-boy-accessories-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-boy-shoes-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-boy-clothing-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/babywear-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/coats-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/jackets-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/shorts-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/swimwear-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/tops-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/tracksuits-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/trousers-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/baby-nursery-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/changing-bags-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/strollers-5/items.aspx",
        "https://www.farfetch.com/sets/kids/baby-gifting-girls-kids.aspx",
        "https://www.farfetch.com/sets/kids/baby-gifting-boys-kids.aspx",
        "https://www.farfetch.com/shopping/kids/girls-accessories-1/items.aspx",
        "https://www.farfetch.com/shopping/kids/girls-shoes-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/girls-clothing-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/coats-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/dresses-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/denim-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/jackets-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/playsuits-jumpsuits-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/shorts-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/skirts-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/swimwear-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/tops-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/trousers-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/boys-accessories-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/boys-shoes-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/boys-clothing-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/coats-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/denim-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/jackets-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/shorts-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/swimwear-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/tops-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/tracksuits-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/trousers-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-girl-accessories-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-girl-shoes-1/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-girl-clothing-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-coats-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-denim-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-dresses-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-jackets-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-skirts-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-swimwear-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-tops-1/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-trousers-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-boy-accessories-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-boy-shoes-1/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-boy-clothing-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-coats-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-denim-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-jackets-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-shorts-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-swimwear-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-tops-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-tracksuits-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/teen-trousers-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/baby-girl-clothing-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/baby-girl-accessories-6/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/baby-boy-clothing-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/baby-boy-accessories-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/baby-nursery-5/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/girls-clothing-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/girls-accessories-1/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/girls-shoes-4/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/boys-clothing-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/boys-accessories-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/boys-shoes-3/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/teen-girl-clothing-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/teen-girl-accessories-7/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/teen-girl-shoes-1/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/teen-boy-clothing-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/teen-boy-accessories-8/items.aspx",
        "https://www.farfetch.com/shopping/kids/sale/teen-boy-shoes-1/items.aspx",
    ]

    user_agents = [
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edge/88.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/74.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/4.0.0.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Avast/88.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Kubuntu/88.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Fedora/88.0.0.0',
        # Add more user-agents as needed
    ]

    headers = {
        'User-Agent': random.choice(user_agents),
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
    handle_httpstatus_list = [429, 430, 500, 403, 443, 404]
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

    start_urls = "https://www.farfetch.com/uk/"

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
        time.sleep(10)
    @inline_requests
    def country_base_url(self, response):
        self.log(f" log response {response}")
        for country in self.countries:
            for link in self.all_target_urls:
                try:
                    new_url = link.replace('https://www.farfetch.com/', country)
                    resp = requests.get(new_url, headers=self.headers)
                    if resp.status_code == 200:
                        list_product_response = TextResponse(url='', body=resp.text, encoding='utf-8')
                        self.parse(list_product_response)
                        time.sleep(10)

                    else:
                        self.log(f"Received Response for URL:{resp.url} =={resp.status_code}")
                        time.sleep(10)

                except Exception as e:
                    self.log(f"Error occurred while processing URL {link}: {e}")
        for sku_id, product_url in self.sku_mapping.items():
            url = response.urljoin(product_url)
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                headers=self.headers,
                cb_kwargs={'product_url': product_url}
            )
            time.sleep(10)

    def parse(self, response):
        try:
            sku_id = ''
            product_elements = response.css(".ltr-cwm78i li")
            for product_ele in product_elements:
                product_url = product_ele.css('a.ltr-1t9m6yq::attr(href)').get()
                split_product_url = product_ele.css('a.ltr-1t9m6yq::attr(href)').get().split('-')[-1]
                sku_id = split_product_url.split('.')[0]
                self.get_all_sku_mapping(product_url, sku_id)

            next_page_link = response.css('.ltr-1anaw5t a::attr(href)').get()
            if next_page_link:
                next_page_resp = requests.get(next_page_link, headers=rotate_headers())
                if next_page_resp.status_code == 200:
                    product_response = TextResponse(url='', body=next_page_resp.text, encoding='utf-8')
                    self.parse(product_response)
            time.sleep(10)
        except Exception as e:
            self.log(f"Error occurred while processing URL: {e}")

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
    def parse_product(self, response, product_url):
        url_parts = product_url.split("/")
        url_without_language = "/".join(url_parts[2:])
        sku_id = ''
        content = {}
        specification = {}
        list_img = []
        brand = ''
        product_color = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            brand = json_data["brand"].get("name")
            product_color = json_data.get("color")
            sku_id = json_data.get("productID")
            image_data = json_data.get('image')
            for image_entry in image_data:
                content_url = image_entry.get('contentUrl')
                if content_url:
                    list_img.append(content_url)

        content_info = self.collect_content_information(response)
        content["en"] = {
            "sku_link": f'{self.base_url}{product_url}',
            "sku_title": content_info["sku_title"],
            "sku_long_description": content_info["sku_long_description"],
            "sku_short_description": content_info["short_description"]
        }
        languages = ["fr-FR", "es-MX", "ru-RU", "de-DE", "zh-CN"]
        for language in languages:
            logging.info(f'Processing: {language}')
            if product_url.endswith("aspx"):
                url = f'{self.base_url}/{url_without_language}?lang={language}'
            else:
                url = f'{self.base_url}/{url_without_language}&lang={language}'
            req = Request(url, headers=self.headers, dont_filter=True)
            resp = yield req
            if resp.status == 404:
                self.log(f"Received 404 Response for URL: {resp.url}")
            else:
                content_info = self.collect_content_information(resp)
                content[language.split("-")[0]] = {
                    "sku_link": resp.url,
                    "sku_title": content_info["sku_title"],
                    "sku_long_description": content_info["sku_long_description"],
                    "sku_short_description": content_info["short_description"]
                }

        try:
            for country in self.countries:
                con_code = country.split('.com/')[1]
                country_code = con_code.replace("/", "")
                url = f'{country}{url_without_language}'
                req = Request(url, headers=self.headers, dont_filter=True)
                resp = yield req
                if resp and resp.status == 200:
                    specification_info = self.collect_specification_info(resp, country_code, url)
                    specification[country_code] = specification_info
                elif resp:
                    self.log(f'Response status {resp.status} on {resp.url}')
                else:
                    self.log('Response is None')
        except json.JSONDecodeError as e:
            self.log(f'Error decoding JSON: {e}')
            return

        domain, domain_url = self.extract_domain_domain_url(response.url)
        time_stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        main_material = response.css('div.ltr-92qs1a > p.ltr-4y8w0i-Body span.ltr-4y8w0i-Body:last_child::text').get()
        product_images_info = []
        is_production = get_project_settings().get("IS_PRODUCTION")
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

        item = ProductItem()
        item['date'] = time_stamp
        item['domain'] = domain
        item['domain_url'] = domain_url
        item['collection_name'] = ''
        item['brand'] = brand
        item['manufacturer'] = brand
        item['sku'] = sku_id
        item['sku_color'] = product_color
        item['main_material'] = main_material
        item['secondary_material'] = ''
        item['image_url'] = product_images_info
        item['size_dimensions'] = ''
        item['content'] = content
        item['specification'] = specification
        yield item

    def collect_content_information(self, response):
        description = ''
        sku_title = ''
        script_tag_content = response.css('script[type="application/ld+json"]::text').getall()
        if script_tag_content:
            for json_content in script_tag_content:
                json_data = json.loads(json_content)
                if 'offers' in json_data:
                    description = json_data.get("description")
                    sku_title = json_data['name']
                    break

        short_description = response.css('.efhm1m90::text').get(default="").strip()
        discrption = response.css('.ltr-92qs1a p')
        filtered_p_tags = discrption.css('p:has(span)')
        if not filtered_p_tags:
            filtered_p_tags = discrption

        Composition = ''
        for p_tag in filtered_p_tags:
            Details = ''.join(p_tag.css('::text').getall())
            Composition += Details.strip() + " "

        Composition = Composition.strip()
        if description is None:
            description = ""

        sku_long_description = description + Composition
        return {
            "sku_title": sku_title,
            "short_description": short_description,
            "sku_long_description": sku_long_description
        }

    def collect_specification_info(self, resp, country_code, url):
        active_price = ''
        currency_code = ''
        availability_status = ''
        out_of_stock_text = ''
        product_number = url.split('/')
        productid = product_number[-1].split("-")[-1].split(".")[0]
        shipping_lead_time = self.getShipping_lead_time(productid, resp.url, country_code)
        shipping_lead_time_str = str(shipping_lead_time)
        shipping_lead_time_message = shipping_lead_time_str + ' days'
        size_available = self.get_Sizing(productid, resp.url, country_code)
        script_tag_content = resp.css('script[type="application/ld+json"]::text').get()
        if script_tag_content:
            json_data = json.loads(script_tag_content)
            price = json_data["offers"].get("price")
            # currency_code = json_data["offers"].get("priceCurrency")
            if price:
                try:
                    active_price = "{:.2f}".format(float(price))
                except ValueError:
                    print("Price is not a valid float representation.")
            else:
                active_price = price

            currency_code = json_data["offers"].get("priceCurrency")
            availability = json_data["offers"].get("availability")
            product_availability = self.check_product_availability(availability)
            availability_status = product_availability[0]
            out_of_stock_text = product_availability[1]

        base_price1 = resp.css('.ltr-zi04li p::text').get()
        if base_price1 is None:
            base_price = active_price
        else:
            price = self.extract_price_info(base_price1)
            base_price = "{:.2f}".format(float(price))

        sales_price1 = resp.css('p.ltr-1db27g6-Heading::text').get()
        if sales_price1 is None:
            sales_price = active_price
        else:
            price = self.extract_price_info(sales_price1)
            sales_price = "{:.2f}".format(float(price))

        return {
            "lang": "en",
            "domain_country_code": country_code,
            "currency": currency_code,
            "base_price": base_price,
            "sales_price": sales_price,
            "active_price": active_price,
            "stock_quantity": "",
            "availability": availability_status,
            "availability_message": out_of_stock_text,
            "shipping_lead_time": shipping_lead_time_message,
            "shipping_expenses": '',
            "marketplace_retailer_name": "",
            "condition": "NEW",
            "reviews_rating_value": "",
            "reviews_number": "",
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
                out_of_stock_text = "Temporarily out of stock"
                return "No", out_of_stock_text
        except Exception as e:
            return "No"

    def extract_price_info(self,text):
        currency_symbols = r'(\$\s*|\€\s*|\£\s*|\¥\s*|\₹\s*|\₽\s*|\₱\s*|\฿\s*|\₩\s*|\₪\s*|\₮\s*|\₦\s*|\﷼\s*|\₫\s*|\₭\s*|\₲\s*|\₴\s*|\₵\s*|\₡\s*|\₤\s*|\₣\s*|\₶\s*|\₻\s*|\₷\s*|\₸\s*|\₺\s*|\₼\s*|\₳\s*|\₠\s*|\₢\s*|\₯\s*|\₣\s*|\₤\s*|\₪\s*|\₥\s*|\₦\s*|\₧\s*|\₨\s*|\₩\s*|\₫\s*|\₭\s*|\₮\s*|\₯\s*|\₰\s*|\₱\s*|\₲\s*|\₳\s*|\₴\s*|\₵\s*|\₸\s*|\₹\s*)'
        cleaned_text = re.sub(currency_symbols, '', text)
        cleaned_text = re.sub(r'[a-zA-Z,]', '', cleaned_text)
        return cleaned_text

    def get_Sizing(self, productid, product_url, country_code ):
        if country_code != "us":
            url = f"https://www.farfetch.com/{country_code}/experience-gateway"
        else:
            url = "https://www.farfetch.com/experience-gateway"

        sizes = []
        payload = "{\"query\":\"query getSizeDetailsFitAnalyticsData($productId: ID!, $merchantId: ID, $sizeId: ID, $variationId: ID) {\\n  user {\\n    id\\n    ... on RegisteredUser {\\n      email\\n      __typename\\n    }\\n    __typename\\n  }\\n  variation(\\n    productId: $productId\\n    merchantId: $merchantId\\n    sizeId: $sizeId\\n    variationId: $variationId\\n  ) {\\n    ... on Variation {\\n      id\\n      quantity\\n      images {\\n        order\\n        size80 {\\n          url\\n          __typename\\n        }\\n        __typename\\n      }\\n      product {\\n        id\\n        gender {\\n          id\\n          name\\n          __typename\\n        }\\n        categories {\\n          id\\n          name\\n          children {\\n            id\\n            name\\n            children {\\n              id\\n              name\\n              children {\\n                id\\n                name\\n                children {\\n                  id\\n                  name\\n                  __typename\\n                }\\n                __typename\\n              }\\n              __typename\\n            }\\n            __typename\\n          }\\n          __typename\\n        }\\n        scale {\\n          id\\n          isOneSize\\n          __typename\\n        }\\n        variations {\\n          edges {\\n            node {\\n              ... on Variation {\\n                id\\n                quantity\\n                variationProperties {\\n                  ... on ScaledSizeVariationProperty {\\n                    order\\n                    values {\\n                      id\\n                      order\\n                      description\\n                      scale {\\n                        id\\n                        abbreviation\\n                        __typename\\n                      }\\n                      __typename\\n                    }\\n                    __typename\\n                  }\\n                  __typename\\n                }\\n                __typename\\n              }\\n              __typename\\n            }\\n            __typename\\n          }\\n          __typename\\n        }\\n        __typename\\n      }\\n      variationProperties {\\n        ... on ScaledSizeVariationProperty {\\n          order\\n          values {\\n            id\\n            order\\n            description\\n            scale {\\n              id\\n              __typename\\n            }\\n            __typename\\n          }\\n          __typename\\n        }\\n        __typename\\n      }\\n      price {\\n        currency {\\n          isoCode\\n          __typename\\n        }\\n        value {\\n          raw\\n          __typename\\n        }\\n        __typename\\n      }\\n      __typename\\n    }\\n    __typename\\n  }\\n}\\n\",\"variables\":{\"productId\":\"22971315\",\"variationId\":\"b210c0db-3443-4596-be6a-676cdc7d9a0f\"}}"
        payload_formatted = payload.replace("{productid}", productid)

        headers = {
            'authority': 'www.farfetch.com',
            'accept': '*/*',
            'accept-language': 'en-US',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://www.farfetch.com',
            'pragma': 'no-cache',
            'referer': 'https://www.farfetch.com/in/shopping/women/alexander-mcqueen-single-breasted-blazer-item-22971315.aspx',
            'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-full-version-list': '"Chromium";v="122.0.6261.95", "Not(A:Brand";v="24.0.0.0", "Google Chrome";v="122.0.6261.95"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'User-Agent': random.choice(self.user_agents),
            # 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'x-client-flow': 'async',
            'x-subfolder': '/in'
        }

        response = requests.request("POST", url, headers=headers, data=payload_formatted)
        try:
            json_data = response.json()
            data = json_data['data']['variation']['product']['variations']['edges']
            for item in data:
                value = item['node']['variationProperties'][0]['values'][0]['description']
                size = item['node']['variationProperties'][0]['values'][0]['scale']['abbreviation']
                sizes.append(value+size)
            return sizes
        except json.decoder.JSONDecodeError as e:
            print(f"Failed to decode JSON: {e}")
            return None

    def getShipping_lead_time(self, productid, product_url, country_code):
        if country_code != "us":
            url = f"https://www.farfetch.com/{country_code}/experience-gateway"
        else:
            url = "https://www.farfetch.com/experience-gateway"

        payload = "{\"query\":\"query getAvailabilityInfo($productId: ID!, $merchantId: ID, $sizeId: ID, $variationId: ID) {\\n  product(id: $productId, merchantId: $merchantId, sizeId: $sizeId) {\\n    ... on Product {\\n      id\\n      availableOffers {\\n        id\\n        image {\\n          alt\\n          url\\n          __typename\\n        }\\n        path\\n        __typename\\n      }\\n      __typename\\n    }\\n    __typename\\n  }\\n  variation(\\n    productId: $productId\\n    merchantId: $merchantId\\n    sizeId: $sizeId\\n    variationId: $variationId\\n  ) {\\n    ... on Variation {\\n      id\\n      shipping {\\n        stockType\\n        city {\\n          id\\n          name\\n          __typename\\n        }\\n        fulfillmentDate\\n        __typename\\n      }\\n      deliveryMethods(types: [STANDARD, EXPRESS, SAME_DAY, NINETY_MINUTES]) {\\n        type\\n        order\\n        purchaseDateInterval {\\n          start\\n          end\\n          __typename\\n        }\\n        estimatedDeliveryDateInterval {\\n          start\\n          end\\n          __typename\\n        }\\n        __typename\\n      }\\n      availabilityTypes\\n      variationProperties {\\n        ... on ScaledSizeVariationProperty {\\n          order\\n          values {\\n            scale {\\n              abbreviation\\n              id\\n              __typename\\n            }\\n            description\\n            id\\n            order\\n            __typename\\n          }\\n          __typename\\n        }\\n        ... on SizeVariationProperty {\\n          order\\n          values {\\n            id\\n            description\\n            order\\n            __typename\\n          }\\n          __typename\\n        }\\n        ... on ColorVariationProperty {\\n          values {\\n            description\\n            id\\n            order\\n            __typename\\n          }\\n          order\\n          __typename\\n        }\\n        __typename\\n      }\\n      __typename\\n    }\\n    __typename\\n  }\\n}\\n\",\"variables\":{\"productId\":\"{productid}\",\"variationId\":null}}"
        headers = {
            'authority': 'www.farfetch.com',
            'accept': '*/*',
            'accept-language': 'en-US',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://www.farfetch.com',
            'pragma': 'no-cache',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-site': 'same-origin',
            'User-Agent': random.choice(self.user_agents),
            # 'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        payload_formatted = payload.replace("{productid}", productid)
        shipping_time = ''
        start_date_components = ''
        end_date_components = ''
        try:
            response = requests.request("POST", url, headers=headers, data=payload_formatted)
            shipping_data = response.json()
            delivery_interval = shipping_data['data']['variation']['deliveryMethods']
            shipping_lead_time = {}
            for method in delivery_interval:
                if method["type"] == "EXPRESS":
                    start_date = method["estimatedDeliveryDateInterval"]["start"]
                    if start_date:
                        start_date_components = start_date.split('T')[0].split('-')
                    end_date = method["estimatedDeliveryDateInterval"]["end"]
                    if end_date:
                        end_date_components = end_date.split('T')[0].split('-')

                    shipping_lead_time["EXPRESS"] = f"{start_date} - {end_date}"
                    start_year, start_month, start_day = map(int, start_date_components)
                    end_year, end_month, end_day = map(int, end_date_components)
                    shipping_time = (end_day - start_day)

                elif method["type"] == "STANDARD":
                    start_date = method["estimatedDeliveryDateInterval"]["start"]
                    if start_date:
                        start_date_components = start_date.split('T')[0].split('-')
                    end_date = method["estimatedDeliveryDateInterval"]["end"]
                    if end_date:
                        end_date_components = end_date.split('T')[0].split('-')
                    shipping_lead_time["STANDARD"] = f"{start_date} - {end_date}"
                    start_year, start_month, start_day = map(int, start_date_components)
                    end_year, end_month, end_day = map(int, end_date_components)
                    shipping_time = (end_day - start_day)

            return shipping_time
        except json.decoder.JSONDecodeError as e:
            print(f"Failed to decode JSON: {e}")
            return None




