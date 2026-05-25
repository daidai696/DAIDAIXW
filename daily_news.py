#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日新闻爬虫脚本
职责：1. 爬取新闻数据 2. 处理数据 3. 读取HTML模板替换内容
"""

import requests
from datetime import datetime
from bs4 import BeautifulSoup
import json
import os
import random

NEWS_SOURCES = {
    'politics': [
        {'name': '新华网', 'url': 'http://www.xinhuanet.com/politics/'},
    ],
    'economy': [
        {'name': '新浪财经', 'url': 'https://finance.sina.com.cn/'},
    ],
    'tech': [
        {'name': '36氪', 'url': 'https://36kr.com/'},
    ],
    'military': [
        {'name': '环球军事', 'url': 'https://mil.huanqiu.com/'},
    ],
    'humanities': [
        {'name': '澎湃新闻', 'url': 'https://www.thepaper.cn/'},
    ]
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

DETAIL_LABELS = {
    'tech': ['核心内容', '核心进展', '核心数据'],
    'economy': ['核心数据', '市场反应', '核心计划'],
    'politics': ['核心内容', '重要成果', '紧张态势'],
    'humanities': ['核心内容', '重要成果'],
    'military': ['重要动作', '紧张态势', '核心计划'],
}

CATEGORY_NAMES = {
    'politics': '政治',
    'economy': '经济',
    'tech': '科技',
    'military': '军事',
    'humanities': '人文',
}

CATEGORY_INSIGHTS = {
    'tech': '科技变革日新月异，每一次技术突破都可能重塑行业格局与生活方式。',
    'economy': '经济数据折射市场脉动，政策信号影响资本流向与产业布局。',
    'politics': '国际政治博弈牵动全球格局，外交动向与经济利益深度交织。',
    'humanities': '人文关怀凝聚社会共识，文化创新承载时代精神。',
    'military': '军事动态关乎国家安全，技术革新重塑防务格局。',
}


def fetch_news_from_source(source):
    news_list = []
    try:
        response = requests.get(source['url'], headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)

        for link in links[:80]:
            title = link.get_text(strip=True)
            href = link['href']

            if not title or len(title) < 8 or len(title) > 80:
                continue
            if any(keyword in title for keyword in ['广告', '推广', '专题', '直播', '视频', '图片']):
                continue

            if href.startswith('/'):
                base_url = '/'.join(source['url'].split('/')[:3])
                href = base_url + href

            news_list.append({
                'title': title,
                'source': source['name'],
                'url': href
            })
            if len(news_list) >= 6:
                break

    except Exception as e:
        print(f"爬取 {source['name']} 失败: {str(e)[:50]}")

    return news_list


def fetch_all_news():
    all_news = {}
    for category, sources in NEWS_SOURCES.items():
        category_news = []
        for source in sources:
            news = fetch_news_from_source(source)
            category_news.extend(news)

        seen = set()
        unique_news = []
        for news in category_news:
            if news['title'] not in seen:
                seen.add(news['title'])
                unique_news.append(news)

        all_news[category] = unique_news[:5]
        print(f"✅ {CATEGORY_NAMES.get(category, category)}: {len(unique_news[:5])} 条")

    return all_news


def get_fallback_news():
    return {
        'politics': [
            {'title': '新华社评论：推动高质量发展取得新成效', 'source': '新华网', 'url': '#'},
            {'title': '人民日报署名文章：中国式现代化是走和平发展道路的现代化', 'source': '人民网', 'url': '#'},
        ],
        'economy': [
            {'title': '中国经济韧性强活力足长期向好基本面不会改变', 'source': '经济日报', 'url': '#'},
            {'title': '金融支持实体经济力度持续加大', 'source': '证券时报', 'url': '#'},
        ],
        'tech': [
            {'title': '我国人工智能产业加速发展应用场景不断拓展', 'source': '科技日报', 'url': '#'},
            {'title': '新能源技术取得突破绿色转型步伐加快', 'source': 'IT之家', 'url': '#'},
        ],
        'military': [
            {'title': '国防和军队现代化建设迈出坚实步伐', 'source': '解放军报', 'url': '#'},
        ],
        'humanities': [
            {'title': '民生保障水平稳步提升人民群众获得感幸福感增强', 'source': '光明日报', 'url': '#'},
        ]
    }


def generate_summary(news_data):
    macro_parts = []
    micro_parts = []

    macro_templates = {
        'politics': '国际政治格局持续演变，{cat}领域的动态反映出大国博弈与多边合作并行推进的趋势。',
        'economy': '全球经济形势复杂多变，{cat}数据表明市场正在寻找新的平衡点。',
        'tech': '科技革命浪潮汹涌，{cat}突破正在加速产业数字化和智能化转型。',
        'military': '全球安全形势面临新挑战，{cat}动态值得持续关注。',
        'humanities': '社会文化领域展现出多元发展态势，{cat}议题引发广泛讨论。',
    }
    micro_templates = {
        'politics': '政策走向和外交信号的细微变化，往往蕴含着深远的战略意图。',
        'economy': '资本流向和消费趋势的微妙变动，折射出市场主体对未来的预期与信心。',
        'tech': '每一次技术迭代都可能催生新的商业模式，个体和企业均需保持敏锐的学习能力。',
        'military': '防务技术的更新换代不仅是军备竞赛，更是国家综合实力的体现。',
        'humanities': '文化创新与人文关怀的细节之处，最能体现一个社会的温度与厚度。',
    }

    active_cats = [cat for cat, items in news_data.items() if items]
    if not active_cats:
        active_cats = list(macro_templates.keys())

    for cat in active_cats[:3]:
        cat_name = CATEGORY_NAMES.get(cat, cat)
        macro_parts.append(macro_templates.get(cat, '{cat}领域出现新动态。').format(cat=cat_name))

    for cat in active_cats[:3]:
        micro_parts.append(micro_templates.get(cat, '值得关注该领域的后续发展。'))

    macro = '。'.join(macro_parts) + '。'
    micro = '。'.join(micro_parts) + '。'

    return macro, micro


def generate_detail_content(title, cat):
    labels = DETAIL_LABELS.get(cat, ['核心内容'])
    selected = random.sample(labels, min(2, len(labels)))

    detail_templates = {
        '核心内容': '围绕"{title}"这一主题，各方正在积极推进相关工作，引发业界广泛关注。',
        '重要成果': '在"{title}"方面取得了阶段性重要突破，为后续发展奠定了坚实基础。',
        '核心进展': '"{title}"相关项目取得关键进展，技术路线和实施方案日趋明朗。',
        '市场反应': '受"{title}"消息影响，市场参与者正在重新评估相关板块的估值与前景。',
        '紧张态势': '"{title}"反映出当前局势的复杂性与紧迫性，各方态度值得密切关注。',
        '核心数据': '"{title}"所涉及的核心指标显示出积极变化，为行业研判提供重要参考。',
        '重要动作': '针对"{title}"，相关方面已启动一系列关键部署与行动方案。',
        '核心计划': '"{title}"所披露的规划蓝图展现出长远战略视野和清晰实施路径。',
    }

    details = []
    for label in selected:
        template = detail_templates.get(label, '关于"{title}"的最新消息值得持续跟踪。')
        content = template.replace('{title}', title)
        details.append({'label': label, 'content': content})

    return details


def update_html_template(news_data):
    print("🔍 当前目录文件:", os.listdir('.'))

    date_str = datetime.now().strftime("%Y年%m月%d日")

    macro, micro = generate_summary(news_data)

    news_items_html = {}
    news_details_js = {}
    news_id = 1

    for cat_key in ['tech', 'economy', 'politics', 'humanities', 'military']:
        items = []
        for news in news_data.get(cat_key, []):
            details = generate_detail_content(news['title'], cat_key)
            details_html_parts = []
            for d in details:
                details_html_parts.append(
                    f'<span class="detail-tag"><strong>{d["label"]}</strong> {d["content"][:28]}…</span>'
                )
            details_html = ''.join(details_html_parts)

            item_html = f'''<div class="news-card" onclick="window.location.href='news_detail.html?n={news_id}'">
                <div class="news-card-title">{news['title']}</div>
                <span class="news-card-source">{news['source']}</span>
                <div class="detail-tags">{details_html}</div>
            </div>'''
            items.append(item_html)

            news_details_js[news_id] = {
                'title': news['title'].replace("'", "\\'").replace('"', '\\"'),
                'source': news['source'],
                'url': news['url'],
                'cat': cat_key,
                'details': details,
                'insight': CATEGORY_INSIGHTS.get(cat_key, '值得持续关注。')
            }
            news_id += 1

        if not items:
            items = ['<p style="color:#aaa;padding:20px;font-size:14px;">暂无新闻</p>']

        news_items_html[cat_key] = '\n'.join(items)

    js_parts = []
    for idx, data in news_details_js.items():
        details_json = json.dumps(data['details'], ensure_ascii=False)
        js_parts.append(
            f"{idx}: {{title: '{data['title']}', source: '{data['source']}', "
            f"url: '{data['url']}', cat: '{data['cat']}', "
            f"details: {details_json}, "
            f"insight: '{data['insight']}'}}"
        )
    js_news_data = ',\n            '.join(js_parts)

    html_template_path = 'daily_news.html'
    detail_template_path = 'news_detail.html'

    with open(html_template_path, 'r', encoding='utf-8') as f:
        main_html = f.read()

    main_html = main_html.replace('{{DATE}}', date_str)
    main_html = main_html.replace('{{SUMMARY_MACRO}}', macro)
    main_html = main_html.replace('{{SUMMARY_MICRO}}', micro)

    for cat in ['tech', 'economy', 'politics', 'humanities', 'military']:
        placeholder = f'{{{{NEWS_{cat.upper()}}}}}'
        main_html = main_html.replace(placeholder, news_items_html.get(cat, ''))
        count_placeholder = f'{{{{{cat.upper()}_COUNT}}}}'
        count = len(news_data.get(cat, []))
        main_html = main_html.replace(count_placeholder, str(count))

    with open('daily_news.html', 'w', encoding='utf-8') as f:
        f.write(main_html)
    print("✅ daily_news.html 已更新")

    with open(detail_template_path, 'r', encoding='utf-8') as f:
        detail_html = f.read()

    if '// {{NEWS_DATA_PLACEHOLDER}}' in detail_html:
        detail_html = detail_html.replace(
            '// {{NEWS_DATA_PLACEHOLDER}}',
            js_news_data if js_news_data else '0: {}'
        )

    with open('news_detail.html', 'w', encoding='utf-8') as f:
        f.write(detail_html)
    print("✅ news_detail.html 已更新")


def main():
    print("=" * 50)
    print(f"📰 每日新闻更新 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    try:
        news_data = fetch_all_news()
        total = sum(len(v) for v in news_data.values())
        if total < 5:
            print("⚠️ 爬取新闻太少，使用备用数据")
            news_data = get_fallback_news()
    except Exception as e:
        print(f"⚠️ 爬取出错: {str(e)}，使用备用数据")
        news_data = get_fallback_news()

    update_html_template(news_data)
    print("\n🎉 更新完成！")


if __name__ == "__main__":
    main()
