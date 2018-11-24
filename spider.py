#-*- coding:utf-8 -*-
from multiprocessing import Pool
from requests.exceptions import RequestException,Timeout,HTTPError,ConnectionError,TooManyRedirects
import requests
import json
from urllib.parse import urlencode
from hashlib import md5
import os
from bs4 import BeautifulSoup as bs
import time
import pymongo
import datetime
import re
from lxml import etree

# MongoDB数据库连接
MONGO_URL   = 'localhost'
MONGO_DB    = 'toutiao'
MONGO_TABLE = 'toutiao2'
client      = pymongo.MongoClient(MONGO_URL)
db          = client[MONGO_DB]

# 获取索引页的json
def get_page_index(offset,keyword):
    
    try:
        # 创建json格式的data
        data = {
            'offset': offset,
            'format': 'json',
            'keyword': keyword,
            'autoload': 'true',
            'count': 20,
            'cur_tab': 3,
            'from': 'gallery',
        }
        
        # 构造请求URL
        url = 'https://www.toutiao.com/search_content/?' + urlencode(data) # 将data字典对象转换成请求参数

        # 获取URL的requests返回结果，设置超时时间为10s，并添加headers头
        response = requests.get(url,timeout=10,headers=headers)
        # 如果返回的状态码为200，则返回页面text内容
        if response.status_code == 200:
            print('连接成功……')
            return response.text
        # 否则返回状态码   
        return response.status_code
    except Exception as e:
        print('获取索引页时，遇到妖孽 >>> ',e)
        return


def parse_page_index(html):
    # 将html参数转化成json格式的键值对，并赋值与js
    js = json.loads(html)
    # print(js.get('data'))  # 测试用，感兴趣的小伙伴可以打印试一下，看一下返回的内容
    # print(js.keys())  # 测试用，感兴趣的小伙伴可以打印试一下，看一下返回的内容
    # 由于js得到的是一个生成器对象，需要使用yield迭代获得详情页的URL
    for item in js.get('data'):
        yield item.get('article_url')
        # 设置 sleep 等待时间为1秒
        time.sleep(1)

def get_page_detail(url):
    response = requests.get(url,timeout=10,headers=headers)
    if response.status_code == 200:
        return response.text
        # return response.content
    else:
        return response.status_code
        get_page_detail(url)    

def parse_page_detail(html,url):

    try:
        # 使用BeautifulSoup获取目标元素
        soup = bs(html,'lxml')
        # 获取title
        # 注意：因为soup.select('tittle')返回的是list列表，需要使用 [] 取出之后，使用 get_text() 获取字符
        title = soup.select('title')[0].get_text()

        # 为图片设定保存的文件路径
        root_dir = os.getcwd()
        # 其中title为每组图片的标题
        download_dir = '{0}/{1}'.format(root_dir,title)
        # 每个详情页，创建一个文件夹
        os.makedirs(download_dir)

        # 注意：此处在使用正则表达式时，需要对正则表达式 [] 的使用有一定了解
        image_pattern = re.compile(r'gallery: JSON.parse[(]"(.*?)"[)],\n',re.S)
        result = re.search(image_pattern,html)
        if result:
            # 使用 replace 将URL中的 \\ 清除掉
            image_data = result.group(1).replace('\\','')
            # return image_data  # 测试用，感兴趣可以打印出来看一下返回结果
            data = json.loads(image_data)
            # return data.keys()  # 测试用，感兴趣可以打印出来看一下返回结果
            if data and 'sub_images' in data.keys():
                sub_images = data.get('sub_images')
                images_url = [item.get('url') for item in sub_images]
                # print(images_url)  # 测试用，感兴趣可以打印出来看一下返回结果
                # 下载图片
                for image in images_url:
                    # return images_url  # 测试用，感兴趣可以打印出来看一下返回结果
                    download_image(download_dir,image)     
                    time.sleep(1)     
                return {
                    'title':title,
                    'url':url,
                    'images':images_url
                    }

    except Exception as e:
        print('解析详情页时，遇到妖孽 >>> ',e)

# 定义下载程序
def download_image(save_dir,url):
    print('正在下载：',url)
    response = requests.get(url,headers=headers)
    if response.status_code == 200:
        # 因为要下载的是图片，所以需要传入的内容是 response.content
        save_images(save_dir,response.content)
    return None

def save_images(save_dir,content):
    # 使用 md5(content).hexdigest() 为图片创建名称
    file_path = '{0}/{1}.{2}'.format(save_dir,md5(content).hexdigest(),'jpg')
    if not os.path.exists(file_path):
        print('file_path:',file_path)
        with open(file_path,'wb') as f:
            f.write(content)
            print('下载完成！')
            f.close()

# 保存数据至MongoDB模块
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDB成功')

def main(offset):
    # 获取索引页
    html = get_page_index(offset,KEYWORD)
    # parse_page_index(html)
    # 从索引页获取URL的list
    for url in parse_page_index(html):
        # print(url)  # 测试用，感兴趣可以打印出来看一下返回结果
        # 获取详情页
        html = get_page_detail(url)
        # print(html)  # 测试用，感兴趣可以打印出来看一下返回结果
        # 解析索引页，获取详情页图片URL
        if html:
            # parse_page_detail(html,url)
            result = parse_page_detail(html,url)
            # print(result)  # 测试用，感兴趣可以打印出来看一下返回结果
            if result:
                save_to_mongo(result)

if __name__ == '__main__':

    # 获取开始时间
    start_time = datetime.datetime.now()

    KEYWORD = input('请输入要查找的关键字 >>> ')

    # 设置headers
    headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3602.2 Mobile Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'Keep-Alive',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'     
        }
        
    # 设定json格式的data中offset的开始和结束的值
    GROUP_START = 1
    GROUP_END   = 1 
    groups = [x*20 for x in range(GROUP_START,GROUP_END+1)]
    
    # 运行主程序，并将offset值作为参数传入
    # 创建进程池，设置最大进程数为20个
    pool = Pool(20)
    # 在进程池中运行程序
    pool.map(main,groups)
    
    # main(groups)
    
    # 获取结束时间
    end_time = datetime.datetime.now()

    print('*'*100)
    print('开始时间：',start_time)
    print('结束时间：',end_time)
    print('共计用时：',end_time - start_time)
    # 得到数据总数
    total_nums = db[MONGO_TABLE].count()
    print('共计获取数据：',total_nums,' 条')
    print('*'*100)
