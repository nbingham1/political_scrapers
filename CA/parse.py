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
import pprint

from pyhtml.html import *
from pyhtml.parse import *

class ParseCA:
	def __init__(self):
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [
			("Host", "www.cadem.org"),
			("User-Agent", "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"),
			("Accept", "text/pain"),
			("Accept-Language", "en-US,en;q=0.5"),
			("Accept-Encoding", "gzip, deflate, br")
		]
		self.api = {
			"elected": 'http://www.cadem.org/our-party/elected-officials',
			"leaders": 'http://www.cadem.org/our-party/leaders',
			"county" : 'http://www.cadem.org/our-party/our-county-committees',
			"committee": 'http://www.cadem.org/our-party/standing-committees',
			"dnc": 'http://www.cadem.org/our-party/dnc-members'
		}

	def getURL(self, url, cache):
		if not os.path.isfile(cache + ".html"):
			with open(cache + ".html", "w") as fptr:
				response = self.opener.open(url)
				data = io.BytesIO(response.read())
				decoded = gzip.GzipFile(fileobj=data).read().decode("latin1").encode('utf8')
				print >>fptr, decoded
		parser = Parser()
		with open(cache + ".html", 'r') as fptr:
			data = fptr.read().decode('utf8').replace("%20", "").replace(u"\xe2\x80\x9c", u"\"").replace(u"\xe2\x80\x9d", u"\"")
			parser.feed(data)
		return parser


	def scrapeOfficials(self, parser):
		result = []
		
		officials = parser.syntax.get(Class="official")
		for official in officials:
			entry = {}
			query = official.get("span", Class="title")
			if len(query) == 1:
				entry["name"] = query[0].content[0]
			elif len(query) > 1:
				print "Error: More than one name"
				print official
				print ""

			query = official.get("span", Class="office")
			if len(query) == 1:
				entry["office"] = query[0].content[0]
			elif len(query) > 1:
				print "Error: More than one office"
				print official
				print ""

			query = official.get(Class="phone")
			if len(query) == 1:
				entry["phone"] = query[0].content[0]
			elif len(query) > 1:
				print "Error: More than one phone"
				print official
				print ""

			query = official.get("img")
			if len(query) == 1:
				entry["img"] = u"http://www.cadem.org" + query[0].attrs["src"]
			elif len(query) > 1:
				print "Error: More than one image"
				print official
				print ""

			query = official.get(Class="body")
			if len(query) == 1:
				query = query[0].get("p")
				if len(query) > 1:
					entry["office"] = query[0].content[0]
					entry["name"] = query[1].content[0].content[0]

			links = []
			for link in official.get("a"):
				link = link.attrs["href"]
				if u"mailto:" in link:
					links.append(link.replace(u"mailto:", u""))
				elif link[0:7] == u"http://":
					links.append(link)
				elif link[0:8] == u"https://":
					links.append(link)
				elif link[0] == u'/':
					subparser = self.getURL("http://www.cadem.org" + link, link[link.rfind('/')+1:])
					subparser = subparser.syntax.get("article")[0]
					query = subparser.get("span", Class="office")
					if len(query) == 1:
						entry["office"] = query[0].content[0]
					elif len(query) > 1:
						print "Error: More than one office"
						print subparser
						print ""

					query = subparser.get(Class="phone")
					if len(query) == 1:
						entry["phone"] = query[0].content[0]
					elif len(query) > 1:
						print "Error: More than one phone"
						print subparser
						print ""

					query = subparser.get("img")
					if len(query) == 1:
						entry["img"] = u"http://www.cadem.org" + query[0].attrs["src"]
					elif len(query) > 1:
						print "Error: More than one image"
						print subparser
						print ""

					for sublink in subparser.get("a"):
						sublink = sublink.attrs["href"]
						if u"mailto:" in sublink:
							links.append(sublink.replace(u"mailto:", u""))

			if links:
				entry["links"] = links

			query = official.get("div", Class="office")
			address = []
			for office in query:
				loc = {}	
				query2 = office.get("h2")
				if len(query2) == 1:
					loc["name"] = query2[0].content[0]
				elif len(query2) > 1:
					print "Error: More than one office name"

				query2 = office.get("p")
				if len(query2) == 1:
					for elem in query2[0].content:
						if not isinstance(elem, STag):
							if ": " in elem:
								sep = elem.index(":")
								loc[elem[0:sep].lower()] = elem[sep+2:]
							elif elem.strip() and "street" not in loc:
								loc["street"] = elem
							elif elem.strip():
								loc["street"] += " " + elem

				address.append(loc)
			if address:
				entry["address"] = address
			entry["state"] = "California"

			if entry["name"] != "DNC Members":
				result.append(entry)
		return result

	def scrapeCounties(self, parser):
		result = []
		
		counties = parser.syntax.get(Class="county")
		for county in counties:
			entry = {}
			
			query = county.get(Class="phone")
			if len(query) == 1:
				entry["phone"] = query[0].content[0]
			elif len(query) > 1:
				print "Error: More than one phone"
				print county
				print ""

			query = county.get(Class="title")
			if len(query) == 1:
				entry["county"] = query[0].content[0]
			elif len(query) > 1:
				print "Error: More than one phone"
				print county
				print ""

			query = county.get(Class="chair")
			if len(query) == 1:
				entry["name"] = query[0].content[0][7:].replace(u" - NEW CHAIR!", u"").replace(u", Chair", u"").replace(u"\t", u" ").replace(u" (Chair)", u"").replace(u" (Co-Chair)", u"").strip()
				entry["office"] = "County Chair"
			elif len(query) > 1:
				print "Error: More than one phone"
				print county
				print ""

			links = []
			for link in county.get("a"):
				link = link.attrs["href"]
				if u"mailto:" in link:
					links.append(link.replace(u"mailto:", u"").replace(u" - NEW", u""))
				elif link[0:7] == u"http://":
					links.append(link)
				elif link[0:8] == u"https://":
					links.append(link)
				elif link[0] == u'/':
					subparser = self.getURL("http://www.cadem.org" + link, link[link.rfind('/')+1:])
					subparser = subparser.syntax.get("article")[0]
					query = subparser.get("span", Class="office")
					if len(query) == 1:
						entry["office"] = query[0].content[0]
					elif len(query) > 1:
						print "Error: More than one office"
						print subparser
						print ""

					query = subparser.get(Class="phone")
					if len(query) == 1:
						entry["phone"] = query[0].content[0]
					elif len(query) > 1:
						print "Error: More than one phone"
						print subparser
						print ""

					query = subparser.get("img")
					if len(query) == 1:
						entry["img"] = u"http://www.cadem.org" + query[0].attrs["src"]
					elif len(query) > 1:
						print "Error: More than one image"
						print subparser
						print ""

					for sublink in subparser.get("a"):
						sublink = sublink.attrs["href"]
						if u"mailto:" in sublink:
							links.append(sublink.replace(u"mailto:", u""))

			if links:
				entry["links"] = links

			entry["state"] = "California"

			if " - " in entry["name"]:
				entry1 = entry.copy()
				names = entry["name"].split(u" - ")
				phones = entry["phone"].split(u" or ")
				links = [[], []]
				for link in entry["links"]:
					sp = link.split(u" or ")
					if len(sp) == 1:
						links[0].append(link)
						links[1].append(link)
					elif len(sp) > 1:
						links[0].append(sp[0][0:sp[0].rfind("(")-1] if "(" in sp[0] else sp[0])
						links[1].append(sp[1][0:sp[1].rfind("(")-1] if "(" in sp[1] else sp[1])

				phones = entry["phone"].split(u" or ")
				entry["name"] = names[0]
				entry1["name"] = names[1]
				entry["phone"] = phones[0][0:phones[0].rfind("(")-1] if "(" in phones[0] else phones[0]
				entry1["phone"] = phones[1][0:phones[1].rfind("(")-1] if "(" in phones[1] else phones[1]
				entry["links"] = links[0]
				entry1["links"] = links[1]
				result.append(entry1)

			for i, link in enumerate(entry["links"]):
				if u" or " in link:
					sp = link.split(" or ")
					entry["links"][i] = sp[0]
					for j in range(1, len(sp)):
						entry["links"].append(sp[j])

			result.append(entry)

		return result

	def getElected(self):
		parser = self.getURL(self.api["elected"], "elected")
		return self.scrapeOfficials(parser)

	def getLeaders(self):
		parser = self.getURL(self.api["leaders"], "leaders")
		return self.scrapeOfficials(parser)
	
	def getCounty(self):
		parser = self.getURL(self.api["county"], "county")
		return self.scrapeCounties(parser)
	
	#def getCommittee(self, people):
	#	parser = self.getURL(self.api["committee"], "committee")
	#	return self.scrape(parser)
		
	#def getDNC(self, people):
	#	parser = self.getURL(self.api["dnc"], "dnc")
	#	return people	

parser = ParseCA()

results = []
results += parser.getElected()
results += parser.getLeaders()
results += parser.getCounty()
#parser.getAPI("committee")
#results = parser.getDNC(results)

print json.dumps(results, indent=2)

#keys = []
#for result in results:
#	keys += result.keys()
#keys = sorted(set(keys))

#for key in keys:
#	print key+"\t",
#print ""

#for result in results:
#	for key in keys:
#		if key in result:
#			print repr(result[key]) + "\t",
#		else:
#			print "\t",
#	print ""

#for result in results:
#	for key, value in result.items():
#		print key + u": " + repr(value)
#	print ""
