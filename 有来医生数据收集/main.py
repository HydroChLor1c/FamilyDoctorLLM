import requests
import time
import random
import json
import os
from rich import print
from rich.progress import Progress
from lxml import etree

from configs import COOKIES, HEADERS

class Youlai:
    def __init__(self, page=1) -> None:
        # 初始化时设定的基本URL和页面数量
        self.base_url = 'https://www.youlai.cn'
        self.page = page
        # 用于存储解析失败或被跳过的页面的列表
        self.skipped_pages = []

    def __get_page(self, url, retries=3, timeout=10) -> requests.Response:
        # 为给定URL发送GET请求，并设定重试次数
        for _ in range(retries):
            try:
                __response = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=timeout)
                if __response.status_code == 200:
                    return __response
                else:
                    # 如果请求失败，则等待一段随机时间并重试
                    print(f'[bold red]请求失败，状态码：{__response.status_code}，正在重试...[/bold red]')
                    time.sleep(random.uniform(1, 3))  # 随机等待1到3秒再重试
            except requests.exceptions.RequestException as e:
                # 处理请求异常，等待一段时间后重试
                print(f'[bold red]请求异常，正在重试... 错误信息：{e}[/bold red]')
                time.sleep(random.uniform(1, 3))  # 随机等待1到3秒再重试

        # 达到最大重试次数后，返回None
        print(f'[bold red]请求 {url} 失败，已达最大重试次数[/bold red]')
        return None

    def __parse_page(self, response) -> list:
        # 解析返回的HTML页面并提取其中的详情页URL
        html = etree.HTML(response.text)
        qa_doc_ok = html.xpath('/html/body/div[2]/div[1]/div[3]')
        qa_detail_urls = []

        # 从查询到的元素中提取详情URL
        for qa_docs in qa_doc_ok[0]:
            p_content = qa_docs.xpath('div[@class="doc_list_r"]/p[@class="doc_list_r_a"]/a/@href')
            qa_detail_urls.append(p_content[0])
        
        return qa_detail_urls

    def __parse_detail_page(self, response) -> dict:
        # 解析详情页面，从中提取有关的信息（如标题和内容）
        html = etree.HTML(response.text)
        article_title = html.xpath("/html/body/div[2]/div[1]/dl/dt/h3/text()")
        article_content = html.xpath("/html/body/div[2]/div[1]/div[1]/div[2]/p/text()")

        # 返回一个包含文章标题和内容的字典
        return {
            'instruction': article_title[0],
            'output': article_content[0]
        }

    def save_data_to_json(self, data):
        json_file_path = 'data/test.json'
        
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as jsonfile:
                existing_data = json.load(jsonfile)
        else:
            existing_data = []

        # 将新数据合并到现有数据中（只添加不重复的数据项）
        new_data_count = 0  # 用于计数新增数据项的数量
        for item in data:
            if item not in existing_data:
                existing_data.append(item)
                new_data_count += 1
            else:
                print(f'[bold yellow]数据重复，不添加：{item}[/bold yellow]')  # 打印提示信息

        # 如果新数据项的数量大于0，则显示新增数据的数量
        if new_data_count:
            print(f'[bold green]新增 {new_data_count} 项数据到test.json[/bold green]')

        with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(existing_data, jsonfile, ensure_ascii=False, indent=4)

    def run(self):
        # 确保数据文件夹存在，如果不存在则创建一个
        if not os.path.exists('data'):
            os.mkdir('data')

        # 初始化上次爬取的页面为1，如果存在 last_page.txt 则从中读取上次的页面数
        last_page = 1
        if os.path.exists('last_page.txt'):
            with open('last_page.txt', 'r') as f:
                last_page = int(f.read().strip())

        # 设置要爬取的总页面数
        total_pages = self.page

        # 使用 rich 库来创建一个进度条
        with Progress() as progress:
            page_task = progress.add_task("[cyan]正在获取页面...", total=total_pages)

            # 遍历从上次的页面到设定的最后一个页面
            for current_page in range(last_page, self.page + 1):
                try:
                    # 构建要爬取的页面URL
                    url = self.base_url + '/ask/reply_' + str(current_page) + '.html'
                    
                    # 使用私有方法来获取页面数据
                    res = self.__get_page(url)
                    
                    # 如果请求失败，将当前页面添加到跳过的页面列表并继续下一个页面
                    if res is None:
                        self.skipped_pages.append(current_page)
                        continue
                    
                    # 使用私有方法解析获取的页面数据并获取详情页的URLs
                    qa_detail_urls = self.__parse_page(res)

                    qa_detail_data = []
                    # 创建一个进度条用于显示获取详情页面的进度
                    detail_task = progress.add_task("[green]正在获取详情...", total=len(qa_detail_urls))
                    
                    # 遍历每一个详情页的URL并获取内容
                    for detail_url in qa_detail_urls:
                        full_url = self.base_url + detail_url
                        res = self.__get_page(full_url)
                        if res is None:
                            continue
                        data = self.__parse_detail_page(res)
                        qa_detail_data.append(data)
                        
                        # 休眠一段时间以避免频繁请求
                         
                        # 更新详情页面进度条
                        progress.update(detail_task, advance=1)

                    # 保存解析到的数据到JSON文件中
                    self.save_data_to_json(qa_detail_data)

                    # 更新页面进度条
                    progress.update(page_task, completed=current_page)
                     

                except AttributeError:
                    # 当页面解析出现错误时，将其添加到跳过的页面列表中
                    print(f'[bold red]解析页面 {current_page} 出现错误，正在跳过...[/bold red]')
                    self.skipped_pages.append(current_page)
                    current_page += 1  # 跳过当前页面
                
                # 无论是否成功或出错，都更新last_page的值
                with open('last_page.txt', 'w') as f:
                    f.write(str(current_page))

        print('[bold green]获取内容完成并保存至test.json[/bold green]')

        # 如果有跳过的页面，则将这些页面编号保存到 skipped_pages.txt 中
        if self.skipped_pages:
            with open('skipped_pages.txt', 'w') as f:
                for page in self.skipped_pages:
                    f.write(str(page) + '\n')
            print(f"[bold red]跳过了 {len(self.skipped_pages)} 个页面。详情请查看 'skipped_pages.txt'。[/bold red]")

        print('-'*50)    


if __name__ == "__main__":
    print('[bold red]欢迎使用[/bold red][bold green]有来问答数据爬取工具[/bold green]')
    
    y = Youlai(page=19865)

    try:
        y.run()
    except KeyboardInterrupt:
        # 当用户按下 Ctrl+C 时，保存当前的状态
        print('\n[bold yellow]用户中断，正在保存当前状态...[/bold yellow]')
        if y.skipped_pages:
            with open('skipped_pages.txt', 'w') as f:
                for page in y.skipped_pages:
                    f.write(str(page) + '\n')
            print(f"[bold red]跳过了 {len(y.skipped_pages)} 个页面。详情请查看 'skipped_pages.txt'。[/bold red]")

        print('-'*50)

try:
    y.run()
except KeyboardInterrupt:
    print('-'*50)
