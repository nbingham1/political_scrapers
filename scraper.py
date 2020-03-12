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
from lxml import etree
from difflib import SequenceMatcher

from pyhtml.html import *
from pyhtml.parse import *

# To parse google sheets:
# https://docs.google.com/spreadsheets/d/1kWoPXvugCEtxluGcHJuq4geWBAFa0HhI-V3BVelVgJ8/gviz/tq?tqx=out:csv&sheet=

def depth(addr1, addr2):
	for i, (a, b) in enumerate(zip(addr1, addr2)):
		if a != b:
			return i
	return min(len(addr1), len(addr2))

name_incl = set([])
with open("name_words.txt", "r") as fptr:
	for line in fptr:
		name_incl.add(line.strip())

preps = set([])
with open("prepositions.txt", "r") as fptr:
	for line in fptr:
		preps.add(line.strip())

title_tags = set([])
with open("titles.txt", "r") as fptr:
	for line in fptr:
		title_tags.add(line.strip())

name_excl = set(["regional", "website", "office", "camp", "employment", "ceo", "tlc", "tempore", "mr", "ms", "dnc", "latino", "february", "african", "puerto", "boe"])

html_attrs = set(["id", "class", "style", "lang", "xml:lang", "coords", "shape", "href", "src", "width", "height", "rel"])
html_tags = set(["svg", "path", "style", "script", "link", "form", "input"])

phone_codes = [("ABC", 2), ("DEF", 3), ("GHI", 4), ("JKL", 5), ("MNO", 6), ("PQRS", 7), ("TUV", 8), ("WXYZ", 9)]

class Url:
	def __init__(self, protocol, domain, port, path, anchor, get):
		self.protocol = "http"
		if protocol is not None:
			self.protocol = protocol
		self.domain = domain
		self.port = port
		self.path = path
		self.anchor = anchor
		self.get = ""
		if get is not None:
			get = [attr.split('=') for attr in get.split('&')]
			self.get = dict({attr[0]: attr[1] if len(attr) > 1 else "" for attr in get})
		else:
			self.get = dict()

	def __repr__(self):
		result = ""
		if self.domain:
			result += self.protocol + "://" + self.domain
			if self.port:
				result += ":" + self.port
		if self.path:
			result += self.path
		if self.anchor:
			result += "#" + self.anchor
		if self.get:
			result += "?" + "&".join([str(key) + "=" + str(value) for key, value in self.get.items()])
		return result

	def __hash__(self):
		return hash(repr(self))

	def __lt__(self, other):
		return repr(self) < repr(other)

	def __eq__(self, other):
		return repr(self) == repr(other)

def extractUrls(text, domain = None):
	r_domain = r'(?:([a-z]+)://)?([-A-Za-z0-9_]+(?:\.[-A-Za-z0-9_]+)+)(?::([0-9]+))?'
	r_path = r'((?:/[-A-Za-z0-9_%]+)+(?:\.(?:[Hh][Tt][Mm][Ll]?|[Pp][Yy]|[Pp][Hh][Pp]|[Jj][Pp][Ee]?[Gg]|[Pp][Nn][Gg]|[Gg][Ii][Ff]|[Tt][Xx][Tt]|[Mm][Dd]|[Pp][Dd][Ff]|[Xx][Ll][Ss][Xx]?)|/)?)'
	r_anchor = r'#([-A-Za-z0-9_]+)'
	r_get = r'\?([-A-Za-z0-9_]+=[-\?\.%:/A-Za-z0-9_\"\']*(?:\&[-A-Za-z0-9_]+=[-\?\.%:/A-Za-z0-9_\"\']*)*)'
	r_second = r_path + r'(?:' + r_anchor + ')?' + r'(?:' + r_get + r')?'
	r_link = r'(?![-_a-zA-Z0-9@])(?:' + r_domain + r_second + r'|' + r_second + r'|' + r_domain + r')'
	objs = re.finditer(r_link, text)
	result = []
	for obj in objs:
		groups = obj.groups()
		result.append((obj.start(0), obj.end(0), Url(
			groups[0] if groups[0] else groups[9], # protocol
			groups[1] if groups[1] else (groups[10] if groups[10] else domain), # domain
			groups[2] if groups[2] else groups[11], # port
			groups[3] if groups[3] else groups[6], # path
			groups[4] if groups[4] else groups[7], # anchor
			groups[5] if groups[5] else groups[8], # get
		)))
	return result

class SetEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, set):
			return list(obj)
		elif isinstance(obj, Url):
			return repr(obj)
		return json.JSONEncoder.default(self, obj)

class ScrapeHTML:
	def __init__(self):
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [
			("User-Agent", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"),
			("Accept", "text/pain"),
			("Accept-Language", "en-US,en;q=0.5"),
			("Accept-Encoding", "gzip, deflate, br")
		]

		self.url = None
		self.urls = []
		self.visited = []
		self.tovisit = []
		
		self.urlIndex = []
		self.urlIndexFile = None

		self.eng = enchant.Dict("en_US")
		self.eng.add("signup")
		self.eng.add("iframe")
		self.eng.add("analytics")

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
		self.people = {}
		self.groups = {}

	def getURL(self, url, uid):
		if not os.path.isfile(str(uid) + ".html"):
			with open(str(uid) + ".html", "w") as fptr:
				try:
					response = self.opener.open(url)
				except:
					return None
				data = response.read()
				try:
					decoded = UnicodeDammit(gzip.GzipFile(fileobj=io.BytesIO(data)).read(), ["windows-1252"], smart_quotes_to="html").unicode_markup
				except:
					decoded = UnicodeDammit(data, ["windows-1252"], smart_quotes_to="html").unicode_markup
				decoded = decoded.replace(u"%20", u" ").replace(u"\u00c2", u" ").replace(u"\xe2&euro;&trade;", u"\'").replace(u"\xe2&euro;&oelig;", u"\"").replace(u"\xe2&euro;", "\"").replace(u"\"&ldquo;", "-")
				#.replace(u"\xe2\x80\x9c", u"\"").replace(u"\xe2\x80\x9d", u"\"").replace(u"\xc3\xb3", u"\u00f3").replace(u"\xc3\xad", u"\u00ed").replace(u"\xe2\x20\xac\x21\x22", u"\'").replace(u"\xe2\x20\xac\x01\x53", u"\"").replace(u"\xe2\x20\xac", u"\"").replace(u"\xe2\x20\xac\x20\x1c", u" - ").replace(u"\xc3", u"\u00e9").replace(u"\x00\xc2", u" ")
				print >>fptr, decoded.encode('utf8')
		parser = etree.HTMLParser(target = Parser())
		with open(str(uid) + ".html", 'r') as fptr:
			data = fptr.read()
			parser.feed(data.decode('utf8'))
		return parser.close()

	def extractLinks(self, elem, addr):
		#if 'mailto:' not in elem:
			rng = []
			idx = 0

			urls = extractUrls(elem, self.curr_url.domain if self.curr_url else None)
			for start, end, url in urls:
				if (not url.domain or ("googleapis.com" not in url.domain and "googletagmanager.com" not in url.domain and "addthis.com" not in url.domain)) and (not url.path or ("wp-json" not in url.path and "wp-includes" not in url.path and "press" not in url.path and "resolutions" not in url.path)):
					if url not in self.urls:
						self.urls.append(url)
					if url in self.links:
						self.links[url].append(addr)
					else:
						self.links[url] = [addr]
					rng.append((idx, start))
					idx = end
			return '{}'.join([elem[s:e] for s, e in rng] + [elem[idx:]])
		#else:
		#	return elem

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
			for key, value in phone_codes:
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
				#if lword not in name_excl and lword not in name_incl:
				#	print "maybe add " + str(elem[obj.start(0)-10 if obj.start(0) >= 10 else 0:obj.start(0)].encode("utf8")) + "[" + str(word.encode("utf8")) + "]" + str(elem[obj.end(0):obj.end(0)+10 if obj.end(0)+10 < len(elem) else len(elem)].encode("utf8"))

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
		r_name = ur'(?<![A-Za-z0-9])[A-Z][a-z]+(?![A-Za-z0-9])\.?'

		names = re.finditer(r_name, elem, flags=re.UNICODE)




		options = [name.group(0) for name in names]

		#if len(options) > 0:
		#	print "Searching: " + str(elem)
		#	print "Options: " + str(options)

		r_pos = ur'Chair|Vice|Treasurer|Secretary|Director|Administrator|Fellow|Congressman|Congresswoman|Congressperson|Auditor|Leader|Senator|Representative|Member|Governer|Secretary|Controller|General|Attorney|Commissioner|Superindendent|Officer|President|Governor|Staff|Assemblymember|Rep\.|Sen\.|Speaker|Comptroller|Rev\.|Reverend|Mayor|Parliamentarian|Legal +Counsel|Chairperson'

		r_title = ur'(?:(?:[A-Z][a-z]+|[0-9]+[A-Za-z]*|[A-Z]+)(?: +| *- *))*(?=' + r_pos + ur')(?:' + r_pos + ur')(?![a-zA-Z0-9])(?: (?:of|for|in)(?:(?: +| *- *)(?:[A-Z][a-z]+|[0-9]+[A-Za-z]*|[A-Z]+))+)?'
		objs = re.finditer(r_title, elem, flags=re.UNICODE)

		rng = []
		start = 0
		for i, obj in enumerate(objs):
			title = obj.group(0).replace("  ", " ")
			if not title:
				print "Error: title matches empty string"
			if i > 0 and obj.start(0) - start <= 1:
				self.titles[-1] = (elem[rng[-1][1]:obj.end(0)], addr)
			else:
				#if options:
				#	print "Found: " + str(title)
				self.titles.append((title, addr))
				rng.append((start, obj.start(0)))
			start = obj.end(0)
		#if options:
		#	print ""
		return '{}'.join([elem[s:e] for s, e in rng] + [elem[start:]])

	def extractOrgs(self, elem, addr):
		r_org = r'Democrats|Dems|Republicans|Repubs|Reps|Democratic +Party|Republican +Party|Board|County|State|City|Committee|Council|District:?(?: +[0-9]+[A-Za-z]*)?|Caucus|BOE'

		r_orgtitle = r'(?:(?:[A-Z][a-z]+|[0-9]+[a-z]*)(?: +| *- *))*(?=' + r_org + ')(?:' + r_org + ')(?![A-Za-z0-9])'
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
		r_zip = r'[0-9]{5}(?:-[0-9]{4})?(?![A-Za-z0-9])'
		r_city = r'(?:[A-Z][a-z.-]+ ?)+'
		r_state = r'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'
		r_stateabbr = r'A[lL]\.?|A[kK]\.?|A[sS]\.?|A[zZ]\.?|A[rR]\.?|C[aA]\.?|C[oO]\.?|C[tT]\.?|D[eE]\.?|D\.?C\.?|F[mM]\.?|F[lL]\.?|G[aA]\.?|G[uU]\.?|H[iI]\.?|I[dD]\.?|I[lL]\.?|I[nN]\.?|I[aA]\.?|K[sS]\.?|K[yY]\.?|L[aA]\.?|M[eE]\.?|M[hH]\.?|M[dD]\.?|M[aA]\.?|M[iI]\.?|M[nN]\.?|M[sS]\.?|M[oO]\.?|M[tT]\.?|N[eE]\.?|N[vV]\.?|N[hH]\.?|N[jJ]\.?|N[mM]\.?|N[yY]\.?|N[cC]\.?|N[dD]\.?|M[pP]\.?|O[hH]\.?|O[kK]\.?|O[rR]\.?|P[wW]\.?|P[aA]\.?|P[rR]\.?|R[iI]\.?|S[cC]\.?|S[dD]\.?|T[nN]\.?|T[xX]\.?|U[tT]\.?|V[tT]\.?|V[iI]\.?|V[aA]\.?|W[aA]\.?|W[vV]\.?|W[iI]\.?|W[yY]\.?'
		
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
		r_streetbox = r'(?:' + r_po + '|' + r_street + ')(?![A-Za-z0-9])'
	
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
		r_aptnum = r'(:?[0-9]+[A-Za-z]* +' + r_apt + r'(?![A-Za-z0-9])|(?<![A-Za-z0-9])' + r_apt + r' +[0-9]+[A-Za-z]*(?:(?: *[-,&] *| +)[0-9]+[A-Za-z]*)*)'
		
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
					value = self.extractOrgs(value, addr)
					value = self.extractTitles(value, addr)
					value = self.extractNames(value, addr)
				elif key in ["href", "src", "style"]:
					value = self.extractEmails(value, addr)
					value = self.extractLinks(value, addr)

	def extractStr(self, tag, elem, addr):
		elem = elem.strip().replace(u'\xa0', u' ').replace(u'\xa9', u'')
		if elem:
			elem = self.extractPhones(elem, addr)
			elem = self.extractEmails(elem, addr)
			elem = self.extractStreet(elem, addr)
			elem = self.extractApt(elem, addr)
			elem = self.extractCity(elem, addr)
			if len(elem) < 128:
				elem = self.extractOrgs(elem, addr)
			if len(elem) < 32:
				elem = self.extractTitles(elem, addr)
				elem = self.extractNames(elem, addr)

	def normalize(self, content):
		levels = {
			"h1": 1,
			"h2": 2,
			"h3": 3,
			"h4": 4,
			"h5": 5,
			"h6": 6,
			"h7": 7,
			"h8": 8,
		}

		stack = [(0, [])] # (level, element content)
		i = 0
		for elem in content:
			if isinstance(elem, Tag):
				self.normalize(elem.content)

			if not isinstance(elem, Tag) or elem.name not in levels:
				stack[-1][1].append(elem)
			else:
				level = levels[elem.name]
				while level <= stack[-1][0]:
					del stack[-1]

				stack[-1][1].append(Div() << elem)
				stack.append((level, stack[-1][1][-1].content))
		del content[:]
		content.extend(stack[0][1])

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

	def findBounds(self, name, start, end, maxdepth, addr, data):
		for name1, tests in data.items():
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
		return (start, end, maxdepth)

	def develop(self, props = None):
		membership = []
		organization = {}
		for org, addr in self.orgs:
			root = []
			root = self.findRoot(root, addr, self.street)
			root = self.findRoot(root, addr, self.apt)
			root = self.findRoot(root, addr, self.phones)
			root = self.findRoot(root, addr, self.fax)
			root = self.findRoot(root, addr, self.names)
			found = False
			for addrs in self.names.values():
				for test in addrs:
					if test[0:len(root)] == root:
						found = True
						break
				if found:
					break

			if not found:
				if org in organization:
					organization[org].append(addr)
				else:
					organization[org] = [addr]
			else:
				membership.append((org, addr))
		self.orgs = []

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
			if name in self.people:
				entry = self.people[name]
		
			if props:
				for key, value in props.items():
					if key in entry:
						if isinstance(entry[key], set):
							entry[key].add(value)
						elif isinstance(entry[key], list):
							entry[key].append(value)
					else:
						entry[key] = value

			for addr in addrs:
				maxdepth = 0
				start = None
				end = None
				start, end, maxdepth = self.findBounds(name, start, end, maxdepth, addr, self.names)
				start, end, maxdepth = self.findBounds(name, start, end, maxdepth, addr, organization)
			
				cstart = addr[maxdepth] if maxdepth < len(addr) else start
				base = addr[0:maxdepth]
				if start is None and end is None:
					root = []
					root = self.findRoot(root, addr, self.emails)
					root = self.findRoot(root, addr, self.phones)
					root = self.findRoot(root, addr, self.links)
					root = self.findRoot(root, addr, self.fax)
					if len(root) > len(base):
						base = root
						start = None
						end = None

				entry = self.buildEntry(entry, base, cstart, end, self.emails, 'email')
				entry = self.buildEntry(entry, base, cstart, end, self.phones, 'phone')
				entry = self.buildEntry(entry, base, cstart, end, self.links, 'link')
				entry = self.buildEntry(entry, base, cstart, end, self.fax, 'fax')
				entry = self.buildEntry(entry, base, cstart, end, self.city, 'city')
				entry = self.buildEntry(entry, base, cstart, end, self.street, 'street')
				entry = self.buildEntry(entry, base, cstart, end, self.apt, 'apt')
				entry = self.buildEntry(entry, base, start, end, self.titles, 'title')
				entry = self.buildEntry(entry, base, cstart, end, self.offices, 'office')
				entry = self.buildEntry(entry, base, start, end, membership, 'org')

			self.people[name] = entry

		for name, addrs in organization.items():
			entry = {}
			if name in self.groups:
				entry = self.groups[name]
			
			for addr in addrs:
				maxdepth = 0
				start = None
				end = None
				start, end, maxdepth = self.findBounds(name, start, end, maxdepth, addr, self.names)
				start, end, maxdepth = self.findBounds(name, start, end, maxdepth, addr, organization)
			
				#start = addr[maxdepth] if maxdepth < len(addr) else addr
				base = addr[0:maxdepth]
				if start is None and end is None:
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
				entry = self.buildEntry(entry, base, start, end, self.offices, 'office')
				entry = self.buildEntry(entry, base, start, end, membership, 'org')

			self.groups[name] = entry

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

	def scrape(self, url, uid, props=None, owner=None):
		self.curr_url = url
		parser = self.getURL(repr(url), uid)
		if parser:
			syntax = parser.syntax
			self.normalize(syntax.content)
			self.traverse(syntax)
			self.develop(props)

	def schedule(self, url, props, owner, recurse):
		self.tovisit.append((url, props, owner, recurse))

	def getUID(self, url):
		if not self.urlIndexFile:
			self.urlIndexFile = open("index.txt", "a+")
			self.urlIndexFile.seek(0, 0)
			for line in self.urlIndexFile:
				urls = extractUrls(line)
				if self.urlIndex:
					self.urlIndex.extend([link for start, end, link in urls])
				else:
					self.urlIndex = [link for start, end, link in urls]
		if url in self.urlIndex:
			return self.urlIndex.index(url)
		else:
			uid = len(self.urlIndex)
			self.urlIndex.append(url)
			print >>self.urlIndexFile, url
			return uid

	def crawl(self):
		i = 0
		while i < len(self.tovisit) and len(self.visited) < 100:
			url, props, owner, recurse = self.tovisit[i]
			if url not in self.visited:
				uid = self.getUID(url)
				self.visited.append(url)
				print str(len(self.visited)) + " " + repr(url)
				self.scrape(url, uid, props, owner)
				if recurse:
					recurse(self, url, props, owner, self.urls)
			i += 1

def recurse(scraper, url, props, owner, urls):
	for test in urls:
		if test.domain == url.domain and (not test.path or not re.search(r'\.(?:[Jj][Pp][Ee]?[Gg]|[Pp][Nn][Gg]|[Gg][Ii][Ff]|[Pp][Dd][Ff]|[Xx][Ll][Ss][Xx]?)', test.path)):
			scraper.schedule(test, props, owner, recurse)

scraper = ScrapeHTML()
scraper.schedule(Url("http", "www.cadem.org", None, None, None, None), {"state":"California","party":"Democratic"}, None, recurse) 
#scraper.schedule(Url("http", "www.cadem.org", None, "/news/press-releases/2009/california-democratic-party-protect-all-californians-stop-the-severe-cuts-and-support-a-balanced-solution", None, None), {"state":"California","party":"Democratic"}, None, None) 
#scraper.schedule(Url("http", "www.cadem.org", None, "/our-party/elected-officials", None, None), {"state":"California","party":"Democratic"}, None, None) 
#scraper.schedule(Url("http", "www.nydems.org", None, None, None, None), {"state":"New York","party":"Democratic"}, None, recurse) 
scraper.crawl()

#scraper.scrape("http://www.cadem.org/our-party/leaders", {"state":"California","party":"Democratic"})
#scraper.scrape("http://www.cadem.org/our-party/elected-officials", {"state":"California","party":"Democratic"})
#scraper.scrape("http://www.cadem.org/our-party/our-county-committees", {"state":"California","party":"Democratic"})
#scraper.scrape("http://www.cadem.org/our-party/dnc-members", {"state":"California","party":"Democratic"})
#scraper.scrape("https://nydems.org/our-party/", {"state":"New York","party":"Democratic"})
#scraper.scrape("https://missouridemocrats.org/county-parties/", {"state":"Missouri","party":"Democratic"})
#scraper.scrape("https://missouridemocrats.org/officers-and-staff/", {"state":"Missouri","party":"Democratic"})
#scraper.scrape("https://www.indems.org/our-party/state-committee/", {"state":"Indiana","party":"Democratic"})

#scraper.scrape("https://northplainfield.org/government/departments/directory.php")
#scraper.scrape("http://aldemocrats.org/local/calhoun")
#scraper.scrape("http://jameswelch.co/our-team/")
#scraper.scrape("http://jameswelch.co/our-candidates/")
#scraper.scrape("https://adlcc.com/our-members/state-senate/")
#scraper.scrape("https://adlcc.com/our-members/state-house/")
#scraper.scrape("https://ctdems.org/your-party/officers/")

# TODO check similarity between name or organization name and emails or links
# s = SequenceMatcher(None, name, link)
# s.ratio()

print json.dumps(scraper.people, indent=2, cls=SetEncoder)
print json.dumps(scraper.groups, indent=2, cls=SetEncoder)

