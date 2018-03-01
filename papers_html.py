#!/usr/bin/env python3

import argparse
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from time import sleep, localtime, strftime
import re
import sys
from collections import defaultdict

def paper_from_pmid(pmid, driver):
    driver.get("https://ncbi.nlm.nih.gov/pubmed/{pmid}".format(pmid=pmid))

    author_tags = driver.find_elements_by_xpath('//div[@class="auths"]/a')
    author = ', '.join([tag.text for tag in author_tags])
    author = author.replace("Abyzov A", "<u>Abyzov A</u>")

    cite_tag = driver.find_element_by_xpath('//div[@class="cit"]')
    journal, info = cite_tag.text.split(sep='. ')[:2]
    year = info.strip()[:4]
    try:
        issue = info.split(sep=';')[1].strip()
    except IndexError:
        issue = "[Epub ahead of print]"
    paper = '''<li value="{{index}}" style="font-size:medium;margin-bottom:5pt">
    <div style="color:#1a0dab;font-family:sans-serif;margin-bottom:2pt"><b>{{title}}</b></div>
    <div style="font-family:sans-serif;font-size:small;margin-left:10pt;margin-bottom:2pt">{author}</div>
    <div style="font-family:sans-serif;font-size:small;margin-left:10pt">
    <table style="border-collpase:collapse;border:0"><tr>
    <td style="border:0;vertical-align:middle">
    <i><b>{journal}</b></i> {year}; {issue}.</td>'''.format(author=author, journal=journal, year=year, issue=issue)

    link_tag = driver.find_elements_by_xpath('//div[@class="icons portlet"]/a')
    if link_tag:
        paper += '''<td style="border:0;text-indent:5pt">
        <a href="{href}"><img src="{src}" style="height:16px" />
        </a></td>'''.format(
            href=link_tag[0].get_attribute('href'), 
            src=link_tag[0].find_element_by_tag_name('img').get_attribute('src'))
    paper += '''<td style="border:0;text-indent:3pt">
    <a href="https://ncbi.nlm.nih.gov/pubmed/{pmid}">
    <img style="height:16px" src="//upload.wikimedia.org/wikipedia/commons/thumb/f/fb/US-NLM-PubMed-Logo.svg/200px-US-NLM-PubMed-Logo.svg.png" />
    </a></td></tr></table></div></li>'''.format(pmid=pmid)

    return (year, paper)

def parse_myncbi_collection(cid):
    driver = webdriver.PhantomJS(service_log_path=os.path.devnull)
    driver.implicitly_wait(5)
    driver.get("http://www.ncbi.nlm.nih.gov/sites/myncbi/browse/collection/{cid}/?sort=date&direction=ascending".format(cid=cid))
    
    driver2 = webdriver.PhantomJS(service_log_path=os.path.devnull)
    driver2.implicitly_wait(5)

    papers = defaultdict(list)
    while True:
        title_tags = driver.find_elements_by_xpath('//div[@class="rprt"]')

        for tag in title_tags:
            text = tag.text.split('\n')
            index = text[0][:-1]
            title = text[1]
            sys.stderr.write("Parsing {index}. {title}...\n".format(
                    index=index, title=" ".join(title.split()[:4])))

            source = text[-1]
            pub_type = re.search("\[(.+)\]", source).group(1)
            if pub_type == "book":
                author = text[2].rstrip(".").replace("Abyzov A", "<u>Abyzov A</u>")
                issue, info = text[3].split("; ")
                year = info[:4]
                chapter, page = re.search("(Chapter.+)(\d+-\d+)p.", info).groups()
                paper = '''<li value="{index}" style="font-size:medium;margin-bottom:5pt">
                <div style="color:#1a0dab;font-family:sans-serif;margin-bottom:2pt"><b>{chapter}. In: {title}.</b></div>
                <div style="font-family:sans-serif;font-size:small;margin-left:10pt;margin-bottom:2pt">{author}</div>
                <div style="font-family:sans-serif;font-size:small;margin-left:10pt">
                <table style="border-collpase:collapse;border:0"><tr>
                <td style="border:0;vertical-align:middle">
                {issue}: {year}. p.{page}.</td></tr></table>
                </div></li>'''.format(index=index, chapter=chapter, title=title, 
                                      author=author, issue=issue, year=year, page=page) 
            elif pub_type == "journal": 
                m = re.search("PMID: (\d+)", source)
                if m:
                    pmid = m.group(1)
                    year, paper = paper_from_pmid(pmid, driver2)
                    paper = paper.format(index=index, title=title)
                else:
                    author, info = text[2:4]
                    author = author.rstrip(".").replace("Abyzov A", "<u>Abyzov A</u>")
                    journal, issue = info.split(". ")[:2]
                    year = issue[:4]
                    paper = '''<li value="{index}" style="font-size:medium;margin-bottom:5pt">
                    <div style="color:#1a0dab;font-family:sans-serif;margin-bottom:2pt"><b>{title}</b></div>
                    <div style="font-family:sans-serif;font-size:small;margin-left:10pt;margin-bottom:2pt">{author}</div>
                    <div style="font-family:sans-serif;font-size:small;margin-left:10pt">
                    <table style="border-collpase:collapse;border:0"><tr>
                    <td style="border:0;vertical-align:middle">
                    <i><b>{journal}</b></i> {issue}.</td></tr></table>
                    </div></li>'''.format(index=index, title=title, author=author, journal=journal, issue=issue)
            papers[year].append(paper)

        page_input_tag = driver.find_element_by_xpath('//input[@class="num"]')
        last = page_input_tag.get_attribute('last')
        page = page_input_tag.get_attribute('value')

        if page == last: 
            return papers

        next_tag = driver.find_element_by_link_text('Next >')
        next_tag.click()

def build_html(papers):
    total_n = 0
    html = ""
    for year, year_papers in sorted(papers.items(), reverse=True):
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

    return html

def main():
    parser = argparse.ArgumentParser(
        description='html builder for a publication list')

    parser.add_argument(
        '-c', '--collection', metavar='id',
        help='my ncbi collection number',
        required=True)

    args = parser.parse_args()

    papers = parse_myncbi_collection(args.collection)
    html = BeautifulSoup(build_html(papers), 'html.parser')
    print(html.prettify())
    
if __name__ == "__main__":
    main()
