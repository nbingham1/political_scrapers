#!/usr/bin/python

import httplib
import urllib
import urllib2 
import requests
import json
import os.path
import gzip
import io
import unicodedata
import re
import enchant


from pyhtml.html import *
from pyhtml.parse import *

def depth(addr1, addr2):
	for i, (a, b) in enumerate(zip(addr1, addr2)):
		if a != b:
			return i

word_names = set(["rusty", "hicks", "abbey", "albert", "allie", "amber", "andrew", "angel", "april", "april", "art", "august", "aurora", "autumn", "baldric", "barb", "bay", "bill", "bob", "booth", "brad", "brandy", "brook", "buck", "candy", "carol", "carole", "cat", "chad", "charity", "chase", "chip", "christian", "chuck", "clay", "cliff", "colt", "cricket", "crystal", "daisy", "dale", "dale", "dash", "dawn", "dean", "derrick", "destiny", "dick", "dixie", "dolly", "don", "dori", "dory", "dot", "earl", "ebony", "elle", "eve", "faith", "fanny", "faye", "fern", "flora", "frank", "gale", "gay", "gene", "ginger", "glen", "gore", "grace", "grant", "guy", "hale", "harmony", "harry", "hazel", "heath", "heather", "heaven", "henry", "holly", "hope", "hunter", "iris", "ivy", "ivy", "jack", "jade", "jean", "jenny", "jerry", "jersey", "jewel", "jimmy", "john", "josh", "joy", "june", "kitty", "lacy", "lance", "laurel", "lee", "lily", "lily", "marina", "mark", "mark", "marsh", "mason", "matt", "max", "maxim", "may", "may", "mcdonald", "melody", "mike", "miles", "milo", "misty", "nick", "norm", "olive", "opal", "oral", "pam", "pansy", "pat", "patience", "patsy", "patty", "pearl", "peg", "penny", "pepper", "peter", "petunia", "pierce", "poppy", "queen", "ralph", "randy", "ransom", "ray", "red", "reed", "rich", "rick", "river", "rob", "rock", "roger", "rose", "rowan", "ruth", "sally", "sandy", "scot", "shad", "shepherd", "skip", "sky", "sly", "stone", "sue", "summer", "summer", "tab", "tad", "tanner", "tara", "tiffany", "tom", "tony", "tucker", "violet", "wade", "ward", "warren", "will", "winter", "wren"])

word_places = set(["regional", "website"])

html_attrs = set(["id", "class", "style", "lang", "xml:lang", "coords", "shape"])

class ParseCA:
	def __init__(self):
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [
			("User-Agent", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"),
			("Accept", "text/pain"),
			("Accept-Language", "en-US,en;q=0.5"),
			("Accept-Encoding", "gzip, deflate, br")
		]

		self.names = {}
		self.phones = {}
		self.emails = {}
		self.links = {}
		self.office = {}
		self.street = {}
		self.apt = {}
		self.city = {}
		self.fax = {}
		self.eng = enchant.Dict("en_US")
		self.eng.add("signup")
		self.eng.add("iframe")
		self.eng.add("analytics")
		
		self.phone_codes = [("ABC", 2), ("DEF", 3), ("GHI", 4), ("JKL", 5), ("MNO", 6), ("PQRS", 7), ("TUV", 8), ("WXYZ", 9)]
		self.results = {}
		self.urls = []

	def getURL(self, url, cache):
		if not os.path.isfile(cache + ".html"):
			with open(cache + ".html", "w") as fptr:
				response = self.opener.open(url)
				data = response.read()
				try:
					decoded = gzip.GzipFile(fileobj=io.BytesIO(data)).read().decode("latin1").encode('utf8')
				except:
					decoded = data.decode("latin1").encode('utf8')
				print >>fptr, decoded
		parser = Parser()
		with open(cache + ".html", 'r') as fptr:
			data = fptr.read().decode('utf8').replace("%20", "").replace(u"\xe2\x80\x9c", u"\"").replace(u"\xe2\x80\x9d", u"\"")
			parser.feed(data)
		return parser

	def extractLinks(self, elem, addr):
		if '@' not in elem:
			objs = re.finditer(r'(?:(?:[a-z]+://)?[-A-Za-z0-9_]+(?:\.[-A-Za-z0-9_]+)+)?(?:/[-A-Za-z0-9 _]+)*(?:\.(?:html|py|php|jpg|jpeg|png|gif|txt|md)|/)?(?:#[-A-Za-z0-9_]+)?(?:\?(?:[-A-Za-z0-9_]+=[-A-Za-z0-9_ \"\']*)+)?', elem)
			rng = []
			start = 0
			for obj in objs:
				link = obj.group(0).lower()
				if link:
					if link in self.links:
						self.links[link].append(addr)
					else:
						self.links[link] = [addr]
				rng.append((start, obj.start(0)))
				start = obj.end(0)
			return ''.join([elem[s:e] for s, e in rng] + [elem[start:]])
		else:
			return elem

	def extractEmails(self, elem, addr):
		objs = re.finditer(r'[A-Za-z.0-9]+@[A-Za-z]+.[A-Za-z]+', elem)
		rng = []
		start = 0
		for obj in objs:
			email = obj.group(0).lower()
			sp = email.split("@")
			sp[0] = sp[0].replace('.', '')
			email = '@'.join(sp)
			if email in self.emails:
				self.emails[email].append(addr)
			else:
				self.emails[email] = [addr]
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return ''.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractPhones(self, elem, addr):
		objs = re.finditer(r'\(?[0-9][0-9][0-9]\)?[ -.][0-9][0-9][0-9][ -.][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z]', elem)
		rng = []
		start = 0
		for obj in objs:
			phone = obj.group(0).replace("(", "").replace(")", "").replace(" ", "-").replace(".", "-")
			for key, value in self.phone_codes:
				for char in key:
					phone = phone.replace(unicode(char), unicode(value))

			if "fax" in elem.lower():
				if phone in self.fax:
					self.fax[phone].append(addr)
				else:
					self.fax[phone] = [addr]
			else:
				if phone in self.phones:
					self.phones[phone].append(addr)
				else:
					self.phones[phone] = [addr]
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return ''.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractNames(self, elem, addr):
		objs = re.findall(ur'(?:[A-Z\u00C0-\u00D6\u00D8-\u00DE][a-z\u00DF-\u00f6\u00f8-\u00ff]+(?:-\s*[A-Z\u00C0-\u00D6\u00D8-\u00DE][a-z\u00DF-\u00f6\u00f8-\u00ff]+)*,\s*)?(?:[A-Z\u00C0-\u00D6\u00D8-\u00DE][a-z\u00DF-\u00f6\u00f8-\u00ff]+|[A-Z\u00C0-\u00D6\u00D8-\u00DE][A-Z\u00C0-\u00D6\u00D8-\u00DE])(?:\s[A-Z\u00C0-\u00D6\u00D8-\u00DE][a-z\u00DF-\u00f6\u00f8-\u00ff]+(?:-\s*[A-Z\u00C0-\u00D6\u00D8-\u00DE][a-z\u00DF-\u00f6\u00f8-\u00ff]+)*|\s[A-Z\u00C0-\u00D6\u00D8-\u00DE][a-z\u00DF-\u00f6\u00f8-\u00ff]*\.)*', elem)
		for obj in objs:
			obj = obj.replace("- ", "-")
			if "," in obj:
				obj = obj.split(",")
				obj = " ".join([word.strip() for word in reversed(obj)])
				obj = obj.replace("  ", " ")

			words = obj.split(" ")
			isName = False
			if len(words) > 1:
				for word in words:
					word = word.lower()
					if word in word_names or not self.eng.check(word):
						isName = True
					if word in word_places:
						isName = False
						break

			if isName:
				if obj in self.names:
					self.names[obj].append(addr)
				else:
					self.names[obj] = [addr]
	
	def extractPositions(self, elem, addr):
		r_pos = r'Chair|Vice|Treasurer|Secretary|Executive|Director|Administrator|Fellow|Congressman|Congresswoman|Auditor|Leader|Senator|Representative|Member|Governer|Secretary|Controller|General|Attorney|Commissioner|Superindendent'

	def extractLocations(self, elem, addr):
		r_loc = r'Office'

	def extractOrganizations(self, elem, addr):
		r_org = r'Democrats|Dems|Republicans|Repubs|Reps|Party|Board'

	def extractCity(self, elem, addr):
		r_zip = r'\b[0-9]{5}(?:-[0-9]{4})?\b'
		r_city = r'(?:[A-Z][a-z.-]+ ?)+'
		r_state = r'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'
		r_stateabbr = r'AL|AK|AS|AZ|AR|CA|CO|CT|DE|D\.?C\.?|FM|FL|GA|GU|HI|ID|IL|IN|IA|KS|KY|LA|ME|MH|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|MP|OH|OK|OR|PW|PA|PR|RI|SC|SD|TN|TX|UT|VT|VI|VA|WA|WV|WI|WY'
		
		r_citystatezip = r_city + r',? (?:' + r_state + r'|' + r_stateabbr + r')(?: ' + r_zip + r')?'

		objs = re.finditer(r_citystatezip, elem)
		rng = []
		start = 0
		for obj in objs:
			city = obj.group(0)
			if city in self.city:
				self.city[city].append(addr)
			else:
				self.city[city] = [addr]
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return ''.join([elem[s:e] for s, e in rng] + [elem[start:]])
	
	def extractStreet(self, elem, addr):
		r_street = r'(?:[0-9]+[A-Za-z]*|[A-Z][a-z]*) (?:[A-Z0-9][a-z0-9]*(?:-[A-Z0-9][a-z0-9]*)?\.? )+(?=Avenue|Lane|Road|Boulevard|Drive|Street|Mall|Plaza|Ave|Dr|Rd|Blvd|Ln|St)(?:Avenue|Lane|Road|Boulevard|Drive|Street|Mall|Plaza|Ave|Dr|Rd|Blvd|Ln|St)\.?'
		r_po = r'P\.?O\.? Box [0-9]+'
		r_streetbox = r'(?:' + r_po + '|' + r_street + ')'
	
		objs = re.finditer(r_streetbox, elem)
		rng = []
		start = 0
		for obj in objs:
			street = obj.group(0)
			if street in self.street:
				self.street[street].append(addr)
			else:
				self.street[street] = [addr]
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return ''.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractApt(self, elem, addr):
		r_apt = r'(?:[A-Z0-9][a-z0-9]*(?:-[A-Z0-9][a-z0-9]*)?\.?,? )*(?=Apartment|Building|Floor|Suite|Unit|Room|Department|Apt|Bldg|Fl|Ste|Rm|Dept)(?:Apartment|Building|Floor|Suite|Unit|Room|Department|Mall|Apt|Bldg|Fl|Ste|Rm|Dept)s?\.?'
		r_aptnum = r'(:?[0-9]+[A-Za-z]* ' + r_apt + r'|' + r_apt + r' [0-9]+[A-Za-z]*(?:(?: *[-,&] *| +)[0-9]+[A-Za-z]*)+)'
		
		objs = re.finditer(r_aptnum, elem)
		rng = []
		start = 0
		for obj in objs:
			apt = obj.group(0)
			if apt in self.apt:
				self.apt[apt].append(addr)
			else:
				self.apt[apt] = [addr]
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return ''.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractAttr(self, key, value, addr):
		if value:
			value = value.strip()
			if value and key not in html_attrs:
				value = self.extractPhones(value, addr)
				value = self.extractEmails(value, addr)
				if key in ["href", "src"]:
					value = self.extractLinks(value, addr)
				value = self.extractCity(value, addr)
				value = self.extractStreet(value, addr)
				value = self.extractApt(value, addr)
				self.extractNames(value, addr)

	def extractStr(self, elem, addr):
		elem = elem.strip().replace(u'\xa0', u' ')
		if elem:
			elem = self.extractPhones(elem, addr)
			elem = self.extractEmails(elem, addr)
			elem = self.extractCity(elem, addr)
			elem = self.extractStreet(elem, addr)
			elem = self.extractApt(elem, addr)
			self.extractNames(elem, addr)

	def traverse(self, elem, addr=[]):
		if isinstance(elem, Tag) and elem.name not in html_attrs:
			for key, value in elem.attrs.items():
				self.extractAttr(key, value, addr)

			stored = u''
			for i, item in enumerate(elem.content):
				if isinstance(item, unicode):
					stored += item
				else:
					self.extractStr(stored, addr)
					stored = u''
					self.traverse(item, addr + [i])
			self.extractStr(stored, addr)
			stored = u''
		elif isinstance(elem, STag):
			for key, value in elem.attrs.items():
				self.extractAttr(key, value, addr)
		elif isinstance(elem, unicode):
			self.extractStr(stored, addr)

	def findBest(self, best, addr, data):
		for _, tests in data.items():
			for test in tests:
				d = depth(addr, test)
				if d > len(best):
					best = addr[0:d]
		return best

	def buildEntry(self, entry, addr, start, end, data, key, clear=True):
		for item, tests in data.items():
			found = False
			for test in tests:
				if test[0:len(addr)] == addr and len(test) > len(addr) and (start is None or test[len(addr)] >= start) and (end is None or test[len(addr)] < end):
					found = True
					break

			if found:
				if key in entry:
					entry[key].add(item)
				else:
					entry[key] = set([item])
				if clear:
					del data[item]
		return entry

	def develop(self):
		for name, addrs in self.names.items():
			entry = {
			}
			
			for addr in addrs:
				maxdepth = 0
				start = None
				end = None
				for name1, tests in self.names.items():
					if name != name1:
						for test in tests:
							d = depth(addr, test)
							if d > maxdepth:
								maxdepth = d
								start = None
								end = None
							if d >= maxdepth:
								if test[maxdepth] < addr[maxdepth]:
									if start is None or test[maxdepth]+1 > start:
										start = test[maxdepth]+1
								elif test[maxdepth] > addr[maxdepth]:
									if end is None or test[maxdepth] < end:
										end = test[maxdepth]
				base = addr[0:maxdepth]
				if start is None or end is None:
					best = []
					best = self.findBest(best, addr, self.emails)
					best = self.findBest(best, addr, self.phones)
					best = self.findBest(best, addr, self.links)
					best = self.findBest(best, addr, self.fax)
					if len(best) > len(base):
						base = best
						start = None
						end = None

				entry = self.buildEntry(entry, base, start, end, self.emails, 'email')
				entry = self.buildEntry(entry, base, start, end, self.phones, 'phone')
				entry = self.buildEntry(entry, base, start, end, self.links, 'link')
				entry = self.buildEntry(entry, base, start, end, self.fax, 'fax')
				entry = self.buildEntry(entry, base, start, end, self.city, 'city', False)
				entry = self.buildEntry(entry, base, start, end, self.street, 'street', False)
				entry = self.buildEntry(entry, base, start, end, self.apt, 'apt', False)

			if name in self.results:
				old = self.results[name]
				if 'email' in old and 'email' in entry:
					entry['email'] |= set(old['email'])
				elif 'email' in old:
					entry['email'] = set(old['email'])				

				if 'phone' in old and 'phone' in entry:
					entry['phone'] |= set(old['phone'])
				elif 'phone' in old:
					entry['phone'] = set(old['phone'])

				if 'fax' in old and 'fax' in entry:
					entry['fax'] |= set(old['fax'])
				elif 'fax' in old:
					entry['fax'] = set(old['fax'])

				if 'link' in old and 'link' in entry:
					entry['link'] |= set(old['link'])
				elif 'link' in old:
					entry['link'] = set(old['link'])

				if 'city' in old and 'city' in entry:
					entry['city'] |= set(old['city'])
				elif 'city' in old:
					entry['city'] = set(old['city'])

				if 'street' in old and 'street' in entry:
					entry['street'] |= set(old['street'])
				elif 'street' in old:
					entry['street'] = set(old['street'])

				if 'apt' in old and 'apt' in entry:
					entry['apt'] |= set(old['apt'])
				elif 'apt' in old:
					entry['apt'] = set(old['apt'])


			if 'email' in entry:			
				entry['email'] = list(entry['email'])
			if 'phone' in entry:
				entry['phone'] = list(entry['phone'])
			if 'fax' in entry:
				entry['fax'] = list(entry['fax'])
			if 'link' in entry:
				entry['link'] = list(entry['link'])
			if 'city' in entry:
				entry['city'] = list(entry['city'])
			if 'street' in entry:
				entry['street'] = list(entry['street'])
			if 'apt' in entry:
				entry['apt'] = list(entry['apt'])

			self.results[name] = entry
		print 'emails: ' + repr(self.emails)
		print 'phones: ' + repr(self.phones)
		print 'links: ' + repr(self.links)
		print 'fax: ' + repr(self.fax)
		self.emails = {}
		self.phones = {}
		self.links = {}
		self.names = {}
		self.office = {}
		self.city = {}
		self.street = {}
		self.apt = {}

	def scrape(self, url):
		uid = str(len(self.urls))
		self.traverse(self.getURL(url, uid).syntax)
		self.urls.append(url)
		self.develop()

parser = ParseCA()

#parser.scrape("http://www.cadem.org/our-party/leaders")
#parser.scrape("http://www.cadem.org/our-party/elected-officials")
#parser.scrape("http://www.cadem.org/our-party/our-county-committees")
#parser.scrape("http://www.cadem.org/our-party/dnc-members")
#parser.scrape("https://nydems.org/our-party/")
#parser.scrape("https://missouridemocrats.org/county-parties/")
parser.scrape("https://missouridemocrats.org/officers-and-staff/")



print json.dumps(parser.results, indent=2)
#print json.dumps(parser.emails.keys(), indent=2)
#print json.dumps(parser.phones.keys(), indent=2)
#print json.dumps(parser.names.keys(), indent=2)
#print json.dumps(parser.links.keys(), indent=2)

# separate out names
# get bound from names
# fall back to findBest
# change findBest to prioritise distance
# develop
# check name mergers


#print json.dumps(results, indent=2)

