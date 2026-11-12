"""数据来源：GitHub 三条公开通道。

A. github.com/trending      官方涨星口径（网页，抓 HTML）
B. Search API  created:>N   新项目爆发榜
C. Search API  pushed:>N    老项目活跃榜

token 依次从 环境变量 / config.json / gh CLI 里找；都没有就走匿名，
匿名每小时 60 次，够跑一期（候选池控在 20-24 个）。
"""
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse

import requests

API = "https://api.github.com"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(HERE, "data", "cache")


# ---------------------------------------------------------------- token

def find_token():
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PAT"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip(), f"环境变量 {k}"
    cfg = os.path.join(HERE, "config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, encoding="utf-8") as f:
                v = (json.load(f).get("gh_token") or "").strip()
            if v and not v.startswith("在这里"):
                return v, "config.json"
        except Exception:
            pass
    if shutil.which("gh"):
        try:
            v = subprocess.run(["gh", "auth", "token"], capture_output=True,
                               text=True, timeout=8).stdout.strip()
            if v:
                return v, "gh CLI"
        except Exception:
            pass
    return None, "无（匿名）"


def _headers(token):
    h = {"Accept": "application/vnd.github+json",
         "User-Agent": "gh-wechat-digest/1.0"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get(url, token=None, params=None, timeout=20, tries=2):
    """匿名时搜索接口是 10 次/分钟，撞上了就等一轮再试，别直接放弃。"""
    is_search = "/search/" in url
    for i in range(tries):
        try:
            r = requests.get(url, headers=_headers(token), params=params, timeout=timeout)
            if r.status_code == 403 and "rate limit" in r.text.lower():
                if is_search and not token and i < tries - 1:
                    time.sleep(7)
                    continue
                return None
            if r.status_code >= 400:
                return None
            return r
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.5)
    return None


def rate_left(token=None):
    r = get(f"{API}/rate_limit", token)
    if r is None:
        return None
    d = r.json().get("resources", {})
    return {"core": d.get("core", {}).get("remaining"),
            "search": d.get("search", {}).get("remaining"),
            "reset": d.get("core", {}).get("reset")}


# ---------------------------------------------------------------- A. trending

_NUM = re.compile(r"([\d,]+)")


def _n(s):
    return int(re.sub(r"[^\d]", "", s) or 0) if s else 0


def trending(since="daily"):
    """解析 github.com/trending。结构一变就返回空，先打印一条 article 看。"""
    r = get(f"https://github.com/trending?since={since}")
    if r is None:
        return []
    out = []
    for art in re.findall(r'<article class="Box-row">(.*?)</article>', r.text, re.S):
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", art, re.S)
        if not h2:
            continue
        hm = re.search(r'href="/([^"/]+)/([^"/]+)"', h2.group(1))
        if not hm:
            continue
        owner, name = hm.group(1), hm.group(2)
        if owner in ("sponsors", "login", "orgs", "topics"):
            continue
        dm = re.search(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', art, re.S)
        desc = re.sub(r"<[^>]+>", "", dm.group(1)).strip() if dm else ""
        lm = re.search(r'itemprop="programmingLanguage">([^<]+)<', art)
        gm = re.search(r"([\d,]+)\s+stars\s+(today|this week|this month)", art)

        def cnt(kind):
            m = re.search(rf'/{kind}"[^>]*>(.*?)</a>', art, re.S)
            return _n(re.sub(r"<[^>]+>", "", m.group(1)).strip()) if m else 0

        out.append({
            "full_name": f"{owner}/{name}", "owner": owner, "name": name,
            "desc": desc, "lang": lm.group(1).strip() if lm else "",
            "stars": cnt("stargazers"), "forks": cnt("forks"),
            "gained": _n(gm.group(1)) if gm else 0,
            "since": since, "source": "trending",
        })
    return out


# ---------------------------------------------------------------- B/C. search

def _map(it, source, since=""):
    return {
        "full_name": it["full_name"], "owner": it["owner"]["login"], "name": it["name"],
        "desc": it.get("description") or "", "lang": it.get("language") or "",
        "stars": it.get("stargazers_count", 0), "forks": it.get("forks_count", 0),
        "gained": 0, "since": since, "source": source,
        "created_at": it.get("created_at"), "pushed_at": it.get("pushed_at"),
        "topics": it.get("topics") or [], "archived": it.get("archived", False),
        "license": ((it.get("license") or {}).get("spdx_id") or ""),
        "open_issues": it.get("open_issues_count"),
        "size_kb": it.get("size"), "homepage": it.get("homepage") or "",
        "watchers": it.get("watchers_count", 0),
    }


def search(q, sort="stars", per_page=25, token=None, source="search"):
    r = get(f"{API}/search/repositories", token,
            params={"q": q, "sort": sort, "order": "desc", "per_page": per_page})
    if r is None:
        return []
    try:
        items = r.json().get("items", [])
    except Exception:
        return []
    return [_map(it, source, q) for it in items]


def search_new(days=30, min_stars=400, token=None, per_page=25):
    from datetime import datetime, timedelta, timezone
    d = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return search(f"created:>{d} stars:>={min_stars}", "stars", per_page, token, "new")


def search_hot(days=7, min_stars=1000, token=None, per_page=25):
    from datetime import datetime, timedelta, timezone
    d = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return search(f"pushed:>{d} stars:>={min_stars}", "updated", per_page, token, "hot")


# ---------------------------------------------------------------- 详情 / README

def detail(full_name, token=None):
    """补详情。核心额度用光时走 search 的 `repo:` 语法 —— 搜索额度跟核心是
    分开算的，这条兜底能让整个流程在 0 核心额度下照样跑完。"""
    r = get(f"{API}/repos/{full_name}", token)
    if r is None:
        rr = get(f"{API}/search/repositories", token,
                 params={"q": f"repo:{full_name}", "per_page": 1}, tries=3)
        if rr is None:
            return {}
        try:
            items = rr.json().get("items", [])
        except Exception:
            return {}
        if not items:
            return {}
        it = items[0]
        return {
            "created_at": it.get("created_at"), "pushed_at": it.get("pushed_at"),
            "topics": it.get("topics") or [], "archived": it.get("archived", False),
            "license": ((it.get("license") or {}).get("spdx_id") or ""),
            "open_issues": it.get("open_issues_count"), "size_kb": it.get("size"),
            "homepage": it.get("homepage") or "", "lang": it.get("language") or "",
            "stars": it.get("stargazers_count"), "forks": it.get("forks_count"),
            "desc": it.get("description") or "", "default_branch": it.get("default_branch") or "main",
            "has_discussions": bool(it.get("has_discussions")),
            "_via": "search",
        }
    it = r.json()
    return {
        "created_at": it.get("created_at"), "pushed_at": it.get("pushed_at"),
        "topics": it.get("topics") or [], "archived": it.get("archived", False),
        "license": ((it.get("license") or {}).get("spdx_id") or ""),
        "open_issues": it.get("open_issues_count"), "size_kb": it.get("size"),
        "homepage": it.get("homepage") or "", "lang": it.get("language") or "",
        "stars": it.get("stargazers_count"), "forks": it.get("forks_count"),
        "desc": it.get("description") or "", "default_branch": it.get("default_branch") or "main",
        "has_discussions": bool(it.get("has_discussions")),
        "subscribers": it.get("subscribers_count"),
        "_via": "core",
    }


README_NAMES = ("README.md", "readme.md", "Readme.md", "README.rst", "README",
                "README.zh-CN.md", "README_CN.md", "docs/README.md")


def readme(full_name, token=None, branch="HEAD"):
    """raw.githubusercontent.com 优先（不花额度），失败才打 API。
    文件名和分支都不固定，所以按候选表逐个试，命中即止。"""
    for br in (branch, "HEAD", "main", "master"):
        for nm in README_NAMES:
            rr = get(f"https://raw.githubusercontent.com/{full_name}/{br}/{nm}", timeout=12)
            if rr is not None and rr.text.strip():
                return rr.text
    r = get(f"{API}/repos/{full_name}/readme", token)
    if r is not None:
        try:
            import base64
            return base64.b64decode(r.json().get("content", "")).decode("utf-8", "ignore")
        except Exception:
            pass
    return ""


# ---------------------------------------------------------------- 工具

def og_image(full_name):
    return f"https://opengraph.githubassets.com/1/{full_name}"


def repo_url(full_name):
    return f"https://github.com/{full_name}"


def cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def load_json(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
