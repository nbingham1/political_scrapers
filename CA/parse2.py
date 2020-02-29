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
from bs4 import UnicodeDammit

from pyhtml.html import *
from pyhtml.parse import *

class SetEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, set):
			return list(obj)
		return json.JSONEncoder.default(self, obj)

def depth(addr1, addr2):
	for i, (a, b) in enumerate(zip(addr1, addr2)):
		if a != b:
			return i
	return min(len(addr1), len(addr2))

name_incl = set(["rusty", "hicks", "abbey", "albert", "allie", "amber", "andrew", "angel", "april", "art", "august", "aurora", "autumn", "baldric", "barb", "bay", "bill", "bob", "booth", "brad", "brandy", "brook", "buck", "candy", "carol", "carole", "cat", "chad", "charity", "chase", "chip", "christian", "chuck", "clay", "cliff", "colt", "cricket", "crystal", "daisy", "dale", "dale", "dash", "dawn", "dean", "derrick", "destiny", "dick", "dixie", "dolly", "don", "dori", "dory", "dot", "earl", "ebony", "elle", "eve", "faith", "fanny", "faye", "fern", "flora", "frank", "gale", "gay", "gene", "ginger", "glen", "gore", "grace", "grant", "guy", "hale", "harmony", "harry", "hazel", "heath", "heather", "heaven", "henry", "holly", "hope", "hunter", "iris", "ivy", "ivy", "jack", "jade", "jean", "jenny", "jerry", "jersey", "jewel", "jimmy", "john", "josh", "joy", "june", "kitty", "lacy", "lance", "laurel", "lee", "lily", "lily", "marina", "mark", "mark", "marsh", "mason", "matt", "max", "maxim", "may", "may", "mcdonald", "melody", "mike", "miles", "milo", "misty", "nick", "norm", "olive", "opal", "oral", "pam", "pansy", "pat", "patience", "patsy", "patty", "pearl", "peg", "penny", "pepper", "peter", "petunia", "pierce", "poppy", "queen", "ralph", "randy", "ransom", "ray", "red", "reed", "rich", "rick", "river", "rob", "rock", "roger", "rose", "rowan", "ruth", "sally", "sandy", "scot", "shad", "shepherd", "skip", "sky", "sly", "stone", "sue", "summer", "summer", "tab", "tad", "tanner", "tara", "tiffany", "tom", "tony", "tucker", "violet", "wade", "ward", "warren", "will", "winter", "wren", "smith", "king", "jr", "robin", "standard", "hall", "curry", "sawyer", "porter", "elder", "service", "early", "shay", "waters", "jay", "peoples", "stokes", "hogan", "los", "iv", "iii", "law", "terry", "rosemary", "coco", "miller", "self", "bates", "young", "gray", "cooper", "ken", "hill", "caballero", "pan", "wiener", "peters", "bass", "ted", "lieu", "cox", "harder", "ma", "wicks", "quirk", "ash", "low", "ed", "bloom", "nelson", "butler", "rice", "bacon", "baker", "bays", "bishop", "brown", "bush", "carter", "crane", "timothy", "dormer", "duke", "fall", "ford", "forte", "freer", "garland", "green", "grove", "hanks", "hart", "hickey", "hood", "margarita", "kirsch", "knight", "long", "maria", "mealy", "miner", "warden", "mills", "sherry", "provost", "molly", "ridge", "rigger", "hector", "romeo", "sharp", "shuffler", "sierra", "silver", "sold", "st", "stage", "stark", "street", "tong", "van", "vita", "weaver", "woods", "bears", "dove", "hunt", "ting", "horseman", "black", "nice", "dickey", "hooker", "repay", "hook", "condo", "cousins"])

name_excl = set(["regional", "website", "office", "camp", "employment", "ceo", "tlc", "tempore", "mr", "ms", "dnc", "latino", "february", "african"])

html_attrs = set(["id", "class", "style", "lang", "xml:lang", "coords", "shape", "href", "src", "width", "height", "rel"])
html_tags = set(["svg", "path", "style", "script", "link", "form", "input"])

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
		self.fax = {}

		self.orgs = []
		self.titles = []
		self.street = []
		self.apt = []
		self.city = []

		self.offices = []

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
					decoded = UnicodeDammit(gzip.GzipFile(fileobj=io.BytesIO(data)).read(), ["windows-1252"], smart_quotes_to="html").unicode_markup
				except:
					decoded = UnicodeDammit(data, ["windows-1252"], smart_quotes_to="html").unicode_markup
				decoded = decoded.replace(u"%20", u" ").replace(u"&nbsp;", u" ").replace(u"\xe2&euro;&trade;", u"\'").replace(u"\xe2&euro;&oelig;", u"\"").replace(u"\xe2&euro;", "\"").replace(u"\"&ldquo;", "-")
				#.replace(u"\xe2\x80\x9c", u"\"").replace(u"\xe2\x80\x9d", u"\"").replace(u"\xc3\xb3", u"\u00f3").replace(u"\xc3\xad", u"\u00ed").replace(u"\xe2\x20\xac\x21\x22", u"\'").replace(u"\xe2\x20\xac\x01\x53", u"\"").replace(u"\xe2\x20\xac", u"\"").replace(u"\xe2\x20\xac\x20\x1c", u" - ").replace(u"\xc3", u"\u00e9").replace(u"\x00\xc2", u" ")
				print >>fptr, decoded.encode('utf8')
		parser = Parser()
		with open(cache + ".html", 'r') as fptr:
			data = fptr.read().decode('utf8')
			parser.feed(data)
		return parser

	def extractLinks(self, elem, addr):
		if 'mailto:' not in elem:
			r_domain = r'(?:[a-z]+://)?[-A-Za-z0-9_]+(?:\.[-A-Za-z0-9_]+)+'
			r_path = r'(?:/[-A-Za-z0-9 _]+)+(?:\.(?:html|py|php|jpg|jpeg|png|gif|txt|md)|/)?'
			r_anchor = r'#[-A-Za-z0-9_]+'
			r_get = r'\?[-A-Za-z0-9_]+=[-A-Za-z0-9_ \"\']*(?:\&[-A-Za-z0-9_]+=[-A-Za-z0-9_ \"\']*)*'
			r_second = r_path + r'(?:' + r_anchor + ')?' + r'(?:' + r_get + r')?'
			r_link = r'(?:' + r_domain + r_second + r'|' + r_path + r'|' + r_domain + '/?)'
			objs = re.finditer(r_link, elem)
			rng = []
			start = 0
			for obj in objs:
				link = obj.group(0).lower()
				if not link:
					print "Error: link matches empty string"
				if "wp-content" not in link and "wp-json" not in link and "googleapis.com" not in link and "wp-includes" not in link and "googletagmanager.com" not in link and "addthis.com" not in link:
					if link in self.links:
						self.links[link].append(addr)
					else:
						self.links[link] = [addr]
					rng.append((start, obj.start(0)))
					start = obj.end(0)
			return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])
		else:
			return elem

	def extractEmails(self, elem, addr):
		objs = re.finditer(r'[-_A-Za-z\.0-9]+@[-_A-Za-z0-9\.]+', elem)
		rng = []
		start = 0
		for obj in objs:
			email = obj.group(0).lower()
			if not email:
				print "Error: email matches empty string"
			sp = email.split("@")
			sp[0] = sp[0].replace('.', '')
			email = '@'.join(sp)
			if email in self.emails:
				self.emails[email].append(addr)
			else:
				self.emails[email] = [addr]
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractPhones(self, elem, addr):
		objs = re.finditer(r'\(?[0-9][0-9][0-9]\)? *[-.]? *[0-9][0-9][0-9] *[-.]? *[0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z]', elem)
		rng = []
		start = 0
		for obj in objs:
			phone = obj.group(0).replace("(", "").replace(")", "").replace("-", "").replace(".", "").replace(" ", "")
			if not phone:
				print "Error: phone matches empty string"
			phone = phone[0:3] + '-' + phone[3:6] + '-' + phone[6:]
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
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractNames(self, elem, addr):
		r_name = ur'[A-Z\u00C0-\u00D6\u00D8-\u00DE][A-Z\u00C0-\u00D6\u00D8-\u00DEa-z\u00DF-\u00f6\u00f8-\u00ff\']*\.?'
		
		objs = re.finditer(r_name, elem, flags=re.UNICODE)
		rng = []
		start = 0
		nameStart = None
		nameEnd = 0
		nextStart = None
		nextEnd = 0

		words = []
		inDict = []
		parsedNames = []

		name = u""
		last = u""
		count = 0
		
		nextName = u""
		nextCount = 0
		for obj in objs:
			word = obj.group(0)
			words.append(word)
			if not word:
				print "Error: name matches empty string"
			#if "," in name:
			#	name = name.split(",")
			#	name = " ".join([word.strip() for word in reversed(name)])
			#	name = name.replace("  ", " ")

			lword = word.lower()
			if lword[-1] == '.':
				lword = lword[0:-1]
			end = False
			if lword not in name_excl and (len(lword) == 1 or lword in name_incl or not self.eng.check(lword)):
				sep = elem[nameEnd:obj.start(0)]
				if count == 0:
					name += word
					count += 1
					nameStart = obj.start(0)
				elif name and name[-1] != '.' and re.match(ur'^ *- *$', sep):
					name += '-' + word
				elif re.match(ur'^ *, *$', sep):
					if count == 1:
						last = name
						name = word
						count += 1
					elif word[-1] == '.' or re.match(ur'^[IVXM]+$', word):
						if last:
							name += " " + last
							last = ""
						name += " " + word
						count += 1
					else:
						end = True
				elif re.match(ur'^ +$', sep):
					name += " " + word
					count += 1
				else:
					nextStart = obj.start(0)
					nextEnd = obj.end(0)
					nextName = word
					nextCount = 1
					end = True
			else:
				inDict.append(lword)
				end = True
				if lword not in name_excl and lword not in name_incl:
					print "maybe add " + str(elem[obj.start(0)-10 if obj.start(0) >= 10 else 0:obj.start(0)].encode("utf8")) + "[" + str(word.encode("utf8")) + "]" + str(elem[obj.end(0):obj.end(0)+10 if obj.end(0)+10 < len(elem) else len(elem)].encode("utf8"))

			if end:
				if count >= 2:
					if last:
						name += " " + last
					parsedNames.append(name)
					if name in self.names:
						self.names[name].append(addr)
					else:
						self.names[name] = [addr]

					rng.append((start, nameStart))
					start = nameEnd

				name = nextName
				last = u""
				count = nextCount
				nameStart = nextStart
				nameEnd = nextEnd
				nextName = u""
				nextCount = 0
				nextStart = None
				nextEnd = 0
			
			if nameStart is not None:
				nameEnd = obj.end(0)

		if count >= 2:
			if last:
				name += " " + last
			parsedNames.append(name)
			if name in self.names:
				self.names[name].append(addr)
			else:
				self.names[name] = [addr]
			
			rng.append((start, nameStart))
			start = nameEnd

		result = '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])
		#if "{}" not in result:
		#	print "input: " + repr(elem)
		#	print "words: " + repr(words)
		#	print "indict: " + repr(inDict)
		#	print "parsed: " + repr(result)
		#	print "names: " + repr(parsedNames)
		#	print ""
		return result

	def extractTitles(self, elem, addr):
		r_pos = ur'Chair|Vice|Treasurer|Secretary|Director|Administrator|Fellow|Congressman|Congresswoman|Auditor|Leader|Senator|Representative|Member|Governer|Secretary|Controller|General|Attorney|Commissioner|Superindendent|Officer|President|Governor|Staff|Assemblymember|Rep\.|Sen\.|Speaker|Comptroller|Rev\.|Reverend|Mayor'

		r_title = ur'(?:(?:[A-Z][a-z]+|[0-9]+[A-Za-z]*|[A-Z]+)(?: +| *- *))*(?=' + r_pos + ur')(?:' + r_pos + ur')(?: (?:of|for|in)(?:(?: +| *- *)(?:[A-Z][a-z]+|[0-9]+[A-Za-z]*|[A-Z]+))+)?'
		objs = re.finditer(r_title, elem, flags=re.UNICODE)

		rng = []
		start = 0
		for i, obj in enumerate(objs):
			title = obj.group(0)
			if not title:
				print "Error: title matches empty string"
			if i > 0 and obj.start(0) - start <= 1:
				self.titles[-1] = (elem[rng[-1][1]:obj.end(0)], addr)
			else:
				self.titles.append((title, addr))
				rng.append((start, obj.start(0)))
			start = obj.end(0)
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractOrgs(self, elem, addr):
		r_org = r'Democrats|Dems|Republicans|Repubs|Reps|Party|Board|County|State|City|Committee|Council'

		r_orgtitle = r'(?:(?:[A-Z][a-z]+|[0-9]+[a-z]*)[ -]+)*(?=' + r_org + ')(?:' + r_org + ')'
		objs = re.finditer(r_orgtitle, elem)

		rng = []
		start = 0
		for i, obj in enumerate(objs):
			org = obj.group(0)
			if not org:
				print "Error: org matches empty string"
			if i > 0 and obj.start(0) - start <= 1:
				self.orgs[-1] = (elem[rng[-1][1]:obj.end(0)], addr)
			else:
				self.orgs.append((org, addr))
				rng.append((start, obj.start(0)))
			start = obj.end(0)
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractCity(self, elem, addr):
		r_zip = r'[0-9]{5}(?:-[0-9]{4})?'
		r_city = r'(?:[A-Z][a-z.-]+ ?)+'
		r_state = r'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'
		r_stateabbr = r'AL\.?|AK\.?|AS\.?|AZ\.?|AR\.?|CA\.?|CO\.?|CT\.?|DE\.?|D\.?C\.?|FM\.?|FL\.?|GA\.?|GU\.?|HI\.?|ID\.?|IL\.?|IN\.?|IA\.?|KS\.?|KY\.?|LA\.?|ME\.?|MH\.?|MD\.?|MA\.?|MI\.?|MN\.?|MS\.?|MO\.?|MT\.?|NE\.?|NV\.?|NH\.?|NJ\.?|NM\.?|NY\.?|NC\.?|ND\.?|MP\.?|OH\.?|OK\.?|OR\.?|PW\.?|PA\.?|PR\.?|RI\.?|SC\.?|SD\.?|TN\.?|TX\.?|UT\.?|VT\.?|VI\.?|VA\.?|WA\.?|WV\.?|WI\.?|WY\.?'
		
		r_citystatezip = r_city + r', +(?:' + r_state + r'|' + r_stateabbr + r')(?:(?:, *| +)' + r_zip + r')?'

		objs = re.finditer(r_citystatezip, elem)
		rng = []
		start = 0
		for obj in objs:
			city = obj.group(0).replace("  ", " ")
			if not city:
				print "Error: city matches empty string"
			self.city.append((city, addr))
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])
	
	def extractStreet(self, elem, addr):
		r_street = r'(?:[0-9]+[A-Za-z]*|[A-Z][a-z]*) (?:[A-Z0-9][A-Za-z0-9]*(?:-[A-Z0-9][a-z0-9]*)?\.? )+(?=Avenue|Lane|Road|Boulevard|Drive|Street|Mall|Plaza|Ave|Dr|Rd|Blvd|Ln|St|Hwy|Highway|Park|Route|Rt|Court|Ct|SR)(?:Avenue|Lane|Road|Boulevard|Drive|Street|Mall|Plaza|Ave|Dr|Rd|Blvd|Ln|St|Hwy\.? *[0-9]+|Highway *[0-9]+|Park|Route *[0-9]+|Rt\.? *[0-9]+|Court|Ct|SR\.? *[0-9]+)\.?'
		r_po = r'P\.?O\.? Box [0-9]+'
		r_streetbox = r'(?:' + r_po + '|' + r_street + ')'
	
		objs = re.finditer(r_streetbox, elem)
		rng = []
		start = 0
		for obj in objs:
			if obj.end(0) >= len(elem) or not re.match(u'^[a-zA-Z0-9]', elem[obj.end(0):]):
				street = obj.group(0)
				if not street:
					print "Error: street matches empty string"
				self.street.append((street, addr))
				rng.append((start, obj.start(0)))
				start = obj.end(0)
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractApt(self, elem, addr):
		r_apt = r'(?:[A-Z0-9][a-z0-9]*(?:-[A-Z0-9][a-z0-9]*)?\.?,? )*(?=Apartment|Building|Floor|Suite|Unit|Room|Department|Apt|Bldg|Fl|Ste|Rm|Dept)(?:Apartment|Building|Floor|Suite|Unit|Room|Department|Mall|Apt|Bldg|Fl|Ste|Rm|Dept)s?\.?'
		r_aptnum = r'(:?[0-9]+[A-Za-z]* +' + r_apt + r'|' + r_apt + r' +[0-9]+[A-Za-z]*(?:(?: *[-,&] *| +)[0-9]+[A-Za-z]*)*)'
		
		objs = re.finditer(r_aptnum, elem)
		rng = []
		start = 0
		for obj in objs:
			apt = obj.group(0)
			if not apt:
				print "Error: apt matches empty string"
			self.apt.append((apt, addr))
			rng.append((start, obj.start(0)))
			start = obj.end(0)
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractAttr(self, tag, key, value, addr):
		if value:
			value = value.strip()
			if value:
				if key not in html_attrs:
					value = self.extractPhones(value, addr)
					value = self.extractEmails(value, addr)
					value = self.extractStreet(value, addr)
					value = self.extractApt(value, addr)
					value = self.extractCity(value, addr)
					value = self.extractTitles(value, addr)
					#value = self.extractOrgs(value, addr)
					value = self.extractNames(value, addr)
					#if value.replace("{}", "").replace(" ", ""):
					#	print (key, value)
				elif key in ["href", "src"]:
					value = self.extractLinks(value, addr)

	def extractStr(self, tag, elem, addr):
		elem = elem.strip().replace(u'\xa0', u' ').replace(u'\xa9', u'')
		if elem:
			elem = self.extractPhones(elem, addr)
			elem = self.extractEmails(elem, addr)
			elem = self.extractStreet(elem, addr)
			elem = self.extractApt(elem, addr)
			elem = self.extractCity(elem, addr)
			elem = self.extractTitles(elem, addr)

			#elem = self.extractOrgs(elem, addr)
			elem = self.extractNames(elem, addr)
			#if elem.replace("{}", "").replace(" ", ""):
			#	print repr(elem)


	def traverse(self, elem, addr=[]):
		if isinstance(elem, Tag) and elem.name not in html_tags:
			for key, value in elem.attrs.items():
				self.extractAttr(elem.name, key, value, addr)

			stored = u''
			for i, item in enumerate(elem.content):
				if isinstance(item, unicode):
					stored += item
				else:
					self.extractStr(elem.name, stored, addr)
					stored = u''
					self.traverse(item, addr + [i])
			self.extractStr(elem.name, stored, addr)
			stored = u''
		elif isinstance(elem, STag) and elem.name not in html_tags:
			for key, value in elem.attrs.items():
				self.extractAttr(elem.name, key, value, addr)
		elif isinstance(elem, unicode):
			self.extractStr("", stored, addr)

	def findRoot(self, root, addr, data):
		if isinstance(data, dict):
			for _, tests in data.items():
				for test in tests:
					d = depth(addr, test)
					if d > len(root):
						root = addr[0:d]
		elif isinstance(data, list):
			for _, test in data:
				d = depth(addr, test)
				if d > len(root):
					root = addr[0:d]
		return root

	def buildEntry(self, entry, addr, start, end, data, key, clear=True):
		if isinstance(data, dict):
			for item, tests in data.items():
				found = []
				for i, test in enumerate(tests):
					if test[0:len(addr)] == addr and (len(test) == len(addr) or (len(test) > len(addr) and (start is None or test[len(addr)] >= start) and (end is None or test[len(addr)] < end))):
						found.append(i)

				if found:
					if isinstance(item, dict):
						if key in entry:
							entry[key].append(item)
						else:
							entry[key] = [item]
					else:
						if key in entry:
							entry[key].add(item)
						else:
							entry[key] = set([item])
					if clear:
						for idx in reversed(found):
							del data[item][idx]
						if not data[item]:
							del data[item]
		elif isinstance(data, list):
			for i, (item, test) in enumerate(data):
				if test[0:len(addr)] == addr and (len(test) == len(addr) or (len(test) > len(addr) and (start is None or test[len(addr)] >= start) and (end is None or test[len(addr)] < end))):
					if isinstance(item, dict):
						if key in entry:
							entry[key].append(item)
						else:
							entry[key] = [item]
					else:
						if key in entry:
							entry[key].add(item)
						else:
							entry[key] = set([item])
					if clear:
						del data[i]
		return entry

	def develop(self):
		# tie addresses together
		cities = [addr for city, addr in self.city]
		for addr in cities:
			root = []
			root = self.findRoot(root, addr, self.street)
			root = self.findRoot(root, addr, self.apt)
			root = self.findRoot(root, addr, self.phones)
			root = self.findRoot(root, addr, self.fax)
			found = False
			for addrs in self.names.values():
				for test in addrs:
					if len(test) > len(root) and test[0:len(root)] == root:
						found = True
						break
				if found:
					break

			if not found:
				entry = {}			
				entry = self.buildEntry(entry, root, None, None, self.city, 'city')
				entry = self.buildEntry(entry, root, None, None, self.street, 'street')
				entry = self.buildEntry(entry, root, None, None, self.apt, 'apt')
				entry = self.buildEntry(entry, root, None, None, self.phones, 'phone')
				entry = self.buildEntry(entry, root, None, None, self.fax, 'fax')
				self.offices.append((entry, root))

		for name, addrs in self.names.items():
			entry = {}
			if name in self.results:
				entry = self.results[name]
			
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
							if d == maxdepth and maxdepth < len(test):
								if maxdepth >= len(addr) or test[maxdepth] < addr[maxdepth]:
									if start is None or test[maxdepth]+1 > start:
										start = test[maxdepth]+1
								if maxdepth >= len(addr) or test[maxdepth] > addr[maxdepth]:
									if end is None or test[maxdepth] < end:
										end = test[maxdepth]
				#start = addr[maxdepth] if maxdepth < len(addr) else addr
				base = addr[0:maxdepth]
				if start is None or end is None:
					root = []
					root = self.findRoot(root, addr, self.emails)
					root = self.findRoot(root, addr, self.phones)
					root = self.findRoot(root, addr, self.links)
					root = self.findRoot(root, addr, self.fax)
					if len(root) > len(base):
						base = root
						start = None
						end = None

				entry = self.buildEntry(entry, base, start, end, self.emails, 'email')
				entry = self.buildEntry(entry, base, start, end, self.phones, 'phone')
				entry = self.buildEntry(entry, base, start, end, self.links, 'link')
				entry = self.buildEntry(entry, base, start, end, self.fax, 'fax')
				entry = self.buildEntry(entry, base, start, end, self.city, 'city')
				entry = self.buildEntry(entry, base, start, end, self.street, 'street')
				entry = self.buildEntry(entry, base, start, end, self.apt, 'apt')
				entry = self.buildEntry(entry, base, start, end, self.titles, 'title')
				entry = self.buildEntry(entry, base, start, end, self.offices, 'office')
				entry = self.buildEntry(entry, base, start, end, self.orgs, 'org')

			self.results[name] = entry
		#print 'emails: ' + repr(self.emails)
		#print 'phones: ' + repr(self.phones)
		#print 'links: ' + repr(self.links)
		#print 'fax: ' + repr(self.fax)
		self.emails = {}
		self.phones = {}
		self.links = {}
		self.names = {}

		#print 'titles: ' + repr(self.titles)
		#print 'city: ' + repr(self.city)
		#print 'street: ' + repr(self.street)
		#print 'apt: ' + repr(self.apt)
		#print 'org: ' + repr(self.orgs)
		self.titles = []
		self.city = []
		self.street = []
		self.apt = []
		self.orgs = []

	def scrape(self, url):
		uid = str(len(self.urls))
		self.traverse(self.getURL(url, uid).syntax)
		self.urls.append(url)
		self.develop()

parser = ParseCA()

parser.scrape("http://www.cadem.org/our-party/leaders")
parser.scrape("http://www.cadem.org/our-party/elected-officials")
parser.scrape("http://www.cadem.org/our-party/our-county-committees")
parser.scrape("http://www.cadem.org/our-party/dnc-members")
parser.scrape("https://nydems.org/our-party/")
parser.scrape("https://missouridemocrats.org/county-parties/")
parser.scrape("https://missouridemocrats.org/officers-and-staff/")
parser.scrape("https://www.indems.org/our-party/state-committee/")

print json.dumps(parser.results, indent=2, cls=SetEncoder)

