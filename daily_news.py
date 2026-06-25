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

# ============================================================
# 新闻源配置：每个分类多个 Google News RSS 查询，覆盖不同角度
# ============================================================

NEWS_SOURCES = {
    'tech': [
        # 科技 —— 侧重 AI 和前沿技术
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD%22+%22%E5%A4%A7%E6%A8%A1%E5%9E%8B%22+%22AI%22+%22AGI%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22AI%E8%8A%AF%E7%89%87%22+%22GPU%22+%22%E6%99%BA%E7%AE%97%E4%B8%AD%E5%BF%83%22+%22%E6%9C%BA%E5%99%A8%E4%BA%BA%22+%22%E8%87%AA%E5%8A%A8%E9%A9%BE%E9%A9%B6%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E7%A7%91%E6%8A%80%E5%88%9B%E6%96%B0%22+%22%E5%8D%8A%E5%AF%BC%E4%BD%93%22+%22%E9%87%8F%E5%AD%90%E8%AE%A1%E7%AE%97%22+%22%E6%96%B0%E8%83%BD%E6%BA%90%22+%22%E5%A4%AA%E7%A9%BA%E6%8E%A2%E7%B4%A2%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'economy': [
        # 经济 —— 聚焦全球和中国宏观经济发展（去股票化）
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E5%85%A8%E7%90%83%E7%BB%8F%E6%B5%8E%22+%22GDP%22+%22%E4%BE%9B%E5%BA%94%E9%93%BE%22+%22%E8%B4%B8%E6%98%93%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E4%B8%AD%E5%9B%BD%E7%BB%8F%E6%B5%8E%22+%22%E9%AB%98%E8%B4%A8%E9%87%8F%E5%8F%91%E5%B1%95%22+%22%E6%96%B0%E7%94%9F%E4%BA%A7%E5%8A%9B%22+%22%E4%BA%A7%E4%B8%9A%E5%8D%87%E7%BA%A7%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E9%80%9A%E8%83%80%22+%22%E5%A4%AE%E8%A1%8C%22+%22%E8%B4%A7%E5%B8%81%E6%94%BF%E7%AD%96%22+%22%E8%B4%A2%E6%94%BF%22+%22%E5%9B%BD%E9%99%85%E7%BB%8F%E6%B5%8E%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'politics': [
        # 政治 —— 国际关系 + 中国政策（不只是内政）
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E4%B8%AD%E7%BE%8E%E5%85%B3%E7%B3%BB%22+%22%E4%B8%AD%E6%AC%A7%22+%22%E5%A4%96%E4%BA%A4%22+%22%E5%9B%BD%E9%99%85%E5%85%B3%E7%B3%BB%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E5%9B%BD%E9%99%85%E5%BD%A2%E5%8A%BF%22+%22%E5%9C%B0%E7%BC%98%E6%94%BF%E6%B2%BB%22+%22%E5%8D%97%E6%B5%B7%22+%22G7%22+%22%E8%81%94%E5%90%88%E5%9B%BD%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E5%9B%BD%E5%8A%A1%E9%99%A2%22+%22%E6%94%BF%E7%AD%96%22+%22%E6%94%B9%E9%9D%A9%22+%22%E6%B3%95%E8%A7%84%22+%22%E4%B8%AD%E5%9B%BD%E6%94%BF%E5%BA%9C%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'humanities': [
        # 人文 —— 聚焦具体人物故事
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E4%BA%BA%E7%89%A9%22+%22%E8%AE%BF%E8%B0%88%22+%22%E4%BA%BA%E7%89%A9%E6%95%85%E4%BA%8B%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E8%89%BA%E6%9C%AF%E5%AE%B6%22+%22%E4%BD%9C%E5%AE%B6%22+%22%E5%AD%A6%E8%80%85%22+%22%E4%BC%81%E4%B8%9A%E5%AE%B6%22+%22%E5%88%9B%E4%B8%9A%E8%80%85%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E6%96%87%E5%8C%96%E5%90%8D%E4%BA%BA%22+%22%E7%A4%BE%E4%BC%9A%E8%BF%90%E5%8A%A8%22+%22%E5%85%AC%E7%9B%8A%22+%22%E4%BA%BA%E6%96%87%E6%8A%A5%E5%91%8A%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
    'military': [
        # 军事 —— 新型装备 + 国际冲突
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E5%86%9B%E4%BA%8B%E8%A3%85%E5%A4%87%22+%22%E6%96%B0%E5%9E%8B%E6%88%98%E6%9C%BA%22+%22%E5%86%9B%E8%88%B0%22+%22%E5%AF%BC%E5%BC%B9%22+%22%E6%AD%A6%E5%99%A8%E7%B3%BB%E7%BB%9F%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E5%86%9B%E4%BA%8B%E5%86%B2%E7%AA%81%22+%22%E6%88%98%E4%BA%89%22+%22%E5%AE%89%E5%85%A8%E5%A8%81%E8%83%81%22+%22%E5%8D%8E%E4%B8%BA%22+%22%E5%8C%97%E7%BA%A6%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
        {'name': 'GoogleNews', 'url': 'https://news.google.com/rss/search?q=%22%E5%9B%BD%E9%98%B2%E7%A7%91%E6%8A%80%22+%22%E5%86%9B%E4%BA%8B%E6%BC%94%E4%B9%A0%22+%22%E9%98%B2%E5%8D%AB%22+%22%E5%9C%B0%E7%BC%98%E5%86%B2%E7%AA%81%22&hl=zh-CN&gl=CN&ceid=CN:zh-Hans', 'type': 'rss'},
    ],
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
    'tech':       ['核心突破', '技术细节', '产业影响', '未来展望'],
    'economy':    ['宏观趋势', '政策动向', '全球影响', '结构变化'],
    'politics':   ['外交动态', '政策要点', '国际反应', '战略意义'],
    'military':   ['装备特性', '战略威慑', '地区影响', '安全格局'],
    'humanities': ['人物事迹', '社会影响', '文化价值', '历史意义'],
}

LABEL_KEYWORDS = {
    '核心突破':   ['突破', '发布', '首次', '创新', '领先', '超越', '刷新', '记录', '里程碑', '首创'],
    '技术细节':   ['技术', '算法', '模型', '参数', '架构', '芯片', 'GPU', '训练', '推理', '开源'],
    '产业影响':   ['产业', '行业', '落地', '应用', '商业化', '投资', '融资', '生态', '合作'],
    '未来展望':   ['未来', '趋势', '预测', '预计', '规划', '愿景', '前景', '方向'],
    '宏观趋势':   ['GDP', '增长', '趋势', '指数', '下降', '恢复', '复苏', '转型', '结构', '制造业'],
    '政策动向':   ['政策', '央行', '财政部', '法规', '调控', '利率', '监管', '改革', '开放'],
    '全球影响':   ['全球', '出口', '进口', '贸易', '供应链', '跨国', '美元', '欧元', 'IMF', '国际'],
    '结构变化':   ['产业', '升级', '转型', '结构', '劳动力', '数字化', '绿色', '碳', '能源'],
    '外交动态':   ['外交', '访问', '会见', '会谈', '磋商', '对话', '声明', '联合', '签署'],
    '政策要点':   ['政策', '法规', '条例', '改革', '部署', '出台', '印发', '实施', '推进'],
    '国际反应':   ['回应', '反应', '表态', '声明', '关注', '谴责', '支持', '反对', '呼吁'],
    '战略意义':   ['战略', '格局', '秩序', '同盟', '博弈', '竞争', '合作', '对抗', '平衡'],
    '装备特性':   ['装备', '武器', '战机', '军舰', '导弹', '雷达', '系统', '无人机', '装甲'],
    '战略威慑':   ['战略', '威慑', '防御', '部署', '演习', '基地', '联盟', '条约', '核'],
    '地区影响':   ['地区', '冲突', '紧张', '领土', '海域', '边界', '对峙', '谈判', '停火'],
    '安全格局':   ['安全', '威胁', '风险', '国防', '军备', '平衡', '监控', '侦察', '情报'],
    '人物事迹':   ['人物', '故事', '经历', '成就', '贡献', '获奖', '荣誉', '传奇', '记录'],
    '社会影响':   ['影响', '改变', '推动', '引领', '启发', '激励', '争议', '热议', '关注'],
    '文化价值':   ['文化', '艺术', '价值', '遗产', '传承', '创新', '思想', '精神', '理念'],
    '历史意义':   ['历史', '时代', '里程碑', '标志', '开创', '先锋', '先驱', '意义'],
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
            # 清理常见冗余：移除标题末尾的 " - SourceName"
            if ' - ' in title[-40:]:
                parts = title.rsplit(' - ', 1)
                if len(parts[1]) <= 20:
                    title = parts[0].strip()
            if len(title) < 10 or len(title) > 120:
                continue

            source_name = 'GoogleNews'
            if src_el:
                src_text = XML_CLEAN_RE.sub('', src_el.text).strip()
                if src_text and len(src_text) <= 30:
                    source_name = src_text

            # 提取原始文章URL：优先从 source 标签的 url 属性获取
            original_url = '#'
            if src_el and src_el.get('url'):
                original_url = src_el['url']
            if original_url == '#' and link_el:
                url_text = link_el.text.strip()
                if url_text.startswith('http'):
                    original_url = url_text

            news_list.append({
                'title': title,
                'source': source_name,
                'url': original_url,
            })
            if len(news_list) >= 6:
                break
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



# ============================================================
# DeepSeek AI 集成
# ============================================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
AI_ENABLED = bool(DEEPSEEK_API_KEY)


def call_deepseek(messages, temperature=0.3, max_tokens=2000):
    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=90
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"  DeepSeek API 错误 {resp.status_code}: {resp.text[:150]}")
            return None
    except Exception as e:
        print(f"  DeepSeek API 调用失败: {str(e)[:100]}")
        return None


def ai_batch_summarize(articles):
    if not articles:
        return {}

    lines = []
    for art in articles:
        body = art.get('body', '')[:600]
        body_display = body if body else "（无正文，请根据标题和来源推断新闻内容）"
        lines.append(
            f"[{art['index']}] 标题：{art['title']}\n"
            f"    来源：{art['source']}\n"
            f"    正文：{body_display}"
        )
    articles_text = "\n\n".join(lines)

    prompt = f"""你是一个专业新闻编辑。请为以下每篇新闻生成一句精炼的摘要（30-60字），准确概括新闻核心内容。

对于没有正文的新闻，请根据标题和来源合理推断其报道内容，生成可信的摘要。

严格返回JSON数组格式，不要任何额外文字：
[
  {{"index": 0, "summary": "摘要内容。"}},
  {{"index": 1, "summary": "摘要内容。"}}
]

新闻列表：
{articles_text}"""

    result = call_deepseek(
        [
            {"role": "system", "content": "你是专业新闻编辑。只返回JSON数组，不要解释。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4000
    )

    if not result:
        return {}

    try:
        json_match = re.search(r'\[[\s\S]*\]', result)
        if json_match:
            summaries = json.loads(json_match.group())
            return {int(s['index']): s['summary'] for s in summaries}
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"  解析AI摘要JSON失败: {str(e)[:80]}")

    return {}


def ai_daily_summary(summaries_by_cat):
    if not summaries_by_cat:
        return None

    context_parts = []
    order = ['economy', 'tech', 'politics', 'military', 'humanities']
    for cat in order:
        items = summaries_by_cat.get(cat, [])
        if not items:
            continue
        cat_name = CATEGORY_NAMES.get(cat, cat)
        context_parts.append(f"【{cat_name}】")
        for i, n in enumerate(items, 1):
            context_parts.append(f"  {i}. {n['title']}")
            context_parts.append(f"     摘要：{n.get('overview', '')}")
        context_parts.append("")

    context = "\n".join(context_parts)

    prompt = f"""你是资深新闻分析师。基于以下今日新闻摘要，撰写一份每日深度总结。

要求：
- 按经济、科技、政治与国际、军事安全、人文人物5个维度分析，每维度写1小段（1-2句精炼洞察）
- 关注趋势关联和深层逻辑，不要罗列标题
- 经济层面聚焦全球宏观和中国经济发展
- 科技层面侧重AI与前沿技术突破
- 政治层面关注国际关系和中国政策走向
- 军事层面侧重新型装备与国际冲突态势
- 人文层面关注具体人物故事及其时代意义
- 最后写1句综合判断
- 严格使用以下HTML格式输出（每行一个p标签）：

<p class="summary-line"><strong>经济层面</strong>：洞察内容...</p>
<p class="summary-line"><strong>科技层面</strong>：洞察内容...</p>
<p class="summary-line"><strong>政治与国际层面</strong>：洞察内容...</p>
<p class="summary-line"><strong>军事安全层面</strong>：洞察内容...</p>
<p class="summary-line"><strong>人文人物层面</strong>：洞察内容...</p>
<p class="summary-line">综合来看，（1-2句总结）。</p>

今日新闻：
{context}"""

    result = call_deepseek(
        [
            {"role": "system", "content": "你是资深新闻分析师。严格输出HTML格式，不要额外解释。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=2000
    )

    return result


def _build_ai_details(overview, cat):
    if not overview:
        return [{'label': '核心内容', 'content': '详情请关注后续报道。'}]

    sentences = re.split(r'[。！？]', overview)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]

    labels = DETAIL_LABELS.get(cat, ['核心内容', '重要动态'])
    details = []
    for i, s in enumerate(sentences[:2]):
        details.append({'label': labels[i] if i < len(labels) else '关键信息', 'content': s + '。'})

    if not details and sentences:
        details.append({'label': labels[0], 'content': sentences[0] + '。'})

    return details[:2]


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
        return [{'label': '核心内容', 'content': '详情请关注后续报道。'}]

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


def _fetch_article_body(news_item):
    try:
        if news_item['url'] == '#':
            return ''
        resp = requests.get(news_item['url'], headers=HEADERS, timeout=10)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        text = extract_article_text(resp.text, news_item['source'], news_item['url'])
        return text
    except Exception as e:
        return ''


def enrich_all_news(news_data):
    """批量抓取正文，用AI生成摘要和细节"""
    all_tasks = []
    for cat, items in news_data.items():
        for item in items:
            all_tasks.append((cat, item))

    print(f"\n📥 正在抓取 {len(all_tasks)} 篇新闻正文...")

    article_results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_fetch_article_body, item): (cat, item)
            for cat, item in all_tasks
        }
        for future in as_completed(futures):
            cat, item = futures[future]
            try:
                body_text = future.result()
                article_results.append((cat, item, body_text))
                status = '✅' if body_text else '(no body)'
                print(f"  {status} [{CATEGORY_NAMES.get(cat, cat)}] {item['title'][:30]}")
            except Exception as e:
                article_results.append((cat, item, ''))
                print(f"  X [{CATEGORY_NAMES.get(cat, cat)}] {item['title'][:30]}: {str(e)[:30]}")

    articles_for_ai = []
    for idx, (cat, item, body_text) in enumerate(article_results):
        articles_for_ai.append({
            'index': idx,
            'cat': cat,
            'title': item['title'],
            'source': item['source'],
            'url': item['url'],
            'body': body_text,
        })

    ai_summaries = {}
    if AI_ENABLED:
        print(f"\n:robot: 正在调用 DeepSeek AI 生成 {len(articles_for_ai)} 篇文章摘要...")
        ai_summaries = ai_batch_summarize(articles_for_ai)
        if ai_summaries:
            print(f"  OK AI摘要生成完成 ({len(ai_summaries)}篇)")
        else:
            print(f"  WARN AI摘要生成失败，回退到传统方法")

    enriched = []
    for art in articles_for_ai:
        if ai_summaries and art['index'] in ai_summaries:
            overview = ai_summaries[art['index']]
        elif art['body']:
            overview = summarize_article(art['body'])
        else:
            overview = ''

        if not overview:
            overview = _build_title_overview(art['title'], art['cat'])

        details = _build_ai_details(overview, art['cat'])

        enriched.append({
            'cat': art['cat'],
            'title': art['title'],
            'source': art['source'],
            'url': art['url'],
            'overview': overview,
            'details': details,
        })

    enriched.sort(key=lambda x: (
        ['tech', 'economy', 'politics', 'military', 'humanities'].index(x['cat'])
    ))
    return enriched


THEME_CLUSTERS = {

    '政策信号与治理方向': {
        'keywords': ['政策', '国务院', '发改委', '财政部', '央行', '会议', '改革', '制度', '法规', '条例',
                   '意见', '方案', '规划', '部署', '出台', '印发', '审议', '全国人大', '政协',
                   '高质量发展', '现代化', '体系', '机制', '中国式现代化', '对外开放'],
        'desc_prefix': '政策层面',
    },

    '全球经济与中国发展': {
        'keywords': ['GDP', '增长', '经济', '贸易', '制造业', '产业链', '供应链',
                   '全球化', '跨国', '出口', '进口', '通胀', '货币政策', '央行',
                   '财政', '税收', '数字化', '绿色', '转型', '升级',
                   '东盟', '一带一路', '金砖', 'IMF', '世界银行'],
        'desc_prefix': '经济层面',
    },

    '科技突破与AI变革': {
        'keywords': ['AI', '人工智能', '大模型', '算法', '芯片', 'GPU', '算力', '量子', '卫星', '航天',
                   '自动驾驶', '机器人', '5G', '6G', '数字化', '技术', '创新', '突破',
                   '研发', '发布', '迭代', '升级', '模型', '系统', '架构',
                   '半导体', '集成电路', '人形机器人', '脑机'],
        'desc_prefix': '科技层面',
    },

    '国际格局与地缘动态': {
        'keywords': ['美国', '中美', '欧盟', '北约', '俄罗斯', '日本', '韩国', '朝鲜', '台湾', '南海',
                   '制裁', '关税', '贸易战', '谈判', '协定', '峰会', '访问', '声明', '军事', '国防',
                   '演习', '装备', '部队', '安全', '威胁', '风险', '冲突', '争端', '主权', '领土',
                   '外交', '联合国', 'G7', 'G20', '地缘'],
        'desc_prefix': '国际层面',
    },

    '社会人文与人物故事': {
        'keywords': ['人物', '故事', '遗产', '文化', '艺术', '教育', '体育',
                   '公益', '慈善', '创新', '创业', '科学家', '艺术家', '作家',
                   '学者', '企业家', '领袖', '获奖', '荣誉', '传承', '保护',
                   '精神', '价值', '影响', '贡献', '时代'],
        'desc_prefix': '社会与人文层面',
    },
}

THEME_INSIGHT_CONCISE = {
    '政策信号与治理方向': [
        '决策层在{angle}方向持续发力，配套措施有望密集落地，对{impact_group}而言意味着制度红利与规则重塑。',
        '{angle}相关部署是战略框架的有机组成，后续细则出台节奏将直接影响行业预期与产业布局。',
    ],
    '全球经济与中国发展': [
        '{angle}成为当前全球经济格局演变的关键变量，各国经济政策的协同与分化值得密切关注。',
        '{angle}领域边际变化折射全球产业链深度重构，结构性调整机遇与挑战并存。',
    ],
    '科技突破与AI变革': [
        '{angle}方向加速演进，AI技术正在从单点突破转向系统性变革，对产业和社会的影响远超预期。',
        '{angle}技术突破是产业智能化升级的缩影，技术先发优势正在转化为国家竞争力。',
    ],
    '国际格局与地缘动态': [
        '{angle}动向反映国际力量对比持续调整，地缘政治风险已成为全球经济的核心不确定因素。',
        '围绕{angle}的多方博弈短期内将加剧紧张态势，中长期可能重塑全球战略平衡格局。',
    ],
    '社会人文与人物故事': [
        '{angle}领域的标杆人物与事件折射社会价值取向的深层变化，个体故事中蕴含着时代精神。',
        '{angle}议题凸显人文关怀与社会进步的共生关系，在快速发展的时代中坚守人性温度更显珍贵。',
    ],
}


def compose_daily_summary(enriched_news):
    """每日深度总结：优先AI生成，失败则回退传统方法"""
    if not enriched_news:
        return '<p>今日暂无足够信息生成深度总结，请浏览各栏目新闻卡片了解详情。</p>'

    if AI_ENABLED:
        by_cat = {}
        for n in enriched_news:
            by_cat.setdefault(n['cat'], []).append(n)
        print("\n🤖 正在调用 AI 生成每日深度总结...")
        ai_result = ai_daily_summary(by_cat)
        if ai_result:
            print("  ✅ AI深度总结生成完成")
            return ai_result
        print("  ⚠️ AI深度总结失败，使用传统方法")

    return _compose_daily_summary_legacy(enriched_news)


def _compose_daily_summary_legacy(enriched_news):
    """传统总结：按主题归类，每层1-2句核心分析（fallback）"""
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
        '综合来看，今日各领域动态共同指向一个深度重构的世界——AI技术正在改写产业规则、'
        '全球经济在分化中寻找新均衡、国际秩序在多极博弈中持续重组、'
        '而个体的坚守与创造则为时代注入了不可替代的人文温度。'
        '在这多重转型叠加的关键时期，跨领域的系统性思维，或许比单一视角更能接近真相。'
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
        escaped_url = data['url']
        js_parts.append(
            f"{idx}: {{title: \"{escaped_title}\", source: \"{escaped_source}\", "
            f"url: \"{escaped_url}\", cat: \"{data['cat']}\", "
            f"overview: \"{escaped_overview}\", "
            f"details: {details_json}}}"
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
        '中美高层对话释放管控分歧积极信号',
        '外交部就国际热点问题阐述中方立场',
        '王毅出席联合国大会一般性辩论并发表讲话',
        '国务院常务会议部署深化改革开放新举措',
        '中欧领导人会晤推动双边关系稳定发展',
        '金砖国家扩员后首次峰会聚焦全球治理改革',
        '中方在安理会就巴以问题提出四点主张',
        '国务院发布优化外商投资环境行动方案',
        '中国与东盟自贸区3.0版谈判取得实质进展',
        '国防白皮书阐释新时代中国防御性国防政策',
        '上合组织峰会签署多项安全合作文件',
        '全国人大常委会通过新修订的对外关系法',
        '中国与太平洋岛国合作论坛达成多项共识',
        '国际原子能机构总干事访华讨论核安全合作',
    ],
    'economy': [
        '世行上调中国经济增长预期至百分之五点二',
        'IMF报告称亚洲仍是全球经济增长主要引擎',
        '我国制造业PMI连续三个月位于扩张区间',
        '国务院出台促进民营经济发展壮大新措施',
        '前五个月我国与共建一带一路国家贸易增长',
        '全球供应链重构背景下中国产业链韧性凸显',
        '央行行长阐述货币政策调控框架转型思路',
        '中国与沙特签署绿色能源合作协议',
        '东盟连续四年保持中国最大贸易伙伴地位',
        '服务业增加值占GDP比重突破百分之五十五',
        '全国统一电力市场体系建设方案出台',
        '全球经济增速分化加剧，南南合作重要性提升',
        '中国经济转型：从高速增长转向高质量发展',
        '政治局会议分析研究当前经济形势和经济工作',
    ],
    'tech': [
        '国产AI大模型在多项国际评测中登顶',
        'OpenAI发布新一代多模态模型能力引关注',
        '中国科学家实现量子纠错重大技术突破',
        '全球AI芯片竞争加剧，算力基础设施投资激增',
        '华为发布盘古大模型最新版本，性能大幅提升',
        '特斯拉人形机器人量产计划引发产业热议',
        'AI制药公司利用深度学习加速新药研发',
        '中美科技竞争进入AI基础设施新阶段',
        '中国脑机接口技术首次实现人脑信号实时解码',
        '全球首款AI原生操作系统发布颠覆交互方式',
        '可控核聚变实验取得里程碑式进展',
        'AI安全治理框架成为联合国科技议程重点',
        '全球半导体投资热潮背后的地缘政治博弈',
        '大模型技术向垂直行业渗透速度超预期',
    ],
    'military': [
        '美军第六代战机NGAD项目技术细节曝光',
        '中国新型隐身舰载机完成首次航母起降测试',
        '俄乌冲突中无人机战术运用引发军事变革讨论',
        '高超音速武器竞赛加速全球战略平衡重塑',
        '北约启动新一轮军事现代化计划聚焦网络战',
        '中国电磁弹射技术实现关键突破',
        '波斯湾局势持续紧张多国增兵加强军事存在',
        '韩国自主研发第五代战机KF-21进入量产',
        '南海海域军事活动频繁引发区域安全关注',
        '激光武器技术从实验室走向实战部署',
        '太空军事化趋势加剧多国组建太空部队',
        '新一代洲际导弹试射成功展示战略威慑能力',
        'AI军事应用伦理问题引发国际激烈辩论',
        '台湾海峡军事态势进入新调整期',
    ],
    'humanities': [
        '诺贝尔文学奖揭晓引发关于文学价值的全球讨论',
        '知名企业家捐赠百亿成立教育基金会',
        '敦煌研究院名誉院长樊锦诗：一生守护莫高窟',
        '残奥冠军转型社会企业家推动无障碍事业',
        '中国非遗传承人获联合国教科文组织表彰',
        '华尔街传奇投资人查理芒格生前最后一次专访',
        '青年科学家放弃海外高薪回国创业故事',
        '太行山深处的支教老师：二十年坚守点亮希望',
        '中国女导演首次摘得戛纳电影节金棕榈奖',
        '考古学家在三星堆遗址发现前所未有的文物',
        '全球气候活动家在联合国气候大会上的演讲',
        '中国医学专家团队攻克罕见病治疗难题',
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


def _build_title_overview(title, cat):
    """从标题生成简洁概述（AI不可用时的fallback）"""
    today_str = datetime.now().strftime("%m月%d日")
    templates = {
        'tech':       f'{today_str}，{title}。这一进展是AI与前沿科技领域的重要动态。',
        'economy':    f'{today_str}，{title}。该消息折射全球宏观经济格局的深层变化。',
        'politics':   f'{today_str}，{title}。此举对国际关系和外交格局具有重要信号意义。',
        'military':   f'{today_str}，{title}。该动态反映出全球军事安全格局的新演变。',
        'humanities': f'{today_str}，{title}。这一人物事件折射出文化与社会层面的深层脉动。',
    }
    return templates.get(cat, f'{today_str}，{title}。该新闻值得关注。')


def generate_fallback_overview(title, cat):
    """为备用新闻生成概述（fallback）"""
    today_str = datetime.now().strftime("%m月%d日")
    templates = {
        'tech':       f'{today_str}，"{title}"取得重要进展。在AI技术快速迭代的背景下，这一突破将对相关产业格局产生深远影响。',
        'economy':    f'{today_str}，"{title}"引发广泛关注。在全球经济格局深度调整之际，该动态对宏观经济走向具有参考价值。',
        'politics':   f'{today_str}，"{title}"引发各方关注。当前国际形势下，这一事件对大国关系和地区格局具有深远影响。',
        'military':   f'{today_str}，"{title}"是国际军事安全领域的重要动态，反映了当前全球安全格局的持续演变。',
        'humanities': f'{today_str}，"{title}"。这一人物故事折射出当代社会的价值追求与文化自觉，具有广泛的启发意义。',
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
