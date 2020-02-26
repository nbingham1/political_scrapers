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

word_places = set(["county", "state", "city", "regional", "street", "office", "blvd"])

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
		self.address = {}
		self.fax = {}
		self.eng = enchant.Dict("en_US")
		self.eng.add("signup")
		self.eng.add("california")
		self.eng.add("iframe")
		self.eng.add("sacramento")
		self.eng.add("analytics")
		self.eng.add("san")
		self.eng.add("diego")
		self.eng.add("francisco")
		self.eng.add("mateo")
		self.eng.add("los")
		self.eng.add("angeles")
		self.eng.add("dc")
		self.eng.add("washington")
		self.eng.add("fresno")
		self.eng.add("ca")
		
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
			objs = re.findall(r'(?:(?:[a-z]+://)?[-A-Za-z0-9_]+(?:\.[-A-Za-z0-9_]+)+)?(?:/[-A-Za-z0-9 _]+)*(?:\.(?:html|py|php|jpg|jpeg|png|gif|txt|md)|/)?(?:#[-A-Za-z0-9_]+)?(?:\?(?:[-A-Za-z0-9_]+=[-A-Za-z0-9_ \"\']*)+)?', elem)
			for obj in objs:
				if obj:
					obj = obj.lower()
					if obj in self.links:
						self.links[obj].append(addr)
					else:
						self.links[obj] = [addr]

	def extractEmails(self, elem, addr):
		objs = re.findall(r'[A-Za-z.0-9]+@[A-Za-z]+.[A-Za-z]+', elem)
		for obj in objs:
			obj = obj.lower()
			sp = obj.split("@")
			sp[0] = sp[0].replace('.', '')
			obj = '@'.join(sp)
			if obj in self.emails:
				self.emails[obj].append(addr)
			else:
				self.emails[obj] = [addr]

	def extractPhones(self, elem, addr):
		objs = re.findall(r'\(?[0-9][0-9][0-9]\)?[ -.][0-9][0-9][0-9][ -.][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z]', elem)
		for obj in objs:
			obj = obj.replace("(", "").replace(")", "").replace(" ", "-").replace(".", "-")
			for key, value in self.phone_codes:
				for char in key:
					obj = obj.replace(unicode(char), unicode(value))

			if "fax" in elem.lower():
				if obj in self.fax:
					self.fax[obj].append(addr)
				else:
					self.fax[obj] = [addr]
			else:
				if obj in self.phones:
					self.phones[obj].append(addr)
				else:
					self.phones[obj] = [addr]

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
				

	def traverse(self, elem, addr=[]):
		if isinstance(elem, Tag) and not isinstance(elem, Script):
			for key, value in elem.attrs.items():
				if value:
					value = value.strip()
					if value:
						self.extractEmails(value, addr)
						if key in ["href", "src"]:
							self.extractLinks(value, addr)
						self.extractPhones(value, addr)
						self.extractNames(value, addr)

			stored = u''
			for i, item in enumerate(elem.content):
				if isinstance(item, unicode):
					stored += item
				else:
					stored = stored.strip().replace(u'\xa0', u' ')
					if stored:
						self.extractEmails(stored, addr)
						self.extractPhones(stored, addr)
						self.extractNames(stored, addr)
						stored = u''
					self.traverse(item, addr + [i])
			stored = stored.strip().replace(u'\xa0', u' ')
			if stored:
				self.extractEmails(stored, addr)
				self.extractPhones(stored, addr)
				self.extractNames(stored, addr)
				stored = u''
		elif isinstance(elem, STag):
			for key, value in elem.attrs.items():
				if value:
					value = value.strip()
					if value:
						self.extractEmails(value, addr)
						if key in ["href", "src"]:
							self.extractLinks(value, addr)
						self.extractPhones(value, addr)
						self.extractNames(value, addr)
		elif isinstance(elem, unicode):
			elem = elem.strip()
			if elem:
				self.extractEmails(elem, addr)
				self.extractPhones(elem, addr)
				self.extractNames(elem, addr)

	def findBest(self, best, addr, data):
		for _, tests in data.items():
			for test in tests:
				d = depth(addr, test)
				if d > len(best):
					best = addr[0:d]
		return best

	def buildEntry(self, entry, addr, start, end, data, key):
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

			if name in self.results:
				print entry
				old = self.results[name]
				print old
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

			if 'email' in entry:			
				entry['email'] = list(entry['email'])
			if 'phone' in entry:
				entry['phone'] = list(entry['phone'])
			if 'fax' in entry:
				entry['fax'] = list(entry['fax'])
			if 'link' in entry:
				entry['link'] = list(entry['link'])

			self.results[name] = entry
		self.emails = {}
		self.phones = {}
		self.links = {}
		self.names = {}
		self.office = {}
		self.address = {}

	def scrape(self, url):
		uid = str(len(self.urls))
		self.traverse(self.getURL(url, uid).syntax)
		self.urls.append(url)
		self.develop()

parser = ParseCA()

parser.scrape("http://www.cadem.org/our-party/leaders")
parser.scrape("http://www.cadem.org/our-party/elected-officials")
parser.scrape("http://www.cadem.org/our-party/our-county-committees")
#parser.scrape("http://www.cadem.org/our-party/dnc-members")
#parser.scrape("https://nydems.org/our-party/")


print json.dumps(parser.results, indent=2)
#print json.dumps(parser.emails.keys(), indent=2)
#print json.dumps(parser.phones.keys(), indent=2)
#print json.dumps(parser.names.keys(), indent=2)
#print json.dumps(parser.links.keys(), indent=2)

# separate out names
# get bound from names
# fall back to findBest
# develop
# check name mergers


#print json.dumps(results, indent=2)

