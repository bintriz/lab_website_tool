#!/usr/bin/env python3

import argparse
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from time import sleep, localtime, strftime
import re
import sys
from collections import defaultdict

class MyNCBI:
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    path = os.path.dirname(os.path.abspath(__file__)) + '/chromedriver'

    def __init__(self, authid, members_fname=None):
        self.papers = defaultdict(list)
        self.set_members(members_fname)

        self.myncbi = webdriver.Chrome(executable_path=self.path, options=self.options)
        self.myncbi.implicitly_wait(5)
        self.pubmed = webdriver.Chrome(executable_path=self.path, options=self.options)
        self.pubmed.implicitly_wait(5)

        self.scrap_myncbi(authid)

        self.myncbi.quit()
        self.pubmed.quit()

    def scrap_myncbi(self, authid):
        self.myncbi.get("https://www.ncbi.nlm.nih.gov/myncbi/{authid}.1/bibliography/public/?sortby=pubDate&sdirection=ascending".format(authid=authid))
        index = 0
        while True:
            for docsum in self.myncbi.find_elements_by_xpath('//div[@class="ncbi-docsum"]'):
                index += 1

                try:
                    title = docsum.find_element_by_xpath('./span[@class="title"]').text
                except NoSuchElementException:
                    title = docsum.find_element_by_xpath('./a').text
                
                sys.stderr.write("Scraping {index}. {title}...\n".format(index=index, title=title[:40]))

                author = docsum.find_element_by_xpath('./span[@class="authors"]').text.rstrip(".")
                author = self.highlight_members(author)
                
                try:
                    pmid = docsum.find_element_by_xpath('./span[@class="pmid"]').text.split()[-1]
                    year, paper = self.paper_from_pmid(pmid)
                    paper = paper.format(index=index, title=title, author=author)
                except NoSuchElementException:
                    year = docsum.find_element_by_xpath('./span[@class="displaydate"]').text[:4]
                    page = docsum.find_element_by_xpath('./span[@class="page"]').text.rstrip(".")
                    try:
                        journal = docsum.find_element_by_xpath('./span[@class="journalname"]').text.rstrip(".")
                        volume = docsum.find_element_by_xpath('./span[@class="volume"]').text
                        issue = docsum.find_element_by_xpath('./span[@class="issue"]').text
                        
                        paper = '''<li value="{index}" style="font-size:11pt;margin-bottom:5pt">
                        <div style="color:#1a0dab;font-family:sans-serif;margin-bottom:2pt"><b>{title}</b></div>
                        <div style="font-family:sans-serif;font-size:small;margin-left:3pt;margin-bottom:2pt">{author}</div>
                        <div style="font-family:sans-serif;font-size:small">
                        <table style="border-collpase:collapse;border:0"><tr>
                        <td style="border:0;vertical-align:top">
                        <i><b>{journal}</b></i> {year}; {volume}{issue}{page}.</td></tr></table>
                        </div></li>'''.format(
                            index=index, 
                            title=title, 
                            author=author, 
                            journal=journal,
                            year=year, 
                            volume=volume,
                            issue=issue,
                            page=page)
                    except NoSuchElementException:    
                        editor = docsum.find_element_by_xpath('./span[@class="editors"]').text    
                        ch_num = docsum.find_element_by_xpath('./span[@class="chapter-details"]').text
                        ch_title = docsum.find_element_by_xpath('./span[@class="chaptertitle"]').text
                        publisher = docsum.find_element_by_xpath('./span[@class="book-publisher"]').text
                        
                        paper = '''<li value="{index}" style="font-size:11pt;margin-bottom:5pt">
                        <div style="color:#1a0dab;font-family:sans-serif;margin-bottom:2pt"><b>{ch_title}</b></div>
                        <div style="font-family:sans-serif;font-size:small;margin-left:3pt;margin-bottom:2pt">{author}</div>
                        <div style="font-family:sans-serif;font-size:small">
                        <table style="border-collpase:collapse;border:0">
                        <tr><td style="border:0;vertical-align:top">In: {title} {editor}</td></tr>
                        <tr><td style="border:0;vertical-align:top">{publisher} {year}. {ch_num} {page}</td></tr>
                        </table></div></li>'''.format(
                            index=index, 
                            ch_title=ch_title,
                            author=author,
                            title=title, 
                            editor=editor,
                            publisher=publisher,
                            year=year, 
                            ch_num=ch_num,
                            page=page)

                self.papers[year].append(paper)

            try:
                self.myncbi.find_element_by_xpath('//a[@class="nextPage enabled"]').click()
            except NoSuchElementException:
                break

    def set_members(self, fname):
        if fname is None:
            self.members = None
        else:
            with open(fname) as f:
                self.members = [line.strip() for line in f]

    def highlight_members(self, author):
        if self.members is not None:
            for member in self.members:
                author = author.replace(member, "==^"+member+"$==")
        return author

    def paper_from_pmid(self, pmid):
        self.pubmed.get("https://pubmed.ncbi.nlm.nih.gov/{pmid}".format(pmid=pmid))

        journal = self.pubmed.find_element_by_xpath('//button[@id="full-view-journal-trigger"]').text
        cite_info = self.pubmed.find_element_by_xpath('//span[@class="cit"]').text
        year = re.search(r"[12]\d\d\d", cite_info.split(sep=';')[0])[0] 
        try:
            issue = cite_info.split(sep=';')[1].strip().rstrip(".")
        except IndexError:
            issue = "[Epub ahead of print]"
        paper = '''<li value="{{index}}" style="font-size:11pt;margin-bottom:5pt">
        <div style="color:#1a0dab;font-family:sans-serif;margin-bottom:2pt"><b>{{title}}</b></div>
        <div style="font-family:sans-serif;font-size:small;margin-left:3pt;margin-bottom:2pt">{{author}}</div>
        <div style="font-family:sans-serif;font-size:small">
        <table style="border-collpase:collapse;border:0"><tr>
        <td style="border:0;vertical-align:top">
        <i><b>{journal}</b></i> {year}; {issue}.</td>'''.format(journal=journal, year=year, issue=issue)

        link_tag = self.pubmed.find_elements_by_xpath('//a[contains(@class,"link-item") and contains(@class,"dialog-focus")]')
        if link_tag:
            paper += '''<td style="border:0;text-indent:2pt">
            <a href="{href}"><img src="{src}" style="height:16px" />
            </a></td>'''.format(
                href=link_tag[0].get_attribute('href'), 
                src=link_tag[0].find_element_by_tag_name('img').get_attribute('src'))
        paper += '''<td style="border:0;text-indent:3pt">
        <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">
        <img style="height:16px" src="//upload.wikimedia.org/wikipedia/commons/thumb/f/fb/US-NLM-PubMed-Logo.svg/200px-US-NLM-PubMed-Logo.svg.png" />
        </a></td></tr></table></div></li>'''.format(pmid=pmid)

        return (year, paper)

    @property
    def html(self):
        total_n = 0
        html = ""
        for year, year_papers in sorted(self.papers.items(), reverse=True):
            year_papers.reverse()
            year_n = len(year_papers)
            total_n += year_n

            html += '''<table style="border-collapse:collapse"><tbody><tr>
            <td><h3 style="margin:0">{year} ({year_n})</h3></td>
            </tr></tbody></table><ol>{year_html}</ol>'''.format(
                year=year, year_n=year_n, year_html="".join(year_papers))

        html = '''<table style="border-collapse:collapse"><tbody><tr>
        <td><h3 style="margin:0">Total papers: {total_n}</h3></td>
        <td style="vertical-align:middle;text-indent:5pt">(Last updated: {time})</td>
        </tr></tbody></table><p></p>'''.format(
            total_n=total_n, time=strftime("%a, %m/%d/%Y %I:%M:%S %p %Z", localtime())) + html

        return BeautifulSoup(html, 'html.parser').prettify().replace("==^", "<u><b>").replace("$==", "</b></u>")

def main():
    parser = argparse.ArgumentParser(
        description='html builder for a publication list')

    parser.add_argument('-m', '--members', metavar='lab_member_list.txt', help='Lab member list to highlight in authors')
    parser.add_argument('-a', '--authid', metavar='firstname.lastname', required=True, help='My NCBI author name. ex) alexej.abyzov')

    args = parser.parse_args()
    
    m = MyNCBI(args.authid, args.members)
    print(m.html)

if __name__ == "__main__":
    main()
