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


def fetch_news_from_source(source):
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
        print(f"  爬取 {source['name']} 失败: {str(e)[:60]}")

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


def compose_daily_summary(enriched_news):
    """基于所有新闻摘要撰写有深度的每日总结"""
    by_cat = {}
    for n in enriched_news:
        by_cat.setdefault(n['cat'], []).append(n)

    titles_by_cat = {}
    overviews_by_cat = {}
    for cat, items in by_cat.items():
        titles_by_cat[cat] = [item['title'] for item in items[:4]]
        overviews_by_cat[cat] = [item['overview'] for item in items if item['overview']]

    macro_parts = []
    micro_parts = []

    cat_macro_templates = {
        'politics': '今日政治领域聚焦{}等方面，{}{}',
        'economy': '经济方面重点报道了{}，{}{}',
        'tech': '科技领域关注{}，{}{}',
        'military': '军事方面围绕{}等动态，{}{}',
        'humanities': '人文社会领域涉及{}，{}{}',
    }
    cat_micro_templates = {
        'politics': '{}等消息显示国际政治格局正在发生深刻调整，各方博弈进入新阶段。',
        'economy': '{}等动态提示我们，市场主体需关注政策节奏与结构性机会。',
        'tech': '{}等技术突破表明，深耕自主创新仍是长期竞争力的关键。',
        'military': '{}等动向提醒我们，安全与发展需统筹兼顾。',
        'humanities': '{}等话题启示我们，民生改善与文化传承需要持续投入与关注。',
    }

    for cat in ['politics', 'economy', 'tech', 'military', 'humanities']:
        titles = titles_by_cat.get(cat, [])
        overviews = overviews_by_cat.get(cat, [])
        cat_name = CATEGORY_NAMES.get(cat, cat)

        if not titles:
            continue

        title_list = '、'.join(titles[:3])

        if overviews:
            combined = overviews[0][:120]
        else:
            combined = f'{cat_name}今日有多条值得关注的消息。'

        macro = cat_macro_templates.get(cat, '{}领域{}。').format(
            title_list,
            combined[:80],
            '值得持续关注。' if not combined else ''
        )
        macro_parts.append(macro)

        micro = cat_micro_templates.get(cat, '{}值得关注后续发展。').format(title_list)
        micro_parts.append(micro)

    macro_final = '；'.join(macro_parts[:4]) if macro_parts else '今日各领域新闻呈现多元态势，建议结合具体条目深入了解。'
    micro_final = '；'.join(micro_parts[:4]) if micro_parts else '建议关注各领域的后续动态与政策走向。'

    return macro_final, micro_final


def escape_js_string(s):
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ').replace('\r', '').replace('"', '&quot;')


def update_html_template(enriched_news, macro, micro):
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
    main_html = main_html.replace('{{SUMMARY_MACRO}}', macro)
    main_html = main_html.replace('{{SUMMARY_MICRO}}', micro)

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
    """为单条新闻撰写启示"""
    cat = news['cat']
    overview = news.get('overview', '')
    title = news.get('title', '')

    cat_insights = {
        'tech': '该科技动态折射出产业变革的深层逻辑——技术突破正从实验室加速走向商业化落地，对行业格局和人才需求都将产生涟漪效应。',
        'economy': '这条消息给出的核心信号是：在当前经济环境下，市场参与者的预期管理与风险对冲能力比以往任何时候都更重要。',
        'politics': '该政治事件提醒我们，国际关系的每一次微妙调整背后都是深刻的战略博弈，理解其底层逻辑有助于看清未来走向。',
        'military': '军事领域的每一步发展都是国家安全能力建设的具体体现，其背后涉及的技术储备和产业链支撑同样值得深思。',
        'humanities': '这条人文新闻的意义超越了事件本身——它折射出社会价值取向与文化自信的深层脉动，提醒我们关注精神层面的建设。',
    }

    return cat_insights.get(cat, '持续关注该事件的后续发展与深远影响。')


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


def generate_fallback_overview(title, cat):
    """为备用新闻生成概述"""
    templates = {
        'politics': '围绕"{title}"这一主题，相关各方正在积极推进。此事件在国际国内引发了广泛关注和讨论，后续发展值得密切关注。',
        'economy': '"{title}"这一消息引发市场各方关注。当前经济环境下，此类动态对行业预期和政策方向具有重要参考价值。',
        'tech': '"{title}"标志着相关领域技术取得重要进展，或将推动行业格局发生变化，值得持续跟踪后续落地情况。',
        'military': '"{title}"是国防军事领域的重要动态，体现了国家安全能力建设的持续推进。',
        'humanities': '"{title}"展现了社会民生和精神文化层面的新进展，折射出人民群众对美好生活的共同追求。',
    }
    return templates.get(cat, '该新闻值得关注与深入思考。').format(title=title)


def main():
    print("=" * 50)
    print(f"📰 每日新闻更新 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    use_fallback = False
    try:
        news_data = fetch_all_news()
        total = sum(len(v) for v in news_data.values())
        if total < 5:
            print("\n⚠️ 爬取新闻太少，使用备用数据")
            news_data = get_fallback_news()
            use_fallback = True
    except Exception as e:
        print(f"\n⚠️ 爬取出错: {str(e)}，使用备用数据")
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

    macro, micro = compose_daily_summary(enriched)
    update_html_template(enriched, macro, micro)

    total_news = len(enriched)
    total_with_content = sum(1 for n in enriched if n['overview'])
    print(f"\n🎉 更新完成！共 {total_news} 条新闻，{total_with_content} 条抓取到正文内容")


if __name__ == "__main__":
    main()
