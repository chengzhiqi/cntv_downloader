# -*- coding: utf-8 -*-

'''
Created on Aug 26, 2012

@author: coolcute

Require: wget MP4Box 
'''

import argparse
import os
import errno
import urllib
import subprocess
import concurrent.futures

from urllib.request import urlopen
from html.parser import HTMLParser

from me.yanghu.log.Logger import createLogger
from me.yanghu.log.Logger import setLogFilePath
from me.yanghu.util.Mp4Merger import Mp4Merger

# set the global log file name
# TODO may need to find a better way to set this
setLogFilePath('cntv.log')
logger = createLogger(__name__)

# create a subclass and override the handler methods
class FlvcdHTMLParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag != 'input' :
            return
        
        attrsDict = dict() 
        for key, value in attrs:
            attrsDict[key] = value
        
        if 'name' not in attrsDict or 'value' not in attrsDict:
            return
        
        if attrsDict['name'] == 'inf':
            value = attrsDict['value']
            if r'<$>' in value :
                return
            
            self.urls = attrsDict['value'].splitlines()
        elif attrsDict['name'] == 'filename':
            self.title = attrsDict['value']
        else:
            return
        
    def getTitle(self):
        return self.title
    def getUrls(self):
        return self.urls

'''
http://kejiao.cntv.cn/bjjt/classpage/video/20120824/100886.shtml
http://www.flvcd.com/parse.php?kw=http%3A%2F%2Fkejiao.cntv.cn%2Fbjjt%2Fclasspage%2Fvideo%2F20120824%2F100886.shtml&format=high&flag=one
'''

def getCNTVDownloadLinksWithTitle(cntvUrl):
    cntvUrlEncoded = urllib.parse.quote(cntvUrl, safe='');
    flvcdPrefix = 'http://www.flvcd.com/parse.php?kw='
    flvcdSuffix = '&format=high&flag=one'
    
    flvcdQuery = flvcdPrefix + cntvUrlEncoded + flvcdSuffix

    with urlopen(flvcdQuery) as webFile:
        text = webFile.read().decode ('gb2312');

    flvcdParser = FlvcdHTMLParser()
    flvcdParser.feed(text);
    
    return {'Title' : flvcdParser.getTitle(), 'Urls' : flvcdParser.getUrls()}

def wgetDownload(download_url, filename):
    wget_opts = 'wget ' + download_url + ' -O "' + filename + '" -q'
    if os.path.exists(filename):
        wget_opts += ' -c'
    # When shell is true, we should not use list
    exit_code = subprocess.call(wget_opts, shell=True)
    if exit_code != 0:
        raise Exception(filename + ' : wget exited abnormaly')

def downloadUrlToFile(url, saveFilePath):
    logger.info('Saving ' + url + ' to ' + saveFilePath)
    wgetDownload(url, saveFilePath)
    logger.info('Done ' + saveFilePath)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else: raise

def executeMp4Merge(mp4Merger):
    mp4Merger.merge(True) # delete the source files on success

def main():
    # Get arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-urls-path', help='urls as txt file location')
    parser.add_argument('-o', '--output-folder', help='output folder')
    args = parser.parse_args()
    
    inputFilePath = args.input_urls_path
    outputFolderPath = args.output_folder
    
    with open(inputFilePath) as file:
        content = file.readlines()
    
    # Download cntv mp4s with the urls and titles as the folder name
    # for each cntv url ( one video ) 
    for cntvUrl in content :
        logger.info( 'Getting ' + cntvUrl)
        titleToUrls = getCNTVDownloadLinksWithTitle(cntvUrl);
        
        saveFileDirPath = outputFolderPath + '/' + titleToUrls['Title']
        mkdir_p(saveFileDirPath)
        
        future_to_url = dict()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            for mp4url in titleToUrls['Urls']:
                mp4urlPath = urllib.parse.urlparse(mp4url)[2] # 2 is the index for path
                fileName = saveFileDirPath + mp4urlPath[mp4urlPath.rindex(r'/'):] # find the file name
                future_to_url[executor.submit(downloadUrlToFile, mp4url, fileName)] = mp4url
            
            bShouldMerge = True
            
            # check if there is no exception
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                if future.exception() is not None:
                    logger.warning('%r generated an exception: %s' % (url, future.exception()))
                    bShouldMerge = False
            
            # merge the mp4 file
            if (bShouldMerge):
                mp4Merger = Mp4Merger(saveFileDirPath, titleToUrls['Title'] + '.mp4')
                executor.submit(executeMp4Merge, mp4Merger)
            
# Main method
if __name__ == '__main__':
    main()
