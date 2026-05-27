#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日新闻爬虫脚本
职责：1. 爬取新闻标题+正文 2. 提取摘要与细节 3. 生成深度总结 4. 渲染HTML
模板文件（永不修改）：template_main.html / template_detail.html
输出文件（每次覆盖）：daily-news.html / news-detail.html
"""

import requests
from datetime import datetime
from bs4 import BeautifulSoup
import json
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

NEWS_SOURCES = {
    'politics': [
        {'name': '新华网', 'url': 'https://www.xinhuanet.com/politics/', 'type': 'html'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%E4%B8%AD%E5%9B%BD%E6%94%BF%E6%B2%BB&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'economy': [
        {'name': '新浪财经', 'url': 'https://finance.sina.com.cn/', 'type': 'html'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%E7%BB%8F%E6%B5%8E%E9%87%91%E8%9E%8D&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'tech': [
        {'name': '36氪', 'url': 'https://36kr.com/', 'type': 'html'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%E7%A7%91%E6%8A%80AI&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'military': [
        {'name': '环球军事', 'url': 'https://mil.huanqiu.com/', 'type': 'html'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%E5%86%9B%E4%BA%8B%E5%9B%BD%E9%98%B2&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'humanities': [
        {'name': '澎湃新闻', 'url': 'https://www.thepaper.cn/', 'type': 'html'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%E6%96%87%E5%8C%96%E6%95%99%E8%82%B2%E6%B0%91%E7%94%9F&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ]
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

CATEGORY_NAMES = {
    'politics': '政治', 'economy': '经济', 'tech': '科技',
    'military': '军事', 'humanities': '人文',
}

DETAIL_LABELS = {
    'tech':       ['核心进展', '核心数据', '技术突破', '市场影响'],
    'economy':    ['核心数据', '市场反应', '政策动态', '行业影响'],
    'politics':   ['政策要点', '重要成果', '国际反应', '趋势研判'],
    'military':   ['战略动向', '装备进展', '地缘态势', '安全影响'],
    'humanities': ['文化动态', '社会影响', '民生关切', '发展启示'],
}

LABEL_KEYWORDS = {
    '核心数据':   ['增长', '下降', '%', '亿', '万', '数据', '统计', '指标', '同比', '环比', '达到', '突破', '超过'],
    '市场反应':   ['上涨', '下跌', '股市', '股价', '涨', '跌', '收盘', '开盘', '资金', '净流入', '流出', '涨幅', '跌幅'],
    '核心计划':   ['计划', '规划', '目标', '将', '预计', '方案', '措施', '路线图', '布局', '战略', '部署'],
    '重要成果':   ['达成', '签署', '通过', '发布', '揭牌', '启动', '完成', '突破', '实现', '取得', '荣获'],
    '紧张态势':   ['警告', '争端', '冲突', '紧张', '制裁', '对抗', '威胁', '风险', '指责', '谴责'],
    '重要动作':   ['部署', '动员', '演习', '派遣', '调动', '宣布', '召开', '举行', '开展', '推动'],
    '核心进展':   ['研发', '发布', '上线', '推出', '迭代', '升级', '突破', '创新', '试验', '验证'],
    '核心内容':   ['指出', '强调', '提出', '明确', '认为', '分析', '解读', '阐述', '介绍'],
    '政策要点':   ['政策', '法规', '条例', '通知', '意见', '方案', '措施', '出台', '印发', '实施'],
    '国际反应':   ['回应', '表示', '声明', '表态', '关注', '欢迎', '反对', '支持', '呼吁'],
    '市场影响':   ['市场', '行业', '产业', '板块', '领域', '影响', '带动', '推动', '格局'],
    '技术突破':   ['技术', '算法', '模型', '芯片', '算力', '系统', '平台', '框架', '架构'],
    '战略动向':   ['战略', '军事', '国防', '安全', '演习', '部队', '装备', '武器', '部署'],
    '装备进展':   ['装备', '武器', '舰艇', '战机', '导弹', '雷达', '系统', '交付', '入列'],
    '趋势研判':   ['趋势', '走向', '前景', '预测', '预计', '分析', '判断', '展望', '将'],
    '发展启示':   ['启示', '意义', '价值', '影响', '改变', '推动', '促进', '带动'],
    '民生关切':   ['民生', '教育', '医疗', '住房', '养老', '就业', '收入', '保障'],
    '文化动态':   ['文化', '艺术', '遗产', '保护', '创新', '传承', '展览', '出版'],
    '社会影响':   ['社会', '公众', '舆论', '讨论', '关注', '热议', '聚焦', '引发'],
    '行业影响':   ['行业', '产业', '企业', '公司', '业务', '营收', '利润', '竞争'],
}

SITE_ARTICLE_SELECTORS = {
    '新华网': ['div.detail-content', '#detailContent', 'div.article', 'div.content', 'div#content'],
    '新浪财经': ['div.article-content', 'div.article-content-left', 'div.main-content', 'div.article'],
    '36氪': ['article.article', 'div.articleDetailContent', 'div.article-detail', 'div.common-width'],
    '环球军事': ['div.article-con', 'div.article-content', 'div.text', 'div.content', 'div.article'],
    '澎湃新闻': ['div.index_centent', 'div.news_txt', 'div.news_txt_content', 'div.article_content'],
}


XML_CLEAN_RE = re.compile(r'<[^>]+>')


def fetch_news_from_source(source):
    if source.get('type') == 'rss':
        return _fetch_rss_news(source)
    return _fetch_html_news(source)


def _fetch_html_news(source):
    news_list = []
    try:
        response = requests.get(source['url'], headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)

        for link in links[:100]:
            title = link.get_text(strip=True)
            href = link['href']

            if not title or len(title) < 10 or len(title) > 100:
                continue
            skip_keywords = ['广告', '推广', '专题', '直播', '视频', '图片', '更多', '点击查看', '下一页']
            if any(kw in title for kw in skip_keywords):
                continue

            if href.startswith('/'):
                base_url = '/'.join(source['url'].split('/')[:3])
                href = base_url + href
            elif not href.startswith('http'):
                continue

            news_list.append({
                'title': title,
                'source': source['name'],
                'url': href
            })
            if len(news_list) >= 6:
                break

    except Exception as e:
        print(f"  HTML #{source['name']} 失败: {str(e)[:50]}")

    return news_list


def _fetch_rss_news(source):
    news_list = []
    try:
        resp = requests.get(source['url'], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'xml')
        items = soup.find_all('item')[:20]

        for item in items:
            title_el = item.find('title')
            link_el = item.find('link')
            src_el = item.find('source')

            if not title_el:
                continue
            title = XML_CLEAN_RE.sub('', title_el.text).strip()
            if len(title) < 10 or len(title) > 120:
                continue

            source_name = 'GoogleNews'
            if src_el:
                source_name = XML_CLEAN_RE.sub('', src_el.text).strip()[:20]

            url = link_el.text.strip() if link_el else '#'
            if not url.startswith('http'):
                link_candidates = item.find_all('link')
                for lc in link_candidates:
                    t = lc.text.strip()
                    if t.startswith('http'):
                        url = t
                        break

            news_list.append({
                'title': title,
                'source': source_name,
                'url': '#',
            })
            if len(news_list) >= 6:
                break

        print(f"  RSS #{source['name']}: 获取 {len(news_list)} 条")

    except Exception as e:
        print(f"  RSS #{source['name']} 失败: {str(e)[:50]}")

    return news_list


def extract_article_text(html_text, source_name, url):
    """从不同新闻网站提取文章正文"""
    try:
        soup = BeautifulSoup(html_text, 'html.parser')

        selectors = SITE_ARTICLE_SELECTORS.get(source_name, [])
        for sel in selectors:
            container = soup.select_one(sel)
            if container:
                pars = container.find_all('p')
                if pars:
                    text = '\n'.join(p.get_text(strip=True) for p in pars if p.get_text(strip=True))
                    if len(text) > 100:
                        return text

        pars = soup.find_all('p')
        meaningful = [p.get_text(strip=True) for p in pars if len(p.get_text(strip=True)) > 15]
        if meaningful:
            return '\n'.join(meaningful)

        return ''
    except Exception:
        return ''


def summarize_article(text, max_sentences=3):
    """从正文中提取关键句子作为概述"""
    if not text:
        return ''
    sentences = re.split(r'[。！？；\n]', text)
    result = []
    for s in sentences:
        s = s.strip()
        if len(s) > 15 and not any(s.startswith(kw) for kw in
            ['点击', '查看原文', '阅读原文', '来源', '作者', '记者', '编辑', '责任编辑',
             '扫描', '下载', '关注', '分享', '相关', '推荐', '更多']):
            result.append(s)
        if len(result) >= max_sentences:
            break
    return '。'.join(result) + '。' if result else ''


def extract_detail_points(text, cat):
    """从文章正文中提取有实质内容的细节要点"""
    if not text:
        return [{'label': '新闻概述', 'content': '点击查看原文了解详情。'}]

    sentences = re.split(r'[。！？；\n]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    expected_labels = DETAIL_LABELS.get(cat, ['核心内容', '重要成果'])

    scored = []
    for label in expected_labels:
        keywords = LABEL_KEYWORDS.get(label, [])
        for i, s in enumerate(sentences):
            hits = sum(1 for kw in keywords if kw in s)
            if hits > 0:
                scored.append({'label': label, 'content': s, 'hits': hits, 'index': i})

    scored.sort(key=lambda x: x['hits'], reverse=True)

    seen_labels = set()
    details = []
    for item in scored:
        if item['label'] not in seen_labels:
            seen_labels.add(item['label'])
            details.append({'label': item['label'], 'content': item['content'] + '。'})
        if len(details) >= 2:
            break

    if len(details) < 2:
        for expected_label in expected_labels:
            if expected_label not in seen_labels:
                for s in sentences[:6]:
                    if len(s) > 30:
                        details.append({'label': expected_label, 'content': s + '。'})
                        seen_labels.add(expected_label)
                        break
            if len(details) >= 2:
                break

    if not details:
        for s in sentences[:2]:
            if len(s) > 20:
                details.append({'label': '关键信息', 'content': s + '。'})

    return details[:2]


def fetch_article_summary(news_item):
    """抓取单篇新闻正文并提取摘要"""
    try:
        resp = requests.get(news_item['url'], headers=HEADERS, timeout=10)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        text = extract_article_text(resp.text, news_item['source'], news_item['url'])
        if text:
            return summarize_article(text)
    except Exception as e:
        print(f"  抓取正文失败 [{news_item['title'][:20]}]: {str(e)[:40]}")
    return ''


def enrich_all_news(news_data):
    """批量抓取所有新闻的正文，提取摘要和细节"""
    all_tasks = []
    for cat, items in news_data.items():
        for item in items:
            all_tasks.append((cat, item))

    print(f"\n📥 正在抓取 {len(all_tasks)} 篇新闻正文...")
    results = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_article_summary, item): (cat, item)
            for cat, item in all_tasks
        }
        for future in as_completed(futures):
            cat, item = futures[future]
            try:
                summary = future.result()
                results.append((cat, item, summary))
                status = '✅' if summary else '⚠️'
                print(f"  {status} [{CATEGORY_NAMES.get(cat, cat)}] {item['title'][:30]}")
            except Exception as e:
                results.append((cat, item, ''))
                print(f"  ❌ [{CATEGORY_NAMES.get(cat, cat)}] {item['title'][:30]}: {str(e)[:30]}")

    enriched = []
    for cat, item, summary in results:
        details = extract_detail_points(summary, cat)
        enriched.append({
            'cat': cat,
            'title': item['title'],
            'source': item['source'],
            'url': item['url'],
            'overview': summary,
            'details': details,
        })

    enriched.sort(key=lambda x: (
        ['tech', 'economy', 'politics', 'military', 'humanities'].index(x['cat'])
    ))
    return enriched


THEME_CLUSTERS = {

    '政策信号与治理方向': {
        'keywords': ['政策', '国务院', '发改委', '财政部', '央行', '会议', '改革', '制度', '法规', '条例',
                   '意见', '方案', '规划', '部署', '出台', '印发', '审议', '全国人大', '政协', '两会',
                   '高质量发展', '现代化', '体系', '机制', '中国式现代化'],
        'desc_prefix': '政策层面',
    },

    '经济走势与市场信号': {
        'keywords': ['GDP', '增长', '经济', '股市', 'A股', '利率', 'LPR', '贷款', '投资', '消费',
                   '出口', '贸易', 'PMI', '数据', '同比', '环比', '上市', 'IPO', '资金', '流入',
                   '流出', '涨', '跌', '收盘', '涨幅', '跌幅', '板块', '指数', '基金', '债券',
                   '财政', '税收', '地方债', '专项债'],
        'desc_prefix': '经济层面',
    },

    '科技突破与产业变革': {
        'keywords': ['AI', '人工智能', '大模型', '算法', '芯片', '算力', '量子', '卫星', '航天',
                   '自动驾驶', '机器人', '5G', '6G', '数字化', '平台经济', '技术', '创新', '突破',
                   '研发', '发布', '迭代', '升级', '模型', '系统', '架构', '新能源', '光伏',
                   '电池', '新能源汽车', '半导体', '集成电路'],
        'desc_prefix': '科技与产业层面',
    },

    '国际格局与地缘动态': {
        'keywords': ['美国', '中美', '欧盟', '北约', '俄罗斯', '日本', '韩国', '朝鲜', '台湾', '南海',
                   '制裁', '关税', '贸易战', '谈判', '协定', '峰会', '访问', '声明', '军事', '国防',
                   '演习', '装备', '部队', '安全', '威胁', '风险', '冲突', '争端', '主权', '领土'],
        'desc_prefix': '国际层面',
    },

    '民生关切与社会脉动': {
        'keywords': ['民生', '教育', '医疗', '住房', '养老', '就业', '收入', '保障', '社保', '医保',
                   '文化', '遗产', '保护', '体育', '旅游', '交通', '环保', '碳', '绿色', '生态',
                   '社会', '公众', '群众', '人民', '居民', '消费者', '生活', '健康'],
        'desc_prefix': '社会与民生层面',
    },
}

THEME_INSIGHT_CONCISE = {
    '政策信号与治理方向': [
        '决策层在{angle}方向持续发力，配套措施有望密集落地，对{impact_group}而言意味着制度红利与规则重塑。',
        '{angle}相关部署是战略框架的有机组成，后续细则出台节奏将直接影响市场预期与产业布局。',
    ],
    '经济走势与市场信号': [
        '{angle}成为当前经济运行关键变量，需关注政策传导时滞，在短期波动中把握结构性机会。',
        '{angle}领域边际变化值得重视，资金流向与板块轮动暗示市场正对中长期增长逻辑重新定价。',
    ],
    '科技突破与产业变革': [
        '{angle}方向加速演进，技术从实验室到产品化周期缩短，率先完成生态建设的企业将获先发优势。',
        '{angle}技术突破是产业链协同升级的缩影，上下游企业均面临能力重构的压力与机遇。',
    ],
    '国际格局与地缘动态': [
        '{angle}动向反映国际力量对比持续变化，地缘政治风险正成为外贸企业和跨境投资者的核心决策变量。',
        '围绕{angle}的多方博弈短期内将加剧市场波动，中长期可能重塑全球供应链格局。',
    ],
    '民生关切与社会脉动': [
        '{angle}领域进展折射社会治理重心向提质增效转变，将催生新服务业态和消费增长点。',
        '{angle}议题热度表明民生从\"有没有\"向\"好不好\"过渡，这一转向蕴含社会投资机遇。',
    ],
}


def compose_daily_summary(enriched_news):
    """精简总结：按主题归类，每层1-2句核心分析，去除标题罗列和过渡语"""
    if not enriched_news:
        return '<p>今日暂无足够信息生成深度总结，请浏览各栏目新闻卡片了解详情。</p>'

    cluster_news = {}
    for cluster_name, config in THEME_CLUSTERS.items():
        cluster_news[cluster_name] = []
        for n in enriched_news:
            full_text = n['title'] + n.get('overview', '')
            hits = sum(1 for kw in config['keywords'] if kw in full_text)
            if hits >= 2:
                cluster_news[cluster_name].append(n)

    active_clusters = []
    for cluster_name, news_list in cluster_news.items():
        if news_list:
            unique = []
            seen_titles = set()
            for n in news_list:
                if n['title'] not in seen_titles:
                    seen_titles.add(n['title'])
                    unique.append(n)
            if unique:
                active_clusters.append((cluster_name, unique))

    if not active_clusters:
        by_cat = {}
        for n in enriched_news:
            by_cat.setdefault(n['cat'], []).append(n)
        for cat in ['politics', 'economy', 'tech', 'military', 'humanities']:
            items = by_cat.get(cat, [])
            if items:
                active_clusters.append((f'{CATEGORY_NAMES.get(cat, cat)}领域', items[:4]))

    lines = []
    for idx, (cluster_name, news_list) in enumerate(active_clusters[:5]):
        config = THEME_CLUSTERS.get(cluster_name, {'desc_prefix': cluster_name})
        angle = _extract_cluster_angle(cluster_name, news_list)
        prefix = config.get('desc_prefix', cluster_name)
        impact_group = _guess_impact_group(cluster_name, news_list)

        templates = THEME_INSIGHT_CONCISE.get(
            cluster_name,
            ['{}方面，{angle}趋势明显，值得关注。']
        )
        insight = templates[idx % len(templates)].format(angle=angle, impact_group=impact_group)

        lines.append(f'<strong>{prefix}</strong>：{insight}')

    lines.append(
        '综合来看，今日各领域动态共同指向一个正在深刻调整的世界——政策在精细化、'
        '市场在结构性分化、技术在加速渗透、国际秩序在持续重组。'
        '在这多重转型叠加的关键时期，理解不同领域间的联动关系，才能更准确地把握方向。'
    )

    return ''.join(f'<p class="summary-line">{l}</p>' for l in lines)


def _extract_cluster_angle(cluster_name, news_list):

    titles = ' '.join(n['title'] for n in news_list)
    config = THEME_CLUSTERS.get(cluster_name, {})

    angle_keywords = {
        '政策信号与治理方向': [
            ('深化改革', ['改革', '深化', '机制', '体制', '制度']),
            ('高质量发展', ['高质量', '发展', '现代化', '升级', '转型']),
            ('制度完善', ['完善', '健全', '规范', '标准', '体系']),
            ('政策落地', ['落地', '实施', '执行', '推进', '落实']),
            ('统筹协调', ['统筹', '协调', '综合', '一体', '联动']),
        ],
        '经济走势与市场信号': [
            ('稳增长', ['稳增长', '复苏', '恢复', '回升', '回暖']),
            ('结构性调整', ['结构', '调整', '分化', '转型', '优化']),
            ('市场信心修复', ['信心', '修复', '反弹', '回暖', '企稳']),
            ('政策宽松', ['降息', '降准', '宽松', '刺激', '扶持', '补贴']),
            ('风险防控', ['风险', '防控', '监管', '规范', '整治']),
        ],
        '科技突破与产业变革': [
            ('自主创新', ['自主', '国产', '突破', '自研', '原创']),
            ('产业升级', ['产业', '升级', '数字化', '智能化', '转型']),
            ('生态构建', ['生态', '平台', '开放', '合作', '协同']),
            ('应用落地', ['落地', '应用', '商用', '产品', '场景']),
            ('前沿探索', ['前沿', '探索', '突破', '首次', '领先']),
        ],
        '国际格局与地缘动态': [
            ('大国博弈', ['博弈', '竞争', '对抗', '角力', '较量']),
            ('区域安全', ['安全', '稳定', '和平', '冲突', '危机']),
            ('多边合作', ['合作', '对话', '协商', '共识', '联合']),
            ('战略调整', ['战略', '调整', '转向', '布局', '部署']),
            ('供应链安全', ['供应链', '产业链', '依赖', '自主', '脱钩']),
        ],
        '民生关切与社会脉动': [
            ('公共服务优化', ['服务', '优化', '提升', '改善', '便利']),
            ('文化传承创新', ['文化', '传承', '创新', '遗产', '保护']),
            ('社会保障完善', ['保障', '养老', '医疗', '教育', '住房']),
            ('生态环境保护', ['生态', '环境', '绿色', '低碳', '环保']),
            ('社会治理升级', ['治理', '管理', '服务', '基层', '社区']),
        ],
        '军事领域': [
            ('国防现代化', ['现代化', '装备', '升级', '新型', '先进']),
            ('安全态势应对', ['安全', '态势', '应对', '反应', '部署']),
        ],
    }

    cluster_angles = angle_keywords.get(cluster_name, [('最新进展', [])])
    best_angle = '最新进展'
    best_score = 0

    for angle_name, kws in cluster_angles:
        score = sum(1 for kw in kws if kw in titles)
        if score > best_score:
            best_score = score
            best_angle = angle_name

    if best_score == 0 and not any(kw in titles for kw in (cluster_angles[0][1] if cluster_angles else [])):
        for angle_name, kws in cluster_angles:
            if any(kw in titles for kw in kws):
                best_angle = angle_name
                break

    return best_angle


def _guess_impact_group(cluster_name, news_list):
    titles = ' '.join(n['title'] for n in news_list)
    overviews = ' '.join(n.get('overview', '') for n in news_list)
    full_text = titles + overviews

    impact_maps = {
        '政策信号与治理方向': [
            ('相关行业从业者和投资者', ['企业', '市场', '产业', '行业', '投资']),
            ('各级政府与市场主体', ['政府', '地方', '企业', '市场']),
            ('社会公众与各类企业', ['公众', '社会', '企业', '民生']),
        ],
        '经济走势与市场信号': [
            ('投资者和企业决策者', ['投资', '企业', '市场', '板块', '资金']),
            ('市场主体与普通居民', ['消费', '物价', '收入', '就业', '民生']),
            ('金融机构与实体经济部门', ['金融', '银行', '贷款', '实体', '企业']),
        ],
        '科技突破与产业变革': [
            ('科技企业和技术从业者', ['科技', '技术', '企业', '研发', '人才']),
            ('产业链上下游与终端用户', ['产业', '链条', '应用', '用户', '场景']),
            ('行业竞争格局与就业市场', ['竞争', '格局', '就业', '岗位', '人才']),
        ],
        '国际格局与地缘动态': [
            ('跨国企业和外贸从业者', ['贸易', '企业', '国际', '出口', '跨境']),
            ('政策制定者与安全部门', ['政策', '安全', '战略', '部署', '外交']),
            ('全球投资者与供应链管理者', ['投资', '全球', '供应链', '风险', '市场']),
        ],
        '民生关切与社会脉动': [
            ('普通民众和社区服务提供者', ['民众', '居民', '社区', '服务', '生活']),
            ('公共管理部门与服务机构', ['管理', '服务', '部门', '机构', '公共']),
            ('文化教育从业者和家庭', ['文化', '教育', '家庭', '学校', '社会']),
        ],
        '科技领域': [
            ('科技从业者与投资者', ['科技', '技术', '投资', '创新', '研发']),
        ],
        '经济领域': [
            ('市场主体与投资者', ['市场', '投资', '经济', '企业', '资金']),
        ],
        '政治领域': [
            ('政策关注者与相关行业', ['政策', '治理', '制度', '改革']),
        ],
        '军事领域': [
            ('国防安全相关部门', ['国防', '安全', '军事', '装备']),
        ],
        '人文领域': [
            ('社会公众与文化工作者', ['社会', '文化', '公众', '民生']),
        ],
    }

    candidates = impact_maps.get(cluster_name, [('各界关注者', [])])
    for group_name, kws in candidates:
        for kw in kws:
            if kw in full_text:
                return group_name
    return candidates[0][0]


def escape_js_string(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')


def update_html_template(enriched_news, summary_html, use_fallback=False):
    date_str = datetime.now().strftime("%Y年%m月%d日")

    news_items_html = {}
    news_details_js = {}
    news_id = 1

    for cat_key in ['tech', 'economy', 'politics', 'military', 'humanities']:
        items = []
        cat_news = [n for n in enriched_news if n['cat'] == cat_key]

        for news in cat_news:
            overview_html = ''
            if news['overview']:
                overview_html = f'<div class="news-card-overview">{news["overview"]}</div>'

            detail_html_lines = []
            for d in news['details']:
                detail_html_lines.append(
                    '<div class="detail-item">'
                    f'<span class="dlbl">{d["label"]}</span>'
                    f'{d["content"]}'
                    '</div>'
                )
            detail_html = '\n'.join(detail_html_lines)

            cat_class = f'category-{cat_key}'
            item_html = f'''<div class="news-card {cat_class}" onclick="window.location.href='news-detail.html?n={news_id}'">
                <div class="news-card-title">{news['title']}</div>
                <div class="news-card-source">{news['source']}</div>
                {overview_html}
                <div class="detail-list">
                    {detail_html}
                </div>
            </div>'''
            items.append(item_html)

            news_details_js[news_id] = {
                'title': escape_js_string(news['title']),
                'source': news['source'],
                'url': news['url'],
                'cat': cat_key,
                'overview': escape_js_string(news['overview']),
                'details': news['details'],
                'insight': compose_news_insight(news),
            }
            news_id += 1

        if not items:
            items = ['<p class="empty-notice">暂无新闻</p>']

        news_items_html[cat_key] = '\n'.join(items)

    js_parts = []
    for idx, data in news_details_js.items():
        details_json = json.dumps(data['details'], ensure_ascii=False)
        escaped_title = data['title']
        escaped_source = data['source']
        escaped_overview = data['overview']
        escaped_insight = data['insight']
        escaped_url = data['url']
        js_parts.append(
            f"{idx}: {{title: \"{escaped_title}\", source: \"{escaped_source}\", "
            f"url: \"{escaped_url}\", cat: \"{data['cat']}\", "
            f"overview: \"{escaped_overview}\", "
            f"details: {details_json}, "
            f"insight: \"{escaped_insight}\"}}"
        )
    js_news_data = '{\n        ' + ',\n        '.join(js_parts) + '\n    }' if js_parts else '{0: {title: "暂无新闻"}}'

    with open('template_main.html', 'r', encoding='utf-8') as f:
        main_html = f.read()

    main_html = main_html.replace('{{DATE}}', date_str)
    main_html = main_html.replace('{{SUMMARY}}', summary_html)
    main_html = main_html.replace('{{FALLBACK_NOTICE}}',
        '<div style="background:linear-gradient(135deg, rgba(255,193,7,0.1), rgba(255,152,0,0.08));border:1px solid rgba(255,193,7,0.4);border-radius:8px;padding:14px 18px;margin-bottom:24px;font-size:13px;color:#b8860b;"><span style="font-weight:700;">⚡ 网络异常提示：</span>今日新闻源抓取失败，页面展示的是示例数据，实际新闻请关注后续更新。</div>'
        if use_fallback else '')

    for cat in ['tech', 'economy', 'politics', 'humanities', 'military']:
        placeholder = f'{{{{NEWS_{cat.upper()}}}}}'
        main_html = main_html.replace(placeholder, news_items_html.get(cat, ''))
        count_placeholder = f'{{{{{cat.upper()}_COUNT}}}}'
        count = len([n for n in enriched_news if n['cat'] == cat])
        main_html = main_html.replace(count_placeholder, str(count))

    with open('daily-news.html', 'w', encoding='utf-8') as f:
        f.write(main_html)
    print("\n✅ daily-news.html 已生成")

    with open('template_detail.html', 'r', encoding='utf-8') as f:
        detail_html = f.read()

    detail_html = detail_html.replace('{{{NEWS_DATA}}}', js_news_data)

    with open('news-detail.html', 'w', encoding='utf-8') as f:
        f.write(detail_html)
    print("✅ news-detail.html 已生成")


def compose_news_insight(news):
    """为单条新闻撰写有指向性的启示——说明这意味着什么、影响谁、后续如何发展"""
    title = news.get('title', '')
    overview = news.get('overview', '')
    cat = news.get('cat', '')

    keyword_hints = _extract_key_hints(title + overview)

    angle = keyword_hints.get('angle', '值得关注')
    impact = keyword_hints.get('impact', '相关领域各方')
    outlook = keyword_hints.get('outlook', '持续关注后续动态')

    insight_templates = {
        'tech': (
            '“{title}”这一动态传递的核心信号是：{angle}。对于{impact}而言，这意味着技术路线和市场格局可能出现实质性变化。'
            '从趋势上看，{outlook}，值得持续跟踪。'
        ),
        'economy': (
            '“{title}”释放的关键信息在于{angle}。对{impact}来说，这条消息提示关注政策节奏与资金流向的变化。'
            '前瞻来看，{outlook}，建议保持跟踪。'
        ),
        'politics': (
            '“{title}”背后的深层逻辑是{angle}。对于{impact}来说，这意味着战略环境或制度框架正在发生调整。'
            '展望后续，{outlook}，其连锁效应值得密切关注。'
        ),
        'military': (
            '“{title}”反映出的核心变化在于{angle}。这对{impact}来说意味着安全能力或地缘态势进入新阶段。'
            '后续值得关注的是，{outlook}。'
        ),
        'humanities': (
            '“{title}”折射出的社会意义在于{angle}。对于{impact}而言，这意味着发展理念或生活方式正在演进。'
            '未来可以期待，{outlook}。'
        ),
    }

    default_tpl = (
        '“{title}”值得关注的核心是{angle}。对于{impact}而言，这是一个值得重视的信号。'
        '后续可以关注{outlook}。'
    )

    tpl = insight_templates.get(cat, default_tpl)
    return tpl.format(title=title, angle=angle, impact=impact, outlook=outlook)


def _extract_key_hints(text):

    angle_hints = {
        '政策密集出台': ['出台', '印发', '发布', '实施', '落地', '方案', '意见', '通知', '措施', '部署'],
        '产业格局重塑': ['格局', '重塑', '整合', '重组', '并购', '洗牌', '淘汰', '崛起'],
        '技术取得突破': ['突破', '攻克', '研发成功', '首次', '领先', '刷新', '纪录', '自主'],
        '市场信心回暖': ['回暖', '反弹', '回升', '上涨', '流入', '看好', '增持', '突破'],
        '监管边界厘清': ['监管', '规范', '整治', '查处', '合规', '标准', '门槛', '准入'],
        '国际关系调整': ['关系', '合作', '对话', '协商', '谈判', '访问', '声明', '共识', '分歧'],
        '增长动能切换': ['动能', '切换', '转型', '升级', '新经济', '新业态', '新模式', '消费'],
        '安全态势变化': ['安全', '威胁', '风险', '冲突', '对抗', '防御', '部署', '警戒'],
        '民生持续改善': ['改善', '提升', '优化', '保障', '服务', '惠民', '便利', '覆盖'],
        '社会共识凝聚': ['共识', '凝聚', '呼声', '关注', '讨论', '热议', '反思', '觉醒'],
    }

    impact_hints = {
        '投资者和资本市场': ['股市', '股价', '投资', '资本', '基金', '板块', '资金', '市值', 'IPO'],
        '相关行业和企业': ['企业', '公司', '行业', '产业', '厂商', '供应链', '制造业'],
        '政策制定和监管部门': ['政府', '部门', '监管', '政策', '制度', '法规', '标准'],
        '科技从业者和研发机构': ['技术', '研发', '创新', '工程师', '科学家', '实验室', '专利'],
        '普通消费者和居民': ['消费', '居民', '百姓', '民众', '用户', '生活', '服务', '价格', '物价'],
        '外贸和跨境从业者': ['出口', '进口', '贸易', '关税', '跨境', '国际', '海外'],
    }

    outlook_hints = {
        '政策细则和落地节奏将成为关键观察点': ['政策', '细则', '出台', '落地', '实施', '节奏'],
        '行业洗牌和竞争格局可能加速演变': ['竞争', '格局', '洗牌', '行业', '市场', '淘汰'],
        '技术商业化和生态建设进度值得跟踪': ['技术', '商业化', '应用', '落地', '生态', '平台'],
        '市场情绪和资金流向可能出现结构性分化': ['市场', '资金', '情绪', '分化', '结构', '流向'],
        '国际博弈态势和各方后续反应将影响走向': ['国际', '博弈', '反应', '后续', '多方', '回应'],
        '配套措施和长效机制建设是下一步重点': ['配套', '机制', '体系', '建设', '完善', '长期'],
    }

    best_angle = '出现值得关注的变化'
    best_angle_score = 0
    for desc, kws in angle_hints.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_angle_score:
            best_angle_score = score
            best_angle = desc

    best_impact = '相关各方'
    best_impact_score = 0
    for desc, kws in impact_hints.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_impact_score:
            best_impact_score = score
            best_impact = desc

    best_outlook = '该事件的后续发展'
    best_outlook_score = 0
    for desc, kws in outlook_hints.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best_outlook_score:
            best_outlook_score = score
            best_outlook = desc

    return {'angle': best_angle, 'impact': best_impact, 'outlook': best_outlook}


def fetch_all_news():
    all_news = {}
    for category, sources in NEWS_SOURCES.items():
        category_news = []
        for source in sources:
            news = fetch_news_from_source(source)
            category_news.extend(news)

        seen = set()
        unique_news = []
        for news_item in category_news:
            if news_item['title'] not in seen:
                seen.add(news_item['title'])
                unique_news.append(news_item)

        all_news[category] = unique_news[:5]
        print(f"🔍 {CATEGORY_NAMES.get(category, category)}: 抓取到 {len(unique_news[:5])} 条")

    return all_news


FALLBACK_TITLE_POOL = {
    'politics': [
        '国务院常务会议部署稳经济一揽子政策接续措施',
        '外交部回应国际热点：坚持对话协商解决分歧',
        '全国人大常委会审议多项重要法律草案',
        '王毅出席多边外长会议阐述中方立场',
        '国务院发布关于推进全国统一大市场建设的意见',
        '中央经济工作会议定调明年宏观政策方向',
        '商务部：多边贸易体制改革取得阶段性进展',
        '医保基金监管新规出台，守护百姓救命钱',
        '国防部：坚决反对任何形式的军事挑衅',
        '国家发改委推动营商环境进一步优化',
        '中美高层战略对话在第三地举行',
        '国务院印发深化收入分配制度改革方案',
        '中欧班列开行量创新高，贸易通道持续拓宽',
        '全国生态保护红线划定工作全面完成',
    ],
    'economy': [
        'A股三大指数收涨，两市成交突破万亿大关',
        '央行实施降准操作释放长期资金超五千亿元',
        '前五月进出口贸易顺差创近三年新高',
        '大宗商品价格波动加剧，监管部门加强市场引导',
        '新能源板块领涨两市，光伏龙头业绩超预期',
        '人民币汇率弹性增强，央行强调双向浮动是常态',
        '财政部启动新一轮专项债券发行',
        '社融数据超预期，实体经济融资环境持续改善',
        '数字人民币试点已覆盖全国主要城市',
        '快递业务量突破千亿件，消费复苏信号明显',
        '科创50指数成分股调整，硬科技企业占比提升',
        '个人养老金制度落地一年，参保人数稳步增长',
        '智能汽车产业链景气度持续攀升',
        '多地出台购房新政，因城施策稳定市场预期',
    ],
    'tech': [
        '国产AI大模型性能评测：接近国际顶尖水平',
        '中国量子计算原型机再度刷新世界纪录',
        '工信部推进6G技术研发，多个试验卫星发射成功',
        '生物医药领域取得突破，国产创新药首获FDA批准',
        '智能驾驶路测里程累计突破亿公里',
        '5G基站超过四百万座，行业应用全面开花',
        '可复用商业运载火箭实现首次垂直回收',
        '国产操作系统生态建设提速，装机量破千万',
        '第三代半导体产业迎来投资高峰期',
        '脑机接口技术临床试验取得阶段性成果',
        '新能源汽车渗透率突破50%里程碑',
        '全球最大液流储能电站在新疆并网发电',
        '工业机器人装机量稳居全球第一',
        '太赫兹通信技术研究取得关键进展',
    ],
    'military': [
        '解放军东部战区组织多军种联合演训',
        '新一代主战坦克完成高原适应性测试',
        '空军开放活动展示多款新型战机',
        '海军新型综合补给舰入列服役',
        '国防科技大学发布新型无人机集群技术',
        '军事科学院举办国防科技创新成果展',
        '火箭军某旅组织夜间导弹突击演练',
        '中俄联合军事演习在日本海举行',
        '退役军人保障法配套细则出台',
        '武警部队深入推进训练转型',
    ],
    'humanities': [
        '教育部启动基础教育课程改革新方案',
        '中国世界遗产总数稳居世界前列',
        '五一假期旅游市场火爆，文旅融合成新趋势',
        '高校双一流建设进入提质增效新阶段',
        '全民健身公共服务体系进一步完善',
        '全国博物馆年参观人次突破十四亿',
        '基本养老保险全国统筹改革稳步推进',
        '中国作家获国际文学大奖，彰显文化软实力',
        '老旧小区改造加装电梯惠及百万居民',
        '高校就业指导服务升级，多举措促进毕业生就业',
        '数字文化新业态营收规模持续扩大',
        '全国医保参保率稳定在百分之九十五以上',
    ],
}


def get_fallback_news():
    today = datetime.now()
    day_offset = today.day - 1

    result = {}
    for cat, pool in FALLBACK_TITLE_POOL.items():
        start = (day_offset * 3) % len(pool)
        selected = []
        for i in range(min(5, len(pool))):
            idx = (start + i) % len(pool)
            selected.append({
                'title': pool[idx],
                'source': '示例数据',
                'url': '#',
            })
        result[cat] = selected
    return result


def generate_fallback_overview(title, cat):
    """为备用新闻生成简洁概述（时间+地点+主体+事件格式）"""
    today_str = datetime.now().strftime("%m月%d日")
    templates = {
        'politics': f'{today_str}，相关部门就"{title}"作出最新部署。此举旨在推动政策落地见效，后续实施细则值得关注。',
        'economy': f'{today_str}，"{title}"引发市场关注。当前经济环境下，该动态对行业预期和政策方向具有参考价值。',
        'tech': f'{today_str}，"{title}"取得重要进展，标志着相关领域技术加速向产业化迈进。',
        'military': f'{today_str}，"{title}"是国防安全领域的重要动态，体现能力建设的持续推进。',
        'humanities': f'{today_str}，"{title}"展现社会民生和文化领域新进展，折射公众对美好生活的共同追求。',
    }
    return templates.get(cat, f'{today_str}，该新闻值得关注与深入思考。')


def main():
    print("=" * 50)
    print(f"📰 每日新闻更新 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    use_fallback = False
    try:
        news_data = fetch_all_news()
        total = sum(len(v) for v in news_data.values())
        if total < 3:
            print(f"\n⚠️ 只爬取到 {total} 条新闻，启用动态备用数据")
            news_data = get_fallback_news()
            use_fallback = True
    except Exception as e:
        print(f"\n⚠️ 爬取出错: {str(e)[:80]}，启用动态备用数据")
        news_data = get_fallback_news()
        use_fallback = True

    if use_fallback:
        enriched = []
        nid = 1
        for cat in ['tech', 'economy', 'politics', 'military', 'humanities']:
            for item in news_data.get(cat, []):
                overview = generate_fallback_overview(item['title'], cat)
                enriched.append({
                    'cat': cat,
                    'title': item['title'],
                    'source': item['source'],
                    'url': item['url'],
                    'overview': overview,
                    'details': [
                        {'label': '核心内容', 'content': overview},
                    ],
                })
                nid += 1
    else:
        enriched = enrich_all_news(news_data)

    summary_html = compose_daily_summary(enriched)
    update_html_template(enriched, summary_html, use_fallback)

    total_news = len(enriched)
    total_with_content = sum(1 for n in enriched if n['overview'])
    print(f"\n🎉 更新完成！共 {total_news} 条新闻，{total_with_content} 条抓取到正文内容")


if __name__ == "__main__":
    main()
