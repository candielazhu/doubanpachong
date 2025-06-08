import csv
import random
import time
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from lxml import etree
import os
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import logging
from datetime import datetime

# ====================== 合规声明与常量 ======================
LEGAL_NOTICE = """
注意：本工具仅用于学习研究，严禁恶意爬取或商业用途！
豆瓣电影排行爬取
"""

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 代理IP示例（请替换为有效代理或留空）
proxy_list = [
    # 'http://117.69.237.77:8089',
    # 'http://101.37.19.35:80'
    # 'http://221.194.147.197:80'
    # 'http://159.226.227.117:80'
    # 'http://101.37.26.136:80'
    # 'http://202.101.213.33:17406'
    # 'http://120.25.1.15:7890'
]

#====================== 代理验证函数 ======================
def test_proxy(proxy):
    """测试代理IP是否有效"""
    try:
        proxies = {"http": proxy, "https": proxy}
        response = requests.get("https://www.baidu.com", proxies=proxies, timeout=10)
        time.sleep(random.uniform(1, 3))
        if response.status_code == 200:
            print(f"代理 {proxy} 有效")
            return True
        else:
            print(f"代理 {proxy} 无效，状态码：{response.status_code}")
            return False
    except Exception as e:
        print(f"代理 {proxy} 连接失败：{e}")
        return False

# 验证代理列表
valid_proxies = [proxy for proxy in proxy_list if test_proxy(proxy)]
proxy_list = valid_proxies

def get_safe_save_dir():
    """获取安全保存目录"""
    return os.path.abspath(os.path.dirname(__file__))

# ====================== 通用工具函数 ======================
def get_current_dir():
    """获取当前工作目录"""
    return os.path.abspath(os.path.dirname(__file__))

def save_to_csv(data, filename, fieldnames):
    """安全保存数据到当前目录的CSV文件"""
    save_dir = get_safe_save_dir()
    file_path = os.path.join(save_dir, filename)
    # 过滤 data 字典，只保留 fieldnames 中包含的字段
    filtered_data = {key: value for key, value in data.items() if key in fieldnames}
    try:
        if not os.path.exists(file_path):
            with open(file_path, "w", newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
        # 追加模式写入数据
        with open(file_path, "a", newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(filtered_data)
            logging.info(f"成功写入数据到新文件: {file_path}")
    except Exception as e:
        logging.error(f"写入 CSV 文件失败: {str(e)}")

# ====================== 电影爬取模块 ======================
def crawl_movie(rank_type="top250", page=1):
    """爬取豆瓣电影排行榜"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 新增时间戳
    filename = f"豆瓣电影排行_{rank_type}_{timestamp}.csv"  # 修改文件名格式
    fieldnames = ['id', 'title', 'rating', 'director', 'actors', 'year', 'genre', 'country']

    url = f"https://movie.douban.com/top250?start={(page - 1) * 25}"
    headers = get_random_headers()
    # 增加重试机制，提高请求稳定性
    logging.info(f"开始爬取豆瓣电影第 {page} 页，URL: {url}")
    response = make_request_with_retries(url, headers)
    if not response:
        logging.error(f"请求豆瓣电影第 {page} 页失败")
        yield f"请求豆瓣电影第 {page} 页失败", None
        return
    
    logging.info(f"成功获取豆瓣电影第 {page} 页响应，响应状态码: {response.status_code}")
    logging.info(f"响应内容长度: {len(response.text)}")
    
    root = etree.HTML(response.text)
    movies = root.xpath('//div[@class="item"]')
    logging.info(f"找到 {len(movies)} 个电影节点")

    # 增加请求间隔
    time.sleep(random.uniform(2, 5))

    root = etree.HTML(response.text)
    movies = root.xpath('//div[@class="item"]')
    movie_count = 0

    for movie in movies:
        try:
            # 检查 XPath 表达式是否正确
            title = movie.xpath('.//span[@class="title"]/text()')
            if not title:
                logging.warning(f"未找到电影标题，可能页面结构变化，当前电影节点: {etree.tostring(movie, encoding='unicode')}")
                continue
            title = title[0]

            rating = movie.xpath('.//span[@class="rating_num"]/text()')
            if not rating:
                logging.warning(f"未找到电影评分，可能页面结构变化，当前电影节点: {etree.tostring(movie, encoding='unicode')}")
                continue
            rating = rating[0]

            info = movie.xpath('.//div[@class="bd"]/p[1]/text()')
            if not info:
                logging.warning(f"未找到电影信息，可能页面结构变化，当前电影节点: {etree.tostring(movie, encoding='unicode')}")
                continue
            info = ''.join(info).strip()

            # 解析导演、演员、年份、类型、国家
            director, actors = parse_director_and_actors(info)
            year, genre, country = parse_year_genre_country(info)

            data = {
                'title': title,
                'rating': rating,
                'director': director,
                'actors': actors,
                'year': year,
                'genre': genre,
                'country': country
            }
            # 保存数据到CSV文件，暂不保存id
            save_to_csv(data, filename, fieldnames[1:])
            movie_count += 1
            # 返回已获取电影的信息
            yield f"已获取电影：{title}", None
        except Exception as e:
            logging.error(f"解析电影时出错：{str(e)}，当前电影节点: {etree.tostring(movie, encoding='unicode')}")
            yield f"解析电影时出错：{str(e)}", None

    if movie_count == 0:
        logging.error("未成功获取到任何电影数据，可能爬取失败。")
        print("未成功获取到任何电影数据，可能爬取失败。")

    # 数据后处理
    save_dir = get_safe_save_dir()
    file_path = os.path.join(save_dir, filename)
    if os.path.exists(file_path):
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            # 去除重复数据
            df = df.drop_duplicates()

            # 转换评分列为数值类型
            df['rating'] = pd.to_numeric(df['rating'], errors='coerce')
            # 按评分降序排序
            df = df.sort_values(by='rating', ascending=False)
            # 重置索引保证顺序
            df = df.reset_index(drop=True)

            # 插入id列
            df.insert(0, "id", [f"movie{i:04d}" for i in range(1, len(df) + 1)])
            # 将处理后的数据保存到CSV文件
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            logging.info("电影数据处理完成")
            # 返回电影数据爬取完成的信息和文件名
            yield "电影数据爬取完成！", filename
        except Exception as e:
            logging.error(f"电影数据处理失败：{str(e)}")
            yield f"电影数据处理失败：{str(e)}", None
    else:
        logging.error(f"电影数据文件 {filename} 不存在，无法处理")
        yield f"电影数据文件 {filename} 不存在，无法处理", None

def make_request_with_retries(url, headers, max_retries=3):
    """
    带重试机制的请求函数
    :param url: 请求的URL
    :param headers: 请求头
    :param max_retries: 最大重试次数，默认为3
    :return: 响应对象，若请求失败则返回None
    """
    retries = 0
    while retries < max_retries:        # 循环尝试请求，直到达到最大重试次数
        try:
            #使用随机代理
            proxies = {"http": random.choice(proxy_list), "https": random.choice(proxy_list)} if proxy_list else {} 
            #增加代理和超时时间
            response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            #检查响应状态码是否正常
            response.raise_for_status()  

            return response
        except requests.exceptions.RequestException as e:
            print(f"请求失败（第 {retries + 1} 次尝试）：{str(e)}")
            retries += 1
    print("达到最大重试次数，请求失败。")
    return None

def get_text_from_xpath(element, xpath):
    """
    从xpath获取文本，若为空则返回空字符串
    :param element: 要查找的元素
    :param xpath: xpath表达式
    :return: 查找到的文本，若为空则返回空字符串
    """
    result = element.xpath(xpath)        # 获取元素的文本
    return result[0].text.strip() if result else ''     # 去除首尾空格，返回结果或空字符串

def parse_director_and_actors(info):
    """
    解析导演和演员信息
    :param info: 电影信息字符串
    :return: 导演和演员信息
    """
    parts = info.split('\n')[0].split(':')[1].strip().split(' ')
    director = parts[0]
    actors = '|'.join(parts[1:])
    return director, actors

def parse_year_genre_country(info):
    """
    解析年份、类型和国家信息
    :param info: 电影信息字符串
    :return: 年份、类型和国家信息
    """
    year_genre = info.split('\n')[1].strip().split('/')
    year = year_genre[0].strip()
    genre = '/'.join(year_genre[1:-1]).strip()
    country = year_genre[-1].strip()
    return year, genre, country

# ====================== 通用支持函数 ======================
def get_random_headers():
    """
    生成随机请求头
    :return: 包含随机User-Agent和Accept-Language的请求头字典
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }

def safe_request(url, headers,max_retries=3):
    """
    安全请求（带代理和异常处理）
    :param url: 请求的URL
    :param headers: 请求头
    :param max_retries: 最大重试次数，默认为3
    :return: 响应对象，若请求失败则返回None
    """
    retries = 0
    while retries < max_retries:    # 循环尝试请求，直到达到最大重试次数
        try:
            proxies = {"http": random.choice(proxy_list), "https": random.choice(proxy_list)} if proxy_list else {}
            response = requests.get(url, headers=headers, proxies=proxies, timeout=20)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"请求失败（第 {retries + 1} 次尝试）：{str(e)}")
            retries += 1
    print("达到最大重试次数，请求失败。")
    response.encoding = 'utf-8'
    return None

# ====================== 数据分析与可视化模块 ======================
def analyze_and_generate_report(csv_file):
    """
    分析电影数据并生成可视化报告
    :param csv_file: 要分析的CSV文件路径
    :return: 分析是否成功的布尔值和报告文件路径或错误信息
    """
    try:
        
        # ======== 添加中文字体支持 ========
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体作为中文字体
        plt.rcParams['axes.unicode_minus'] = False    # 解决负号显示问题

        # 读取数据
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        
        # 数据清洗
        df = clean_movie_data(df)
        
        # 创建PDF报告
        report_file = csv_file.replace('.csv', '_report.pdf')
        with PdfPages(report_file) as pdf:
            # 添加报告标题
            plt.figure(figsize=(11, 8))
            plt.suptitle('豆瓣电影数据分析报告', fontsize=20, fontweight='bold')
            plt.figtext(0.5, 0.5, f"数据来源: {csv_file}\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                        ha='center', va='center', fontsize=16)
            pdf.savefig()
            plt.close()
            
            # 1. 评分分布直方图
            plot_rating_distribution(df, pdf)
            
            # 2. 年份分布分析
            plot_year_distribution(df, pdf)
            
            # 3. 国家分布分析
            plot_country_distribution(df, pdf)
            
            # 4. 类型分布分析
            plot_genre_distribution(df, pdf)
            
            # 5. 导演作品分析
            plot_director_analysis(df, pdf)
            
            # 6. 评分TOP10电影
            plot_top10_movies(df, pdf)
            
            # 7. 数据概览表格
            plot_data_overview(df, pdf)
        
        return True, report_file
    except Exception as e:
        logging.error(f"生成报告失败: {str(e)}")
        return False, str(e)

def clean_movie_data(df):
    """
    清洗电影数据
    :param df: 电影数据DataFrame
    :return: 清洗后的DataFrame
    """
    # 处理年份异常值
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    #过滤无效年份
    df = df[df['year'] > 1900]
    
    # 拆分电影类型（一部电影可能有多个类型）
    df['genre'] = df['genre'].str.split('/')
    
    # 拆分国家（一部电影可能有多个制片国家）
    df['country'] = df['country'].str.split('/')
    
    return df

def plot_rating_distribution(df, pdf):
    """
    绘制评分分布直方图
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['rating'], bins=20, color='skyblue', edgecolor='black', alpha=0.7)
    plt.title('电影评分分布', fontsize=16)
    plt.xlabel('评分', fontsize=12)
    plt.ylabel('电影数量', fontsize=12)
    plt.grid(axis='y', alpha=0.5)
    plt.tight_layout()
    pdf.savefig()
    plt.close()

def plot_year_distribution(df, pdf):
    """
    绘制年份分布分析
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    # 按年代分组
    df['decade'] = (df['year'] // 10) * 10
    decade_counts = df['decade'].value_counts().sort_index()
    
    plt.figure(figsize=(10, 6))
    decade_counts.plot(kind='bar', color='salmon', alpha=0.7)
    plt.title('电影年代分布', fontsize=16)
    plt.xlabel('年代', fontsize=12)
    plt.ylabel('电影数量', fontsize=12)
    plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.5)
    plt.tight_layout()
    pdf.savefig()
    plt.close()

def plot_country_distribution(df, pdf):
    """
    绘制国家分布分析
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    # 展开多个制片国家
    countries = df['country'].explode()
    country_counts = countries.value_counts().head(10)  # 取前10个国家
    
    plt.figure(figsize=(10, 6))
    country_counts.plot(kind='barh', color='lightgreen', alpha=0.7)
    plt.title('电影类型分布 (Top 10)', fontsize=16)
    plt.xlabel('电影数量', fontsize=12)
    plt.ylabel('电影类型', fontsize=12)
    plt.grid(axis='x', alpha=0.5)
    plt.tight_layout()
    pdf.savefig()
    plt.close()
    
def plot_genre_distribution(df, pdf):
    """
    绘制类型分布分析
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    # 展开多个类型
    genres = df['genre'].explode()
    genre_counts = genres.value_counts().head(10)  # 取前10个类型
    
    plt.figure(figsize=(10, 6))
    genre_counts.plot(kind='bar', color='gold', alpha=0.7)
    plt.title('制片国家分布 (Top 10)', fontsize=16)
    plt.xlabel('国家', fontsize=12)
    plt.ylabel('电影数量', fontsize=12)
    plt.xticks(rotation=45)
    plt.grid(axis='y', alpha=0.5)
    plt.tight_layout()
    pdf.savefig()
    plt.close()

def plot_director_analysis(df, pdf):
    """
    导演作品分析
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    # 统计导演作品数量和平均评分
    director_stats = df.groupby('director').agg(
        movie_count=('title', 'count'),
        avg_rating=('rating', 'mean')
    ).sort_values('movie_count', ascending=False).head(10)  # 取作品数量前10的导演
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 绘制作品数量柱状图
    ax1.bar(director_stats.index, director_stats['movie_count'], color='royalblue', alpha=0.7)
    ax1.set_xlabel('导演', fontsize=12)
    ax1.set_ylabel('作品数量', color='royalblue', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='royalblue')
    plt.xticks(rotation=45)
    
    # 创建第二个Y轴用于平均评分
    ax2 = ax1.twinx()
    ax2.plot(director_stats.index, director_stats['avg_rating'], color='red', marker='o', linewidth=2)
    ax2.set_ylabel('平均评分', color='red', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='red')
    
    plt.title('导演作品数量与评分分析 (Top 10)', fontsize=16)
    plt.grid(axis='y', alpha=0.5)
    plt.tight_layout()
    pdf.savefig()
    plt.close()

def plot_top10_movies(df, pdf):
    """
    绘制评分TOP10电影
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    top10 = df.nlargest(10, 'rating')
    
    plt.figure(figsize=(10, 6))
    plt.barh(top10['title'], top10['rating'], color='violet', alpha=0.7)
    plt.title('评分最高TOP10电影', fontsize=16)
    plt.xlabel('评分', fontsize=12)
    plt.ylabel('电影名称', fontsize=12)
    
    # 为每个条形添加评分值
    for i, rating in enumerate(top10['rating']):
        plt.text(rating + 0.05, i, f'{rating:.1f}', va='center')
    
    plt.gca().invert_yaxis()  # 反转Y轴使最高评分在顶部
    plt.grid(axis='x', alpha=0.5)
    plt.tight_layout()
    pdf.savefig()
    plt.close()

def plot_data_overview(df, pdf):
    """
    绘制数据概览表格
    :param df: 电影数据DataFrame
    :param pdf: PDF报告对象
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')  # 隐藏坐标轴
    
# 创建表格数据
    table_data = [
        ["数据集统计", "值"],
        ["电影总数", len(df)],
        ["平均评分", f"{df['rating'].mean():.2f}"],
        ["最高评分", df['rating'].max()],
        ["最低评分", df['rating'].min()],
        ["最早年份", int(df['year'].min())],
        ["最晚年份", int(df['year'].max())],
        ["涉及国家数", df['country'].explode().nunique()],
        ["涉及类型数", df['genre'].explode().nunique()],
        ["涉及导演数", df['director'].nunique()]
    ]

    # 创建表格
    table = plt.table(
        cellText=table_data,
        loc='center',
        cellLoc='center',
        colWidths=[0.3, 0.3]
    )

    # 设置表格样式
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.5)  # 调整表格大小

    # 设置标题行样式
    for i in range(2):
        table[(0, i)].set_facecolor('#40466e')
        table[(0, i)].set_text_props(color='white', weight='bold')

    plt.title('数据概览', fontsize=16)
    plt.tight_layout()
    pdf.savefig()
    plt.close()

# ====================== GUI界面 ======================
class CrawlerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("豆瓣电影爬取工具")
        self.geometry("600x450")

        # 创建主框架
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 合规声明
        tk.Label(self, text=LEGAL_NOTICE, fg="red", justify=tk.LEFT, padx=10, pady=10).pack()

        # 输入框架
        input_frame = ttk.Frame(self)
        input_frame.pack(pady=15, padx=20, fill=tk.X)

        # 电影爬取输入
        self.movie_page = ttk.Frame(input_frame, style='TFrame')
        self.movie_page.pack(side=tk.LEFT, padx=10, anchor=tk.W)
        
        ttk.Label(self.movie_page, text="页码（1-10）：").pack(side=tk.LEFT, padx=5)
        self.movie_entry = ttk.Entry(self.movie_page, width=5)
        self.movie_entry.pack(side=tk.LEFT, padx=2)
        self.movie_entry.insert(0, "1")  # 设置默认页码

        # 创建样式对象
        style = ttk.Style()
        # 设置 Label 的前景色
        style.configure("Blue.TLabel", foreground="blue")

        # 状态显示
        self.status_text = tk.StringVar()
        ttk.Label(self, textvariable=self.status_text, style="Blue.TLabel", wraplength=550).pack(pady=10, padx=20)
        
        # 代理输入框和验证按钮
        proxy_frame = ttk.Frame(self)
        proxy_frame.pack(pady=10, padx=20, fill=tk.X)
        # 显示代理输入提示
        ttk.Label(proxy_frame, text="手动输入代理（格式：http://IP:端口）：").pack(side=tk.LEFT, padx=5)
        # 创建代理输入框
        self.proxy_entry = ttk.Entry(proxy_frame, width=20)
        # 设置默认代理地址
        self.proxy_entry.insert(0, "http://120.25.1.15:7890")  # 设置默认代理地址
        self.proxy_entry.pack(side=tk.LEFT, padx=5)
        # 创建验证代理按钮
        ttk.Button(proxy_frame, text="验证代理", command=self.validate_proxy).pack(side=tk.LEFT, padx=5)

 
        # 控制按钮框架
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        
        # 爬取控制按钮
        ttk.Button(button_frame, text="开始爬取", command=self.start_crawling).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="退出", command=self.quit).pack(side=tk.LEFT, padx=5)
        
        # 分析报告按钮
        report_frame = ttk.Frame(self)
        report_frame.pack(pady=10)
        
        ttk.Button(report_frame, text="生成分析报告(当前数据)", command=self.generate_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(report_frame, text="选择文件生成报告", command=self.select_and_generate_report).pack(side=tk.LEFT, padx=5)


        
        # 添加状态变量存储当前数据文件路径
        self.current_data_file = None

    def select_and_generate_report(self):
        """打开文件选择对话框并生成报告"""
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialdir=get_safe_save_dir()
        )
        
        if file_path:
            # 更新状态文本
            self.status_text.set(f"已选择文件: {file_path}")
            # 存储当前数据文件路径
            self.current_data_file = file_path
            # 生成报告
            self.generate_report()
        else:
            self.status_text.set("文件选择已取消")
        
    def run_task(self, generator):
        """
        异步执行爬取任务
        :param generator: 爬取任务生成器
        """
        try:
            # 获取爬取状态和文件名
            status, filename = next(generator)
            # 更新状态文本
            self.status_text.set(status)
            
            # 存储当前数据文件路径
            if filename:
                self.current_data_file = os.path.join(get_safe_save_dir(), filename)
            
            # 100毫秒后继续执行任务
            self.after(100, lambda: self.continue_task(generator, filename))
        except StopIteration:
            # 更新状态文本
            self.status_text.set("爬取任务完成！")
            if self.current_data_file:
                # 显示完成提示信息
                messagebox.showinfo("完成", f"数据已保存到：\n{self.current_data_file}")

    def generate_report(self):
        """生成数据分析报告"""
        if not self.current_data_file:
            messagebox.showwarning("警告", "请先爬取数据再生成报告")
            return
        
        # 检查文件是否存在
        if not os.path.exists(self.current_data_file):
            messagebox.showerror("错误", f"文件不存在: {self.current_data_file}")
            return
        
        self.status_text.set(f"正在分析文件: {os.path.basename(self.current_data_file)}")
        # 异步生成报告防止界面卡死
        self.after(100, self._async_generate_report)

    def _async_generate_report(self):
        """异步执行报告生成"""
        try:
            # 生成报告
            success, result = analyze_and_generate_report(self.current_data_file)
            if success:
                self.status_text.set("报告生成成功！")
                messagebox.showinfo("成功", f"分析报告已保存到：\n{result}")
            else:
                self.status_text.set("报告生成失败")
                messagebox.showerror("错误", f"生成报告失败: {result}")
        except Exception as e:
            self.status_text.set(f"报告生成错误: {str(e)}")
            messagebox.showerror("错误", f"生成报告时出错: {str(e)}")

    def validate_proxy(self):
        # 获取输入的代理地址
        proxy = self.proxy_entry.get().strip()
        if not proxy:
            messagebox.showwarning("警告", "请输入代理地址。")
            return
        try:
            # 设置代理
            proxies = {"http": proxy, "https": proxy}
            # 发送请求到百度，设置超时时间为10秒
            response = requests.get("https://www.baidu.com", proxies=proxies, timeout=10)
            if response.status_code == 200:
                # 显示代理可用的提示信息
                messagebox.showinfo("验证成功", f"代理 {proxy} 可用。")
                global proxy_list
                # 更新代理列表
                proxy_list = [proxy]
            else:
                messagebox.showerror("验证失败", f"代理 {proxy} 不可用，状态码：{response.status_code}")
        except Exception as e:
            messagebox.showerror("验证失败", f"代理 {proxy} 连接失败：{str(e)}")

    def start_crawling(self):
        """启动爬取任务"""
        self.status_text.set("正在准备爬取豆瓣电影...")
        try:
            page = int(self.movie_entry.get())
            if not (1 <= page <= 10):
                raise ValueError("电影页码需在1-10之间")
            # 异步执行爬取任务
            self.run_task(crawl_movie(page=page))
        except Exception as e:
            messagebox.showerror("输入错误", f"请检查输入：{str(e)}")

    def continue_task(self, generator, last_filename):
        """继续执行生成器任务"""
        try:
            status, filename = next(generator)
            self.status_text.set(f"{status}\n文件路径：{filename}")
            self.after(100, lambda: self.continue_task(generator, filename))
        except StopIteration:
            self.status_text.set("爬取任务完成！")
            # 检查 last_filename 是否有值
            if last_filename:
                # 获取保存目录
                save_dir = get_safe_save_dir()
                # 拼接文件路径
                file_path = os.path.join(save_dir, last_filename)
                messagebox.showinfo("完成", f"数据已保存到：\n{file_path}")

# ====================== 主程序 ======================
if __name__ == "__main__":
    # 初始化界面
    root = CrawlerGUI()
    root.mainloop()
