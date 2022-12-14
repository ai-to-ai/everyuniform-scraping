from twisted.internet import reactor
import scrapy
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.http import FormRequest
import re
from itemadapter import ItemAdapter
from shutil import which
from scrapy_selenium import SeleniumRequest
from datetime import date  
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import csv

import schedule
import time

import openpyxl

class FranchiseScrapy(scrapy.Spider):
	name="Franchise"
	base_url = "https://www.franchiseball.com"

	custom_settings={
		"ITEM_PIPELINES": {
			'__main__.CSVPipeline': 100
			},
		"FEEDS":{'everythinguniforms_%(time)s.csv': { 'format': 'csv', 'overwrite':True}},
		"LOG_ENABLED": True,
		"CONCURRENT_REQUESTS":32,
		# "SELENIUM_DRIVER_NAME" : 'chrome',
		# "SELENIUM_DRIVER_EXECUTABLE_PATH" : which('chromedriver'),
		# "SELENIUM_DRIVER_ARGUMENTS": ['--headless','--disable-logging','--log-level=3'],
		  
		# "DOWNLOADER_MIDDLEWARES" : {
		#     'scrapy_selenium.SeleniumMiddleware': 800
	    # }
	}

	brands = ['Dansko']

	def __init__(self):
		chrome_options = Options()
		chrome_options.add_argument('--headless')
		self.driver= webdriver.Chrome(executable_path = r"/Users/danielfacciolo/Desktop/uniform/chromedriver",options=chrome_options)

	def start_requests(self):
		yield scrapy.Request(url="https://www.everythinguniforms.ca/brands/",callback=self.parse_brands)

	def parse_brands(self, response):
		brands = response.xpath('//*[@class="card-title"]/a/text()').getall()
		cleaned_brands = []
		for brand in brands:
			cleaned_brands.append(cleanString(brand))
		self.brands = self.brands + cleaned_brands
		yield scrapy.Request(url="https://www.everythinguniforms.ca/",callback=self.parse_main_page)

	def parse_main_page(self, response):
		links = response.xpath('//div[@class="sideCategoryList desktop vertical in-body"]//div[@class="category-list"]//a[contains(@class,"navPages-action")  and not(contains(@class,"is-root"))]/@href').getall()

		# yield scrapy.Request(url=links[0],callback=self.parse_category)
		for category in links:
			yield scrapy.Request(url=category,callback=self.parse_category)

	def parse_category(self, response):
		print(response.url)
		productLinks = response.xpath('//figure[@class="card-figure"]/a/@href').getall()

		# yield SeleniumRequest(url=productLinks[0],callback=self.parse_product)
		# for product in productLinks:
		# 	yield SeleniumRequest(url=product,callback=self.parse_product)
		for product in productLinks:
			yield scrapy.Request(url=product,callback=self.parse_product)
				
		next_page = response.xpath('//a[@class="pagination-link" and contains(.,"Next")]/@href').get(default="NA")
		if next_page != "NA":
			yield scrapy.Request(url=next_page,callback=self.parse_category)


	def parse_product(self, response):
		print(response.url)
		colorLabels = ['Color','Colours', 'Classic','Watch']
		sizeLabels = ['XS2XL', 'Size']
		lengthLabels = ['Lengths']

		colors = []
		sizes = []
		lengths = []

		# item initialization
		item = Item()
		item['brand'] = ''
		item['desc'] = ''
		item['size'] = ''
		item['color'] = ''
		item['length'] = ''
		item['imageLink'] = ''
		item['productLink'] = ''

		# brand
		brand = response.xpath('//*[@class="productView-brand"]/a/span/text()').get(default="NA")
		item["brand"] = cleanString(brand)

		# desc
		desc = response.xpath('//*[@class="productView-title"]/text()').get(default="NA")
		desc = cleanString(desc)

		if brand == "NA":
			brand = findBrand(desc, self.brands)
			print(self.brands)
		item["brand"] = brand

		if desc.find(brand) == 0:
			item["desc"] = desc.replace(item["brand"],"")
		else:
			item["desc"] = desc
		# item["desc"] = desc

		# color/size/length
		forms = response.xpath('//div[@data-product-option-change]/div[@class="form-field"]')
		labels = response.xpath('//div[@data-product-option-change]/div[@class="form-field"]/label[contains(@class,"form-label")]/text()').getall()
		if response.url == "https://www.everythinguniforms.ca/naples-klogs-wow-comfort/":
			print(labels)
			print(forms)
		# remove special characters and filter empty string.
		

		print(labels)

		for idx,label in enumerate(labels):
			if checkAttribute(label,colorLabels):
				colors = response.xpath(f'//div[@data-product-option-change]/div[@class="form-field" and label[contains(.,"{label}")]]//option[@data-product-attribute-value]/text()').getall()
				if len(colors) == 0:
					colors = response.xpath(f'//div[@data-product-option-change]/div[@class="form-field" and label[contains(.,"{label}")]]//label[@data-product-attribute-value]/text()').getall()
				print(colors)


			elif checkAttribute(label, sizeLabels):
				sizes = response.xpath(f'//div[@data-product-option-change]/div[@class="form-field" and label[contains(.,"{label}")]]//span[@class="form-option-variant"]/text()').getall()
				if len(sizes) == 0:
					sizes = response.xpath(f'//div[@data-product-option-change]/div[@class="form-field" and label[contains(.,"{label}")]]//option[@data-product-attribute-value]/text()').getall()


			elif checkAttribute(label, lengthLabels):
				lengths = response.xpath(f'//div[@data-product-option-change]/div[@class="form-field" and label[contains(.,"{label}")]]//span[@class="form-option-variant"]/text()').getall()
				if len(lengths) == 0:
					lengths = response.xpath(f'//div[@data-product-option-change]/div[@class="form-field" and label[contains(.,"{label}")]]//option[@data-product-attribute-value]/text()').getall()


		item["productLink"] = response.url

		self.driver.get(response.url)
		# response.request.meta['driver'].get(response.url)
		if len(colors) > 0:
			for color in colors:
				item["color"] = color

				# get image link
				try:
					color_option_tag = self.driver.find_element('xpath',f'//option[contains(text(),"{color}")]')
					# color_option_tag = response.request.meta['driver'].find_element('xpath',f'//option[contains(text(),"{color}")]')
					if color_option_tag is None:
						color_option_tag = self.driver.find_element('xpath',f'//label[contains(text(),"{color}")]')
						# color_option_tag = response.request.meta['driver'].find_element('xpath',f'//label[contains(text(),"{color}")]')
					color_option_tag.click()
					time.sleep(1)
				except Exception as inst:
					self.driver.get(response.url)
					# response.request.meta['driver'].get(response.url)
					print(inst)
					
				imgTag = self.driver.find_element('xpath','//li[@class="productView-images"]/figure/img')
				# imgTag = response.request.meta['driver'].find_element('xpath','//li[@class="productView-images"]/figure/img')
				imgLink =imgTag.get_attribute("src")

				item["imageLink"] = imgLink

				# get size and length
				if len(sizes) > 0:
					for size in sizes:
						item["size"] = size
						if len(lengths) > 0:
							for length in lengths:
								item["length"] = color
								print(item)
								yield item
						else:
							print(item)
							yield item
				else:
					if len(lengths) > 0:
						for length in lengths:
							item["length"] = color
							print(item)
							yield item
					else:
						print(item)
						yield item
			
		else:
			if len(sizes) > 0:
				for size in sizes:
					item["size"] = size
					if len(lengths) > 0:
						for length in lengths:
							item["length"] = color
							print(item)
							yield item
					else:
						print(item)
						yield item
			else:
				if len(lengths) > 0:
					for length in lengths:
						item["length"] = color
						print(item)
						yield item
				else:
					print(item)
					yield item	

	def spider_closed(self, spider):
	 	self.driver.close()

def checkAttribute(label, labelList):
	label= re.sub(r'[^A-Za-z0-9]+','', label)
	if label != "":
		result = False
		for el in labelList:
			if el in label:
				result = True
		return result
	return False	

def cleanString(str):
	result = re.sub(r'[^A-Za-z0-9\s]+','', str)
	return result

def findBrand(desc, brandList):
	result = "NA"
	for brand in brandList:
		if desc.find(brand) >= 0:
			result = brand
	return result

class CSVPipeline(object):
	header = ['Product URL','Title','Body (HTML)','Vendor','Type','Tags','Published','Option1 Name','Option1 Value','Option2 Name','Option2 Value','Option3 Name','Option3 Value',	'Variant SKU',	'Variant Grams','Variant Inventory Tracker','Variant Inventory Policy','Variant Fulfillment Service','Variant Price','Variant Compare At Price','Variant Requires Shipping','Variant Taxable','Variant Barcode', 'Image Src','Image Position',	'Image Alt Text','Gift Card','SEO Title','SEO Description',	'Google Shopping / Google Product Category','Google Shopping / Gender',	'Google Shopping / Age Group',	'Google Shopping / MPN','Google Shopping / AdWords Grouping','Google Shopping / AdWords Labels',	'Google Shopping / Condition',	'Google Shopping / Custom Product',	'Google Shopping / Custom Label 0',	'Google Shopping / Custom Label 1',	'Google Shopping / Custom Label 2',	'Google Shopping / Custom Label 3',	'Google Shopping / Custom Label 4',	'Variant Image',	'Variant Weight Unit',	'Variant Tax Code',	'Cost per item',	'Status'
	]
	f = None
	write = None
	def open_spider(self, spider):

		file_date = today = date.today().isoformat()
		filename = 'everythinguniforms-'+ file_date + '.csv'
		self.f = open(filename, 'w',newline='')
		self.writer = csv.writer(self.f)
		self.writer.writerow(self.header)

	def process_item(self, item, spider):
		adapter = ItemAdapter(item)
		row = [adapter['productLink'],	adapter['desc'],'',adapter['brand'],'','','','Size',adapter["size"],'Color',adapter['color'],'Length',adapter["length"],'','','','','','','','','',	'', adapter['imageLink'],	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'',	'']
		self.writer.writerow(row)
		return item
	def close_spider(self, spider):
		self.f.close()

class Item(scrapy.Item):
    # define the fields for your item here like:
    desc = scrapy.Field()
    brand = scrapy.Field()
    size = scrapy.Field()
    color = scrapy.Field()
    length = scrapy.Field()
    imageLink = scrapy.Field()
    productLink = scrapy.Field()

def uri_params(params, spider):
    return {**params, 'spider_name': params["batch_time"]}

def start_crawl():
	print("Start Crawling...")
	configure_logging({'LOG_FORMAT': '%(levelname)s: %(message)s'})
	runner = CrawlerRunner()
	d = runner.crawl(FranchiseScrapy)
	d.addBoth(lambda _: reactor.stop())
	reactor.run()

start_crawl()