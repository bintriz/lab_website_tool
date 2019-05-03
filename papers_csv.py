#!/usr/bin/env python3

import argparse
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from time import sleep, localtime, strftime
import re
import sys
from collections import defaultdict

class MyNCBI:
    myncbi = webdriver.Chrome(); # or webdriver.PhantomJS(service_log_path=os.path.devnull)
    myncbi.implicitly_wait(5)

    pubmed = webdriver.Chrome(); # or webdriver.PhantomJS(service_log_path=os.path.devnull)
    pubmed.implicitly_wait(5)

    members = None
    papers = defaultdict(list)

    def __init__(self, cid):
        self.scrap_myncbi(cid)

    def scrap_myncbi(self, cid):
        self.myncbi.get("http://www.ncbi.nlm.nih.gov/sites/myncbi/browse/collection/{cid}/?sort=date&direction=ascending".format(cid=cid))

    def set_members(self, fname):
        if fname is not None:
            with open(fname) as f:
                self.members = [line.strip() for line in f]

    def highlight_members(self, author):
        if self.members is not None:
            for member in self.members:
                author = author.replace(member, "==^"+member+"$==")
        return author

    def paper_from_pmid(self, pmid):
        self.pubmed.get("https://ncbi.nlm.nih.gov/pubmed/{pmid}".format(pmid=pmid))

        author_tags = self.pubmed.find_elements_by_xpath('//div[@class="auths"]/a')
        author = self.highlight_members(', '.join([tag.text for tag in author_tags]))
 
        cite_tag = self.pubmed.find_element_by_xpath('//div[@class="cit"]')
        journal, info = cite_tag.text.split(sep='. ')[:2]
        year = info.strip()[:4]
        try:
            issue = info.split(sep=';')[1].strip().rstrip(".")
        except IndexError:
            issue = "[Epub ahead of print]"
        paper = '{{title}}|{author}|{journal}|{year}|{issue}|'.format(author=author, journal=journal, year=year, issue=issue)

        link_tag = self.pubmed.find_elements_by_xpath('//div[@class="icons portlet"]/a')
        if link_tag:
            paper += '{href}|{src}|'.format(href=link_tag[0].get_attribute('href'),
              src=link_tag[0].find_element_by_tag_name('img').get_attribute('src'))
        else:
          paper += '||'
        paper += 'https://ncbi.nlm.nih.gov/pubmed/{pmid}|imgs/pubmed.png\n'.format(pmid=pmid)

        return (year, paper)

    def parse_myncbi(self):
        while True:
            title_tags = self.myncbi.find_elements_by_xpath('//div[@class="rprt"]')

            for tag in title_tags:
                text = tag.text.split('\n')
                index = text[0][:-1]
                title = text[1]
                sys.stderr.write("Parsing {index}. {title}...\n".format(
                        index=index, title=" ".join(title.split()[:4])))

                source = text[-1]
                pub_type = re.search("\[(.+)\]", source).group(1)
                if pub_type == "book":
                    author = self.highlight_members(text[2].rstrip("."))
                    issue, info = text[3].split("; ")
                    issue = issue.rstrip(".")
                    year = info[:4]
                    chapter, page = re.search("(Chapter.+)(\d+-\d+)p.", info).groups()
                    paper = '''{title}|{author}|{chapter}|{year}|{issue}; {page}||||\n'''.format(index=index, chapter=chapter, title=title, 
                                          author=author, issue=issue, year=year, page=page) 
                elif pub_type == "journal": 
                    m = re.search("PMID: (\d+)", source)
                    if m:
                        pmid = m.group(1)
                        year, paper = self.paper_from_pmid(pmid)
                        paper = paper.format(index=index, title=title)
                    else:
                        author, info = text[2:4]
                        author = self.highlight_members(author.rstrip("."))
                        journal, issue = info.split(". ")[:2]
                        issue = issue.rstrip(".")
                        year = issue[:4]
                        paper = '''{title}|{author}|{journal}|{year}|{issue}||||\n'''.format(index=index, title=title, author=author, year=year, journal=journal, issue=issue)
                self.papers[year].append(paper)

            page_input_tag = self.myncbi.find_element_by_xpath('//input[@class="num"]')
            last = page_input_tag.get_attribute('last')
            page = page_input_tag.get_attribute('value')

            if page == last: 
                break

            next_tag = self.myncbi.find_element_by_link_text('Next >')
            next_tag.click()

    def get_csv(self):
        self.parse_myncbi()

        total_n = 0
        csv = ""
        for year, year_papers in sorted(self.papers.items(), reverse=True):
            year_papers.reverse()
            year_n = len(year_papers)
            total_n += year_n
            csv +="".join(year_papers);
        return csv

def main():
    parser = argparse.ArgumentParser(
        description='html builder for a publication list')

    parser.add_argument('-m', '--members', metavar='lab_member_list.txt', help='Lab member list to highlight in authors')
    parser.add_argument('-c', '--cid', metavar='12345', required=True, help='My NCBI collection number')

    args = parser.parse_args()
    
    m = MyNCBI(args.cid)
    m.set_members(args.members)
    print(m.get_csv(),end='')

if __name__ == "__main__":
    main()
