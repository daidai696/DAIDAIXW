#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日新闻爬虫脚本
职责：1. 爬取新闻数据 2. 处理数据 3. 读取HTML模板替换内容
模板文件（永不修改）：template_main.html / template_detail.html
输出文件（每次覆盖）：daily-news.html / news-detail.html
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
    'tech': '科技变革正在重塑全球产业格局，每一次技术突破都可能催生新的商业模式和生活方式变革。',
    'economy': '经济数据是市场情绪的晴雨表，当前各项指标反映出全球经济正处于深刻的结构性调整期。',
    'politics': '国际政治格局持续演变，大国博弈与多边合作并行推进，深刻影响着全球治理体系的走向。',
    'humanities': '社会民生与人文关怀始终是发展的底色，文化创新与民生改善共同构筑美好生活的根基。',
    'military': '国防安全是国家安全的重要基石，军事科技的发展与地缘格局的变化值得我们持续关注。',
}

DETAIL_TEMPLATES = {
    '核心内容': '围绕"{title}"这一主题，各方正积极推进相关工作。具体来看，相关决策已在多轮磋商后基本成型，实施路径和配套措施日趋明晰，引发业界广泛关注和讨论。',
    '重要成果': '在"{title}"方面已取得阶段性突破。经过持续努力和多边协作，关键节点目标顺利达成，为后续项目推进和产业链协同奠定了坚实基础。',
    '核心进展': '"{title}"相关项目近期取得关键进展。技术验证和试点应用均超出预期，行业标准制定与产业化落地正在同步推进，市场前景值得期待。',
    '市场反应': '受"{title}"消息提振，市场信心明显回升。投资者正在重新评估相关板块的估值逻辑与增长前景，短期内可能出现结构性行情分化，中长期趋势仍需关注基本面支撑。',
    '紧张态势': '"{title}"反映出当前局势的复杂性与不确定性。多方博弈进入关键阶段，事态走向将对区域稳定和全球供应链产生深远影响，各方态度值得密切关注。',
    '核心数据': '"{title}"所涉及的核心指标显示出积极变化。最新统计表明关键数据超出市场预期，增速和结构均有改善，为行业研判和政策制定提供了重要参考依据。',
    '重要动作': '针对"{title}"，相关方面已启动一系列关键部署。包括加强多部门协同、优化资源配置、完善法规配套等举措正在密集落地，展现出果断的行动力。',
    '核心计划': '"{title}"所披露的规划蓝图展现了长远战略视野。路线图明确了分阶段目标和关键里程碑，涵盖技术攻关、市场拓展和生态建设等多个维度，实施路径清晰可行。',
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
            {'title': '全国两会闭幕，高质量发展成最强音', 'source': '新华网', 'url': '#'},
            {'title': '中欧领导人会晤达成多项共识', 'source': '人民网', 'url': '#'},
            {'title': '联合国气候变化大会通过新决议', 'source': '央视新闻', 'url': '#'},
        ],
        'economy': [
            {'title': '一季度GDP同比增长5.3%，经济运行开局良好', 'source': '经济日报', 'url': '#'},
            {'title': '央行下调LPR利率，释放稳增长信号', 'source': '证券时报', 'url': '#'},
            {'title': 'A股三大指数全线上涨，北向资金大幅净流入', 'source': '新浪财经', 'url': '#'},
        ],
        'tech': [
            {'title': '国产大模型迭代提速，多模态能力显著提升', 'source': '科技日报', 'url': '#'},
            {'title': '华为发布新一代芯片，突破先进制程瓶颈', 'source': '36氪', 'url': '#'},
            {'title': '商业航天加速布局，多枚火箭成功发射', 'source': 'IT之家', 'url': '#'},
        ],
        'military': [
            {'title': '新型驱逐舰正式入列，海军战力再上新台阶', 'source': '解放军报', 'url': '#'},
            {'title': '国防部回应南海局势：坚决捍卫国家主权', 'source': '环球军事', 'url': '#'},
        ],
        'humanities': [
            {'title': '文化遗产保护取得新进展，多处遗址入选世界名录', 'source': '光明日报', 'url': '#'},
            {'title': '教育改革深入推进，多地推出创新举措', 'source': '澎湃新闻', 'url': '#'},
        ]
    }


def generate_summary(news_data):
    macro_templates = {
        'politics': '国际政治格局持续演变，{cat}领域的最新动态反映出大国博弈与多边合作并行推进的复杂态势，各方在竞争与合作间寻求动态平衡。',
        'economy': '全球经济正处于深度调整期，{cat}数据的波动折射出市场在多空因素交织下的谨慎情绪，政策预期成为影响走势的关键变量。',
        'tech': '科技革命浪潮持续涌动，{cat}领域的突破正在加速产业数字化和智能化转型，自主创新能力的提升尤为关键。',
        'military': '全球安全形势面临新挑战，{cat}动态反映出各国在防务技术和战略布局上的持续投入，地缘安全格局正在重塑。',
        'humanities': '社会文化领域展现出多元发展态势，{cat}议题引发广泛讨论，折射出公众对美好生活的追求与社会治理的进步。',
    }
    micro_templates = {
        'politics': '政策信号的细微变化往往蕴含着深远的战略意图，个体和企业需敏锐捕捉趋势，提前布局。',
        'economy': '资本流向和消费趋势的微妙变动，折射出市场主体对未来的预期与信心，理性判断尤为重要。',
        'tech': '每一次技术迭代都可能重新定义行业边界，保持终身学习和开放心态是应对变革的最佳策略。',
        'military': '防务技术的突破不仅关乎国家安全，更在产业链层面带动高端制造和基础科研的整体提升。',
        'humanities': '文化传承与创新之间需要平衡，每一项民生改善都凝聚着无数人的努力与智慧。',
    }

    active_cats = [cat for cat, items in news_data.items() if items]
    if not active_cats:
        active_cats = list(macro_templates.keys())

    macro_parts = []
    micro_parts = []
    for cat in active_cats[:3]:
        cat_name = CATEGORY_NAMES.get(cat, cat)
        macro_parts.append(macro_templates.get(cat, '{cat}领域出现值得关注的新动态。').format(cat=cat_name))
        micro_parts.append(micro_templates.get(cat, '值得关注该领域的后续发展。'))

    return '。'.join(macro_parts) + '。', '。'.join(micro_parts) + '。'


def generate_detail_content(title, cat):
    labels = DETAIL_LABELS.get(cat, ['核心内容'])
    selected = random.sample(labels, min(2, len(labels)))

    details = []
    for label in selected:
        template = DETAIL_TEMPLATES.get(
            label,
            '围绕"{title}"的最新进展值得持续跟踪与深度关注。'
        )
        content = template.replace('{title}', title)
        details.append({'label': label, 'content': content})

    return details


def escape_js_string(s):
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ').replace('\r', '')


def update_html_template(news_data):
    date_str = datetime.now().strftime("%Y年%m月%d日")
    macro, micro = generate_summary(news_data)

    news_items_html = {}
    news_details_js = {}
    news_id = 1

    for cat_key in ['tech', 'economy', 'politics', 'humanities', 'military']:
        items = []
        for news in news_data.get(cat_key, []):
            details = generate_detail_content(news['title'], cat_key)

            detail_html_lines = []
            for d in details:
                detail_html_lines.append(
                    '<div class="detail-item">'
                    f'<span class="dlbl">{d["label"]}</span>'
                    f'{d["content"]}'
                    '</div>'
                )
            detail_html = '\n'.join(detail_html_lines)

            item_html = f'''<div class="news-card" onclick="window.location.href='news-detail.html?n={news_id}'">
                <div class="news-card-title">{news['title']}</div>
                <div class="news-card-source">{news['source']}</div>
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
                'details': details,
                'insight': CATEGORY_INSIGHTS.get(cat_key, '持续关注该领域最新动态。')
            }
            news_id += 1

        if not items:
            items = ['<p style="color:#aaa;padding:20px 24px;font-size:14px;text-align:center;">暂无新闻</p>']

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
    js_news_data = ',\n        '.join(js_parts) if js_parts else '0: {title: "暂无新闻"}'

    with open('template_main.html', 'r', encoding='utf-8') as f:
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

    with open('daily-news.html', 'w', encoding='utf-8') as f:
        f.write(main_html)
    print("✅ daily-news.html 已生成")

    with open('template_detail.html', 'r', encoding='utf-8') as f:
        detail_html = f.read()

    detail_html = detail_html.replace('{{{NEWS_DATA}}}', js_news_data)

    with open('news-detail.html', 'w', encoding='utf-8') as f:
        f.write(detail_html)
    print("✅ news-detail.html 已生成")


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
