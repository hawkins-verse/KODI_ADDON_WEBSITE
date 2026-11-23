# language: Python 3, file: default.py
import sys
import os
import json
import time
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
from concurrent.futures import ThreadPoolExecutor, as_completed

SERVER = "https://allinoneextractor-production.up.railway.app"

# Apne GitHub repo ka Raw URL yahan daalna (branch main ya master)
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/hawkins-verse/YOUR_REPO_NAME/main"

SITES = [
    {"id": "movies4u",    "name": "Movies4u",     "api": "/movies4u-api",
     "home_ep": None, "home_key": None,
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "4khdhub",     "name": "4KHDHUB",      "api": "/4khdhub-api",
     "home_ep": "/api/latest", "home_key": None,
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "hdhub4u",     "name": "HdHub4U",      "api": "/hdhub4u-api",
     "home_ep": "/api/latest", "home_key": None,
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "moviesdrive", "name": "MoviesDrive",  "api": "/drive-api",
     "home_ep": None, "home_key": None,
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "desire",      "name": "DesireMovies", "api": "/desire-api",
     "home_ep": "/api/home", "home_key": "posts",
     "servers": ["HUBCLOUD", "GDFLIX", "MULTICLOUD"], "extract_mode": "standard"},
    {"id": "zink",        "name": "ZinkMovies",   "api": "/zink-api",
     "home_ep": "/api/posters", "home_key": "posters",
     "servers": ["HUBCLOUD", "GDFLIX"], "extract_mode": "standard"},
    {"id": "bolly",       "name": "BollyFlix",    "api": "/bolly-api",
     "home_ep": "/api/home", "home_key": "posts",
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "ssr",         "name": "SSRMovies",    "api": "/ssr-api",
     "home_ep": "/api/home", "home_key": "items",
     "dynamic_servers": True, "extract_mode": "ssr"},
    {"id": "cinevood",    "name": "CineVood",     "api": "/cinevood-api",
     "home_ep": "/api/homeposters", "home_key": None,
     "servers": ["HUBCLOUD", "GDFLIX", "FILEPRESS", "OXXFILE"], "extract_mode": "standard"},
    {"id": "7starhd",     "name": "7StarHD",      "api": "/7starhd-api",
     "home_ep": "/api/home", "home_key": "items",
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "moviesmod",   "name": "MoviesMod",    "api": "/moviesmod-api",
     "home_ep": "/api/home", "home_key": "items",
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
    {"id": "uhdmovies",   "name": "UHDMovies",    "api": "/uhdmovies-api",
     "home_ep": "/api/home", "home_key": "items",
     "dynamic_servers": True, "extract_mode": "uhd"},
    {"id": "topmovies",   "name": "TopMovies",    "api": "/topmovies-api",
     "home_ep": "/api/home", "home_key": "items",
     "servers": ["HUBCLOUD"], "extract_mode": "standard"},
]

SITE_BADGES = {
    "movies4u":    "🎬",
    "4khdhub":     "🔥",
    "hdhub4u":     "👑",
    "moviesdrive": "🚗",
    "desire":      "💠",
    "zink":        "⚡",
    "bolly":       "🎭",
    "ssr":         "🌟",
    "cinevood":    "🎥",
    "7starhd":     "⭐",
    "moviesmod":   "🎞️",
    "uhdmovies":   "💎",
    "topmovies":   "🏆",
}

SEARCH_ALL_SITES = [s["id"] for s in SITES]

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
WINDOW = xbmcgui.Window(10000)

ADDON_ID = "plugin.video.allex_tractors"
HISTORY_MAX = 300
HISTORY_DAYS = 50


def _profile_dir():
    path = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/")
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception:
            pass
    return path


BOOKMARK_FILE = os.path.join(_profile_dir(), "bookmarks.json")
HISTORY_FILE = os.path.join(_profile_dir(), "history.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}


# ============================================================
# HTTP & LINK HEALTH CHECK
# ============================================================
def http_get(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        xbmc.log(f"[AE] GET error: {url[:90]} -> {e}", xbmc.LOGERROR)
        return None


def http_post(url, data, timeout=180):
    try:
        body = json.dumps(data).encode("utf-8")
        headers = {**HEADERS, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        xbmc.log(f"[AE] POST error: {e}", xbmc.LOGERROR)
        return None


def is_link_alive(url):
    if not url or not url.startswith("http"):
        return False
    try:
        req = urllib.request.Request(
            url, headers={**HEADERS, "Range": "bytes=0-1"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "text/html" in ctype:
                return False
            return r.status in (200, 206)
    except Exception:
        return False


def get_site(site_id):
    return next((s for s in SITES if s["id"] == site_id), None)


def _get_poster(item):
    return item.get("img") or item.get("poster") or item.get("image") or ""


def _make_key(title, ep="", site_id=""):
    return f"{site_id}|{(title or '').strip().lower()}|{(ep or 'Movie').strip().lower()}"


# ============================================================
# 1-CLICK GITHUB AUTO-UPDATER
# ============================================================
def update_addon():
    if "YOUR_REPO_NAME" in GITHUB_RAW_BASE:
        xbmcgui.Dialog().ok("GitHub Setup Pending", "default.py mein GITHUB_RAW_BASE ke andar apna GitHub repo naam set karo.")
        return

    addon_dir = xbmcvfs.translatePath(f"special://home/addons/{ADDON_ID}/")
    files = ["default.py", "service.py", "addon.xml"]
    updated = []

    pDialog = xbmcgui.DialogProgress()
    pDialog.create("Updating Addon", "GitHub se latest files download ho rahi hain...")

    for i, fname in enumerate(files):
        pDialog.update(int((i / len(files)) * 100), f"Downloading {fname}...")
        raw_url = f"{GITHUB_RAW_BASE.rstrip('/')}/{fname}?t={int(time.time())}"
        content = http_get(raw_url, timeout=15)
        if content and len(content) > 50:
            try:
                target_path = os.path.join(addon_dir, fname)
                with xbmcvfs.File(target_path, 'w') as f:
                    f.write(content)
                updated.append(fname)
            except Exception as e:
                xbmc.log(f"[AE] Update write err {fname}: {e}", xbmc.LOGERROR)

    pDialog.close()

    if updated:
        xbmcgui.Dialog().ok(
            "Update Complete!",
            f"Updated: {', '.join(updated)}\n\nChanges apply hone ke liye Kodi ek baar restart kar lo."
        )
    else:
        xbmcgui.Dialog().notification("Update Failed", "GitHub se files nahi milin")


# ============================================================
# ITEM BUILDERS
# ============================================================
def make_movie_item(title, poster="", site_name=""):
    li = xbmcgui.ListItem(label=title)
    info = {"title": title, "mediatype": "movie"}
    if site_name:
        info["studio"] = site_name
    li.setInfo("video", info)
    if poster:
        li.setArt({"poster": poster, "thumb": poster, "icon": poster})
    return li


def make_action_item(label, title=None):
    li = xbmcgui.ListItem(label=label)
    li.setInfo("video", {"title": title or label, "mediatype": "video"})
    return li


# ============================================================
# HISTORY (50 din)
# ============================================================
def load_history():
    try:
        if not os.path.exists(HISTORY_FILE):
            return {"searches": [], "links": []}
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
            d.setdefault("searches", [])
            d.setdefault("links", [])
    except Exception:
        return {"searches": [], "links": []}

    cutoff = time.time() - (HISTORY_DAYS * 24 * 60 * 60)
    d["searches"] = [s for s in d["searches"] if s.get("t", 0) >= cutoff]
    d["links"] = [l for l in d["links"] if l.get("t", 0) >= cutoff]
    return d


def save_history(data):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def add_search_history(query, site_id):
    if not query or not site_id:
        return
    d = load_history()
    d["searches"] = [s for s in d["searches"]
                     if not (s.get("q") == query and s.get("sid") == site_id)]
    d["searches"].insert(0, {"q": query, "sid": site_id, "t": time.time()})
    d["searches"] = d["searches"][:HISTORY_MAX]
    save_history(d)


def add_link_history(title, url, site_id, quality="", server="", size="", ep="", meta=None):
    if not url:
        return
    key = _make_key(title, ep, site_id)
    d = load_history()
    d["links"] = [l for l in d["links"] if l.get("key") != key and l.get("url") != url]
    entry = {
        "key": key, "title": title, "url": url, "sid": site_id,
        "quality": quality, "server": server, "size": size, "ep": ep,
        "t": time.time(),
    }
    if meta:
        entry["meta"] = meta
    d["links"].insert(0, entry)
    d["links"] = d["links"][:HISTORY_MAX]
    save_history(d)


# ============================================================
# BOOKMARKS (smart resume + auto-refresh meta)
# ============================================================
def load_bookmarks():
    try:
        if not os.path.exists(BOOKMARK_FILE):
            return {"bookmarks": []}
        with open(BOOKMARK_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
            d.setdefault("bookmarks", [])
            return d
    except Exception:
        return {"bookmarks": []}


def save_bookmarks(data):
    try:
        with open(BOOKMARK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def upsert_bookmark(key, url, title, server="", ep="", meta=None):
    if not url or not title:
        return 0
    d = load_bookmarks()
    for b in d["bookmarks"]:
        if (key and b.get("key") == key) or b.get("url") == url:
            b["key"] = key
            b["url"] = url
            b["title"] = title
            if server:
                b["server"] = server
            if ep:
                b["ep"] = ep
            if meta:
                b["meta"] = meta
            b["t"] = time.time()
            save_bookmarks(d)
            return int(b.get("position", 0))

    d["bookmarks"].insert(0, {
        "key": key, "url": url, "title": title, "server": server,
        "ep": ep, "meta": meta or {}, "position": 0, "total": 0, "t": time.time(),
    })
    d["bookmarks"] = d["bookmarks"][:80]
    save_bookmarks(d)
    return 0


# ============================================================
# AUTO-REFRESH EXPIRED LINK
# ============================================================
def _call_extract_api(site, target_links, server_name):
    api = f"{SERVER}{site['api']}/api/extract"
    extract_mode = site.get("extract_mode", "standard")

    if extract_mode == "uhd":
        payload = {
            "link": target_links[0].get("url", ""),
            "server": server_name,
            "episode_filter": "",
            "size": target_links[0].get("size", "")
        }
    elif extract_mode == "ssr":
        payload = {
            "links": [{"url": l.get("url", ""), "episode": l.get("episode", ""),
                       "size": l.get("size", ""), "label": l.get("label", "")} for l in target_links],
            "server": server_name
        }
    else:
        payload = {"links": target_links, "selectedServer": server_name}

    data = http_post(api, payload, timeout=180)
    if not data:
        return []
    try:
        result = json.loads(data)
    except Exception:
        return []

    final_links = result.get("finalLinks", []) or result.get("links", [])
    final_links = [l for l in final_links if l.get("url")]
    return _filter_by_server(final_links, server_name)


def auto_refresh_link(meta, wanted_server="", wanted_ep=""):
    if not meta:
        return None
    site_id = meta.get("sid")
    site = get_site(site_id)
    if not site:
        return None

    target_links = meta.get("target_links") or []
    req_server = meta.get("req_server", "HUBCLOUD")

    if not target_links and meta.get("movie_url"):
        q_url = (f"{SERVER}{site['api']}/api/search"
                 f"?url={urllib.parse.quote(meta['movie_url'])}"
                 f"&title={urllib.parse.quote(meta.get('title', ''))}")
        raw = http_get(q_url, timeout=45)
        if raw:
            try:
                res = json.loads(raw)
                all_links = res.get("links", [])
                target_links = _get_target_links(all_links, meta.get("quality", ""), meta.get("mode", "pack"))
            except Exception:
                pass

    if not target_links:
        return None

    fresh_links = _call_extract_api(site, target_links, req_server)
    if not fresh_links:
        return None

    w_ep = (wanted_ep or "").strip().lower()
    w_srv = (wanted_server or "").strip().lower()

    for l in fresh_links:
        ep_ok = (not w_ep or w_ep == "movie" or (l.get("episode") or "").strip().lower() == w_ep)
        srv_ok = (not w_srv or w_srv in (l.get("server") or "").lower())
        if ep_ok and srv_ok:
            return l.get("url")

    if w_ep and w_ep != "movie":
        for l in fresh_links:
            if (l.get("episode") or "").strip().lower() == w_ep:
                return l.get("url")

    return fresh_links[0].get("url")


# ============================================================
# MAIN MENU & WIDGET FEEDS (Netflix-Style Rows)
# ============================================================
def main_menu():
    xbmcplugin.setContent(HANDLE, 'files')

    li = make_action_item("🔍 Search All Sites", "Search All")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=search_all", li, isFolder=True)

    li = make_action_item("▶ Continue Watching", "Continue Watching")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=resume_menu", li, isFolder=True)

    li = make_action_item("📺 Home Widgets (Netflix Rows)", "Home Widgets")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=widgets_menu", li, isFolder=True)

    li = make_action_item("📜 Search History", "Search History")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=history_searches", li, isFolder=True)

    li = make_action_item("🔗 Recent Links", "Recent Links")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=history_links", li, isFolder=True)

    li = make_action_item("🗑 Clear History", "Clear History")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=history_clear_menu", li, isFolder=True)

    li = make_action_item("🔄 Check & Update Addon", "Update Addon")
    xbmcplugin.addDirectoryItem(HANDLE, f"{BASE_URL}?action=update_addon", li, isFolder=False)

    for site in SITES:
        badge = SITE_BADGES.get(site["id"], "📺")
        li = make_action_item(f"{badge} {site['name']}", site["name"])
        if site.get("home_ep"):
            url = f"{BASE_URL}?action=site_menu&site={site['id']}&page=1"
        else:
            url = f"{BASE_URL}?action=search_input&site={site['id']}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def widgets_menu():
    """Kodi Skin Widgets ke liye clean poster feeds (sirf posters, koi Search/Next button nahi)."""
    xbmcplugin.setContent(HANDLE, 'files')
    for site in SITES:
        if not site.get("home_ep"):
            continue
        badge = SITE_BADGES.get(site["id"], "📺")
        li = make_action_item(f"{badge} {site['name']} (Widget Row)", site["name"])
        url = f"{BASE_URL}?action=widget&site={site['id']}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _fetch_site_posters(site, page=1):
    home_ep = site.get("home_ep")
    if not home_ep:
        return []
    data = http_get(f"{SERVER}{site['api']}{home_ep}?page={page}", timeout=15)
    if not data:
        return []
    try:
        parsed = json.loads(data)
    except Exception:
        return []

    home_key = site.get("home_key")
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return (parsed.get(home_key) if home_key else None) or \
               parsed.get("items") or parsed.get("posts") or parsed.get("posters") or []
    return []


def site_widget(site_id):
    """Netflix-style horizontal row ke liye sirf posters return karta hai."""
    site = get_site(site_id)
    if not site:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setContent(HANDLE, 'movies')
    results = _fetch_site_posters(site, page=1)

    for item in results:
        title = item.get("title", "")
        link = item.get("link") or item.get("url") or ""
        poster = _get_poster(item)
        if not title or not link:
            continue

        li = make_movie_item(title, poster, site_name=site["name"])
        next_url = (f"{BASE_URL}?action=qualities&site={site_id}"
                    f"&movie_url={urllib.parse.quote(link)}"
                    f"&title={urllib.parse.quote(title)}")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# SITE MENU (Posters + Pagination)
# ============================================================
def site_menu(site_id, page=1):
    site = get_site(site_id)
    if not site:
        return

    xbmcplugin.setContent(HANDLE, 'movies')

    if page == 1:
        li = make_action_item(f"🔍 Search on {site['name']}...", "Search")
        xbmcplugin.addDirectoryItem(HANDLE,
                                    f"{BASE_URL}?action=search_input&site={site_id}",
                                    li, isFolder=True)

    results = _fetch_site_posters(site, page=page)
    added = 0
    for item in results:
        title = item.get("title", "")
        link = item.get("link") or item.get("url") or ""
        poster = _get_poster(item)

        if not title or not link:
            continue

        li = make_movie_item(title, poster, site_name=site["name"])
        next_url = (f"{BASE_URL}?action=qualities&site={site_id}"
                    f"&movie_url={urllib.parse.quote(link)}"
                    f"&title={urllib.parse.quote(title)}")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)
        added += 1

    if added > 0 and site_id != "hdhub4u":
        next_page = page + 1
        li = make_action_item(f"➡ Next Page (Page {next_page})", f"Page {next_page}")
        xbmcplugin.addDirectoryItem(HANDLE,
                                    f"{BASE_URL}?action=site_menu&site={site_id}&page={next_page}",
                                    li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# SEARCH
# ============================================================
def _run_search(site_id, query):
    site = get_site(site_id)
    if not site:
        return []
    url = f"{SERVER}{site['api']}/api/suggest?q={urllib.parse.quote(query)}"
    data = http_get(url, timeout=15)
    if not data:
        return []
    try:
        r = json.loads(data)
        return r if isinstance(r, list) else []
    except Exception:
        return []


def _render_results(combined, prefix_site=False):
    if not combined:
        return False

    xbmcplugin.setContent(HANDLE, 'movies')

    for item in combined:
        title = item.get("title", "Unknown")
        poster = _get_poster(item)
        link = item.get("link") or item.get("url") or ""
        sid = item.get("_site_id", "")
        site = get_site(sid)
        site_name = site["name"] if site else "Unknown"

        if not link:
            continue

        if prefix_site:
            badge = SITE_BADGES.get(sid, "📺")
            display = f"{badge} [{site_name}]  {title}"
            li = make_movie_item(title, poster, site_name=site_name)
            li.setLabel(display)
        else:
            li = make_movie_item(title, poster, site_name=site_name)

        next_url = (f"{BASE_URL}?action=qualities&site={sid}"
                    f"&movie_url={urllib.parse.quote(link)}"
                    f"&title={urllib.parse.quote(title)}")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
    return True


def search_all():
    kb = xbmc.Keyboard("", "Search All Sites")
    kb.doModal()
    if not kb.isConfirmed():
        return
    query = kb.getText().strip()
    if not query:
        return

    add_search_history(query, "all")

    combined = []
    with ThreadPoolExecutor(max_workers=len(SEARCH_ALL_SITES)) as ex:
        futures = {ex.submit(_run_search, sid, query): sid for sid in SEARCH_ALL_SITES}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                for r in fut.result():
                    r["_site_id"] = sid
                    combined.append(r)
            except Exception:
                pass

    if not combined:
        xbmcgui.Dialog().notification("No results", query)
        return

    _render_results(combined, prefix_site=True)


def search_all_with_query(query):
    if not query:
        return
    combined = []
    with ThreadPoolExecutor(max_workers=len(SEARCH_ALL_SITES)) as ex:
        futures = {ex.submit(_run_search, sid, query): sid for sid in SEARCH_ALL_SITES}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                for r in fut.result():
                    r["_site_id"] = sid
                    combined.append(r)
            except Exception:
                pass
    _render_results(combined, prefix_site=True)


def search_input(site_id):
    site = get_site(site_id)
    if not site:
        return
    kb = xbmc.Keyboard("", f"Search on {site['name']}")
    kb.doModal()
    if not kb.isConfirmed():
        return
    query = kb.getText().strip()
    if not query:
        return

    add_search_history(query, site_id)
    results = _run_search(site_id, query)
    if not results:
        xbmcgui.Dialog().notification("No results", query)
        return

    for r in results:
        r["_site_id"] = site_id
    _render_results(results)


def search_input_with_query(site_id, query):
    if not query:
        return
    results = _run_search(site_id, query)
    for r in results:
        r["_site_id"] = site_id
    _render_results(results)


# ============================================================
# QUALITIES
# ============================================================
def show_qualities(site_id, movie_url, title):
    site = get_site(site_id)
    if not site:
        return

    url = (f"{SERVER}{site['api']}/api/search"
           f"?url={urllib.parse.quote(movie_url)}"
           f"&title={urllib.parse.quote(title)}")
    data = http_get(url, timeout=45)
    if not data:
        xbmcgui.Dialog().notification("Error", "Server connect fail")
        return

    try:
        result = json.loads(data)
    except Exception:
        xbmcgui.Dialog().notification("Error", "Invalid response")
        return

    if result.get("error"):
        xbmcgui.Dialog().notification("Error", result["error"])
        return

    all_links = result.get("links", [])
    seasons = result.get("seasons", [])
    if seasons and not all_links:
        for s in seasons:
            sname = s.get("season", "")
            for l in s.get("links", []):
                l_copy = dict(l)
                if sname and sname not in l_copy.get("quality", ""):
                    l_copy["quality"] = f"[{sname}] {l_copy.get('quality', '')}"
                all_links.append(l_copy)

    qualities = result.get("qualities", []) or []
    episode_qualities = result.get("episode_qualities", []) or []

    if not episode_qualities and not qualities:
        pack_set, single_set = [], []
        for l in all_links:
            q = l.get("quality") or l.get("label") or ""
            if not q:
                continue
            if l.get("is_zip"):
                if q not in pack_set:
                    pack_set.append(q)
            else:
                if q not in single_set:
                    single_set.append(q)
        qualities = pack_set
        episode_qualities = single_set

    if not qualities and not episode_qualities:
        xbmcgui.Dialog().notification("No qualities", "Kuch nahi mila")
        return

    WINDOW.setProperty("ae_all_links", json.dumps(all_links))
    WINDOW.setProperty("ae_movie_title", title)
    WINDOW.setProperty("ae_movie_url", movie_url)
    WINDOW.setProperty("ae_site_id", site_id)

    xbmcplugin.setContent(HANDLE, 'files')

    for q in qualities:
        li = make_action_item(f"[PACK] {q}", f"{title} — {q}")
        next_url = (f"{BASE_URL}?action=servers&site={site_id}"
                    f"&quality={urllib.parse.quote(q)}&mode=pack")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    for q in episode_qualities:
        li = make_action_item(f"[EP] {q}", f"{title} — {q}")
        next_url = (f"{BASE_URL}?action=servers&site={site_id}"
                    f"&quality={urllib.parse.quote(q)}&mode=single")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# SERVERS
# ============================================================
def _get_target_links(all_links, quality, mode):
    target_links = []
    for l in all_links:
        q_val = l.get("quality") or l.get("label") or ""
        if q_val != quality:
            continue
        if mode == "pack":
            if l.get("is_zip") is True:
                target_links.append(l)
        else:
            if not l.get("is_zip"):
                target_links.append(l)
    if not target_links:
        target_links = [l for l in all_links if (l.get("quality") or l.get("label")) == quality]
    return target_links


def show_servers(site_id, quality, mode):
    site = get_site(site_id)
    if not site:
        return

    title = WINDOW.getProperty("ae_movie_title") or "Movie"
    servers_list = site.get("servers", ["HUBCLOUD"])

    if site.get("dynamic_servers"):
        links_json = WINDOW.getProperty("ae_all_links")
        if links_json:
            try:
                all_links = json.loads(links_json)
                t_links = _get_target_links(all_links, quality, mode)
                if t_links:
                    sample_url = t_links[0].get("url", "")
                    s_data = http_get(f"{SERVER}{site['api']}/api/servers?url={urllib.parse.quote(sample_url)}", timeout=25)
                    if s_data:
                        s_res = json.loads(s_data)
                        if s_res.get("servers"):
                            servers_list = s_res["servers"]
            except Exception:
                pass

    xbmcplugin.setContent(HANDLE, 'files')

    for server_name in servers_list:
        li = make_action_item(server_name.upper(), f"{title} • {quality} • {server_name}")
        next_url = (f"{BASE_URL}?action=extract&site={site_id}"
                    f"&quality={urllib.parse.quote(quality)}"
                    f"&server={urllib.parse.quote(server_name)}"
                    f"&mode={mode}")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# EXTRACT (+ Series Auto-Play Playlist Save)
# ============================================================
def _filter_by_server(links, server_name):
    if not server_name:
        return links
    r = server_name.upper()
    if r == "MULTICLOUD":
        return [l for l in links
                if "HUBCLOUD" not in (l.get("server") or "").upper()
                and "GDFLIX" not in (l.get("server") or "").upper()]
    return links


def extract_final_links(site_id, quality, server_name, mode):
    site = get_site(site_id)
    if not site:
        return

    links_json = WINDOW.getProperty("ae_all_links")
    if not links_json:
        xbmcgui.Dialog().notification("Error", "Session expire")
        return
    try:
        all_links = json.loads(links_json)
    except Exception:
        xbmcgui.Dialog().notification("Error", "Parse fail")
        return

    target_links = _get_target_links(all_links, quality, mode)
    if not target_links:
        xbmcgui.Dialog().notification("No links", f"{quality} ke liye kuch nahi")
        return

    final_links = _call_extract_api(site, target_links, server_name)
    if not final_links:
        xbmcgui.Dialog().notification("Extract fail", "Koi link nahi mila")
        return

    title = WINDOW.getProperty("ae_movie_title") or "Movie"
    movie_url = WINDOW.getProperty("ae_movie_url") or ""

    extract_meta = {
        "sid": site_id,
        "movie_url": movie_url,
        "title": title,
        "quality": quality,
        "mode": mode,
        "req_server": server_name,
        "target_links": target_links[:5],
    }
    WINDOW.setProperty("ae_last_meta", json.dumps(extract_meta))

    # Series Auto-Play Next Episode ke liye playlist save karo
    playlist = []
    xbmcplugin.setContent(HANDLE, 'files')

    for idx, l in enumerate(final_links, 1):
        srv = l.get("server", f"Server {idx}")
        link_url = l.get("url", "")
        ep = l.get("episode", "") or "Movie"
        q = l.get("quality", quality)
        size = l.get("size", "")

        play_str = (f"{BASE_URL}?action=play&url={urllib.parse.quote(link_url)}"
                    f"&title={urllib.parse.quote(title)}&server={urllib.parse.quote(srv)}"
                    f"&ep={urllib.parse.quote(ep)}&site={urllib.parse.quote(site_id)}"
                    f"&size={urllib.parse.quote(size)}&quality={urllib.parse.quote(q)}"
                    f"&pl_idx={idx - 1}")

        playlist.append({"ep": ep, "title": title, "play_url": play_str})

        display = f"[{idx:02d}] {srv}"
        if size and size not in ("", "Unknown", "Unknown Size"):
            display += f"  •  {size}"
        if ep and ep != "Movie":
            display += f"  •  {ep}"

        li = xbmcgui.ListItem(label=display)
        li.setProperty("IsPlayable", "true")
        li.setInfo("video", {"title": title, "plot": f"{srv} • {q}", "mediatype": "video"})
        xbmcplugin.addDirectoryItem(HANDLE, play_str, li, isFolder=False)

    WINDOW.setProperty("ae_playlist", json.dumps(playlist))
    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# SMART PLAY (Auto-Refresh + Resume + Next Episode Queue)
# ============================================================
def _resolve_and_play(stream_url, title, server, key, start_pos=0, pl_idx=-1):
    WINDOW.setProperty("ae_playing_key", key)
    WINDOW.setProperty("ae_playlist_idx", str(pl_idx))
    li = xbmcgui.ListItem(label=title, path=stream_url)
    li.setInfo("video", {"title": title, "plot": server, "mediatype": "movie"})

    if start_pos > 30:
        li.setProperty("StartOffset", str(int(start_pos)))

    u = stream_url.lower()
    if ".m3u8" in u or "m3u" in u:
        li.setMimeType("application/vnd.apple.mpegurl")
    elif ".mp4" in u:
        li.setMimeType("video/mp4")
    elif ".mkv" in u:
        li.setMimeType("video/x-matroska")
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def play_url(stream_url, title, server, ep="Movie", site_id="", size="", quality="", pl_idx=-1):
    meta = {}
    meta_raw = WINDOW.getProperty("ae_last_meta")
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
        except Exception:
            meta = {}

    key = _make_key(title, ep, site_id or meta.get("sid", ""))
    add_link_history(title, stream_url, site_id or meta.get("sid", ""),
                     quality=quality, server=server, size=size, ep=ep, meta=meta)
    saved_pos = upsert_bookmark(key, stream_url, title, server=server, ep=ep, meta=meta)
    _resolve_and_play(stream_url, title, server, key, start_pos=saved_pos, pl_idx=pl_idx)


def smart_play_saved(source, key, fallback_url=""):
    entry = None
    if source == "bookmark":
        d = load_bookmarks()
        entry = next((b for b in d.get("bookmarks", []) if b.get("key") == key or b.get("url") == fallback_url), None)
    else:
        d = load_history()
        entry = next((l for l in d.get("links", []) if l.get("key") == key or l.get("url") == fallback_url), None)

    if not entry:
        xbmcgui.Dialog().notification("Error", "Link record nahi mila")
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    stream_url = entry.get("url", "")
    title = entry.get("title", "Movie")
    server = entry.get("server", "")
    ep = entry.get("ep", "Movie")
    meta = entry.get("meta")
    item_key = entry.get("key") or _make_key(title, ep, entry.get("sid", ""))

    bm_data = load_bookmarks()
    bm = next((b for b in bm_data.get("bookmarks", []) if b.get("key") == item_key or b.get("url") == stream_url), None)
    start_pos = int(bm.get("position", 0)) if bm else int(entry.get("position", 0))

    if not is_link_alive(stream_url):
        if meta:
            xbmcgui.Dialog().notification("Link Expire", "Naya link generate ho raha hai...", time=4000)
            fresh_url = auto_refresh_link(meta, wanted_server=server, wanted_ep=ep)
            if fresh_url:
                stream_url = fresh_url
                add_link_history(title, stream_url, meta.get("sid", ""),
                                 quality=entry.get("quality", ""), server=server,
                                 size=entry.get("size", ""), ep=ep, meta=meta)
                upsert_bookmark(item_key, stream_url, title, server=server, ep=ep, meta=meta)
            else:
                xbmcgui.Dialog().notification("Error", "Auto-refresh fail ho gaya")
                xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
                return
        else:
            xbmcgui.Dialog().notification("Link Expire", "Purani history mein refresh data nahi hai")

    _resolve_and_play(stream_url, title, server, item_key, start_pos=start_pos, pl_idx=-1)


# ============================================================
# RESUME MENU
# ============================================================
def resume_menu():
    d = load_bookmarks()
    bmarks = [b for b in d.get("bookmarks", [])
              if b.get("position", 0) > 30
              and not (b.get("total", 0) > 60 and b.get("position", 0) / max(b["total"], 1) > 0.93)]

    if not bmarks:
        xbmcgui.Dialog().notification("Empty", "Koi adhoori movie nahi")
        return

    bmarks.sort(key=lambda x: x.get("t", 0), reverse=True)
    xbmcplugin.setContent(HANDLE, 'files')

    for idx, b in enumerate(bmarks, 1):
        title = b.get("title", "Unknown")
        pos = int(b.get("position", 0))
        total = int(b.get("total", 1)) or 1
        pct = min(99, int(100 * pos / total))
        srv = b.get("server", "")
        ep = b.get("ep", "")
        key = b.get("key") or _make_key(title, ep, "")

        display = f"[{idx:02d}] {title}"
        if ep and ep != "Movie":
            display += f"  ·  {ep}"
        if srv:
            display += f"  ·  {srv}"
        display += f"  ·  {pct}%"

        li = make_action_item(display, title)
        li.setProperty("IsPlayable", "true")
        next_url = (f"{BASE_URL}?action=smart_play&source=bookmark"
                    f"&key={urllib.parse.quote(key)}"
                    f"&url={urllib.parse.quote(b.get('url', ''))}")
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# HISTORY MENUS
# ============================================================
def history_searches():
    d = load_history()
    s = d.get("searches", [])
    if not s:
        xbmcgui.Dialog().notification("Empty", "Koi search history nahi")
        return

    xbmcplugin.setContent(HANDLE, 'files')
    for e in s:
        q = e.get("q", "")
        sid = e.get("sid", "all")
        site = get_site(sid) if sid != "all" else None
        label_site = "All Sites" if sid == "all" else (site["name"] if site else sid)

        li = make_action_item(f"🔍 {q}  [{label_site}]", q)
        if sid == "all":
            next_url = f"{BASE_URL}?action=search_all_go&q={urllib.parse.quote(q)}"
        else:
            next_url = f"{BASE_URL}?action=search_input_go&site={sid}&q={urllib.parse.quote(q)}"
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def history_links():
    d = load_history()
    links = d.get("links", [])
    if not links:
        xbmcgui.Dialog().notification("Empty", "Koi link history nahi")
        return

    xbmcplugin.setContent(HANDLE, 'files')
    for idx, l in enumerate(links[:100], 1):
        title = l.get("title", "Unknown")
        srv = l.get("server", "")
        size = l.get("size", "")
        ep = l.get("ep", "")
        key = l.get("key") or _make_key(title, ep, l.get("sid", ""))

        display = f"[{idx:02d}] {title}"
        if ep and ep != "Movie":
            display += f"  ·  {ep}"
        if srv:
            display += f"  ·  {srv}"
        if size and size not in ("Unknown", "Unknown Size", ""):
            display += f"  ·  {size}"

        li = make_action_item(display, title)
        li.setProperty("IsPlayable", "true")
        play_str = (f"{BASE_URL}?action=smart_play&source=history"
                    f"&key={urllib.parse.quote(key)}"
                    f"&url={urllib.parse.quote(l.get('url', ''))}")
        xbmcplugin.addDirectoryItem(HANDLE, play_str, li, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)


def history_clear_menu():
    opts = ["Clear Search History", "Clear Link History", "Clear All", "Cancel"]
    c = xbmcgui.Dialog().select("Clear History", opts)
    d = load_history()
    if c == 0:
        d["searches"] = []
        save_history(d)
        xbmcgui.Dialog().notification("Done", "Search history clear")
    elif c == 1:
        d["links"] = []
        save_history(d)
        xbmcgui.Dialog().notification("Done", "Link history clear")
    elif c == 2:
        save_history({"searches": [], "links": []})
        save_bookmarks({"bookmarks": []})
        xbmcgui.Dialog().notification("Done", "Sab clear")


# ============================================================
# ROUTER
# ============================================================
def main():
    params = urllib.parse.parse_qs(sys.argv[2][1:])
    action = params.get("action", [None])[0]

    if action == "search_all":
        search_all()
    elif action == "search_all_go":
        search_all_with_query(params.get("q", [""])[0])
    elif action == "widgets_menu":
        widgets_menu()
    elif action == "widget":
        site_widget(params.get("site", [""])[0])
    elif action == "site_menu":
        site_menu(params.get("site", [""])[0],
                  int(params.get("page", ["1"])[0]))
    elif action == "search_input":
        search_input(params.get("site", [""])[0])
    elif action == "search_input_go":
        search_input_with_query(params.get("site", [""])[0], params.get("q", [""])[0])
    elif action == "qualities":
        show_qualities(params.get("site", [""])[0],
                       params.get("movie_url", [""])[0],
                       params.get("title", ["Movie"])[0])
    elif action == "servers":
        show_servers(params.get("site", [""])[0],
                     params.get("quality", [""])[0],
                     params.get("mode", ["pack"])[0])
    elif action == "extract":
        extract_final_links(params.get("site", [""])[0],
                            params.get("quality", [""])[0],
                            params.get("server", ["HUBCLOUD"])[0],
                            params.get("mode", ["pack"])[0])
    elif action == "play":
        play_url(params.get("url", [""])[0],
                 params.get("title", ["Movie"])[0],
                 params.get("server", ["Video"])[0],
                 params.get("ep", ["Movie"])[0],
                 params.get("site", [""])[0],
                 params.get("size", [""])[0],
                 params.get("quality", [""])[0],
                 int(params.get("pl_idx", ["-1"])[0]))
    elif action == "smart_play":
        smart_play_saved(params.get("source", ["history"])[0],
                         params.get("key", [""])[0],
                         params.get("url", [""])[0])
    elif action == "resume_menu":
        resume_menu()
    elif action == "history_searches":
        history_searches()
    elif action == "history_links":
        history_links()
    elif action == "history_clear_menu":
        history_clear_menu()
    elif action == "update_addon":
        update_addon()
    else:
        main_menu()


if __name__ == "__main__":
    main()