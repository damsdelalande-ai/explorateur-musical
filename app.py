#!/usr/bin/env python3
"""
Explorateur musical underground - version Render avec authentification.

Authentification HTTP Basic :
- Variables d'environnement APP_USERNAME (defaut: "larsen") et APP_PASSWORD
- Si APP_PASSWORD n'est pas defini, le service refuse toutes les requetes
- Le navigateur memorise les credentials pour la session
"""

import base64
import hmac
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket

PORT = int(os.environ.get('PORT', 8765))
LASTFM_KEY = os.environ.get('LASTFM_KEY', 'b25b959554ed76058ac220b7b2e0a026')
MB_BASE = 'https://musicbrainz.org/ws/2'
LB_BASE = 'https://labs.api.listenbrainz.org'
LFM_BASE = 'https://ws.audioscrobbler.com/2.0/'
USER_AGENT = 'ExplorateurMusicalLeLarsen/1.0 (contact: lelarsen@example.com)'
TIMEOUT = 10

APP_USERNAME = os.environ.get('APP_USERNAME', 'larsen')
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')
AUTH_REALM = 'Le Larsen - Explorateur musical'


def check_auth(auth_header):
    if not APP_PASSWORD:
        return False
    if not auth_header or not auth_header.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
        user, _, password = decoded.partition(':')
        u_ok = hmac.compare_digest(user, APP_USERNAME)
        p_ok = hmac.compare_digest(password, APP_PASSWORD)
        return u_ok and p_ok
    except Exception:
        return False


def http_get_json(url, headers=None):
    req_headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}'
    except urllib.error.URLError as e:
        return None, f'Reseau : {e.reason}'
    except json.JSONDecodeError as e:
        return None, f'JSON invalide : {e}'
    except socket.timeout:
        return None, 'Timeout'


def mb_search_artist(name):
    query = urllib.parse.quote(name.strip())
    url = f'{MB_BASE}/artist/?query={query}&fmt=json&limit=10'
    data, err = http_get_json(url)
    if err:
        return [], err
    return data.get('artists', []), None


def mb_get_relations(mbid):
    url = f'{MB_BASE}/artist/{mbid}?inc=artist-rels+label-rels+tags+genres&fmt=json'
    data, err = http_get_json(url)
    return data, err


def lb_similar_artists(mbid):
    algo = ('session_based_days_7500_session_300_contribution_5'
            '_threshold_10_limit_100_filter_True_skip_30')
    url = f'{LB_BASE}/similar-artists/json?artist_mbids={mbid}&algorithm={algo}'
    data, err = http_get_json(url)
    if err or not data:
        return [], err
    if isinstance(data, list) and data and isinstance(data[0], dict) and 'data' in data[0]:
        return data[0].get('data', []), None
    if isinstance(data, list):
        return data, None
    return [], None


def lastfm_similar(name):
    params = {
        'method': 'artist.getsimilar',
        'artist': name,
        'api_key': LASTFM_KEY,
        'format': 'json',
        'limit': 15,
        'autocorrect': 1,
    }
    url = f'{LFM_BASE}?{urllib.parse.urlencode(params)}'
    data, err = http_get_json(url)
    if err or not data:
        return [], err
    if data.get('error'):
        return [], f"Last.fm code {data['error']}"
    artists = data.get('similarartists', {}).get('artist', [])
    if isinstance(artists, dict):
        artists = [artists]
    return artists, None


INDEX_HTML = r'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>Explorateur musical - Le Larsen</title>
<style>
  :root {
    --bg: #faf9f6; --surface: #ffffff; --surface-2: #f1efe8;
    --border: rgba(0,0,0,0.12); --border-strong: rgba(0,0,0,0.22);
    --text: #1a1a1a; --text-2: #5f5e5a; --text-3: #888780;
    --info: #185fa5; --info-bg: #e6f1fb;
    --success: #0f6e56; --warning: #854f0b; --warning-bg: #faeeda;
    --danger: #a32d2d; --purple: #534ab7;
    --radius: 8px;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #1a1a18; --surface: #252523; --surface-2: #2c2c2a;
      --border: rgba(255,255,255,0.12); --border-strong: rgba(255,255,255,0.22);
      --text: #f0efe9; --text-2: #b4b2a9; --text-3: #888780;
      --info: #85b7eb; --info-bg: #042c53;
      --success: #5dcaa5; --warning: #fac775; --warning-bg: #412402;
      --danger: #f09595; --purple: #afa9ec;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    margin: 0; padding: 2rem 1rem; line-height: 1.6;
  }
  .container { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 22px; font-weight: 500; margin: 0 0 4px; }
  .subtitle { font-size: 13px; color: var(--text-2); margin: 0 0 1.5rem; }
  h3 { font-size: 15px; font-weight: 500; margin: 0; }
  .search-row { display: flex; gap: 8px; margin-bottom: 10px; }
  input[type="text"], button {
    font-family: inherit; font-size: 14px;
    border-radius: var(--radius);
    border: 0.5px solid var(--border-strong);
    background: var(--surface); color: var(--text);
    padding: 8px 12px; height: 36px;
  }
  input[type="text"] { flex: 1; }
  input[type="text"]:focus { outline: none; border-color: var(--info); }
  button { cursor: pointer; }
  button:hover { background: var(--surface-2); }
  .seed-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 1rem; }
  .seed-chips button { font-size: 12px; padding: 4px 10px; height: auto; }
  #status { font-size: 13px; color: var(--text-2); margin-bottom: 1rem; min-height: 20px; }
  #status.error { color: var(--danger); }
  #status.warn { color: var(--warning); }
  .current-artist {
    background: var(--surface-2); border-radius: var(--radius);
    padding: 12px 14px; margin-bottom: 1.25rem;
  }
  .current-artist .label { font-size: 11px; color: var(--text-3); margin-bottom: 4px; }
  .current-artist .name { font-size: 16px; font-weight: 500; }
  .current-artist .meta { font-size: 12px; color: var(--text-2); margin-top: 2px; }
  .tag-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .tag {
    font-size: 11px; color: var(--text-2);
    background: var(--surface); padding: 2px 8px;
    border-radius: var(--radius); border: 0.5px solid var(--border);
  }
  .section { margin-bottom: 1.5rem; }
  .section-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
  .section-head .count { font-size: 12px; color: var(--text-3); }
  .section-head .source-note { font-weight: 400; color: var(--text-3); font-size: 12px; }
  .results { display: grid; grid-template-columns: 1fr; gap: 6px; }
  .result-card {
    background: var(--surface); border: 0.5px solid var(--border);
    border-radius: var(--radius); padding: 10px 12px;
    display: flex; align-items: center; gap: 10px;
  }
  .result-card .info { flex: 1; min-width: 0; }
  .result-card .name { font-size: 14px; font-weight: 500; }
  .result-card .meta { font-size: 12px; color: var(--text-2); margin-top: 2px; }
  .result-card button { font-size: 12px; padding: 5px 10px; height: auto; }
  .source-mb { border-left: 3px solid var(--purple); }
  .source-lb { border-left: 3px solid var(--success); }
  .source-lfm { border-left: 3px solid var(--warning); }
  .candidates {
    background: var(--warning-bg); border: 0.5px solid var(--warning);
    border-radius: var(--radius); padding: 12px 14px; margin-bottom: 1rem;
  }
  .candidates .label { font-size: 12px; color: var(--warning); margin-bottom: 8px; font-weight: 500; }
  .candidate-btn {
    display: block; width: 100%; text-align: left;
    background: var(--surface); margin-bottom: 4px;
    font-size: 13px; padding: 6px 10px; height: auto;
  }
  .label-list { display: flex; flex-wrap: wrap; gap: 6px; }
  .label-btn { font-size: 12px; padding: 5px 10px; height: auto; background: var(--info-bg); color: var(--info); }
  .errors {
    background: var(--warning-bg); border-radius: var(--radius);
    padding: 8px 12px; margin-bottom: 1rem;
    font-size: 12px; color: var(--warning);
  }
  .sources-footer {
    margin-top: 2rem; padding-top: 1rem;
    border-top: 0.5px solid var(--border);
    font-size: 12px; color: var(--text-3); line-height: 1.6;
  }
  .sources-footer a { color: var(--info); }
</style>
</head>
<body>
<div class="container">

<h1>Explorateur musical underground</h1>
<p class="subtitle">Le Larsen - triangulation MusicBrainz + ListenBrainz + Last.fm</p>

<div class="search-row">
  <input type="text" id="artist-input" placeholder="ex. Chat Pile, Shellac, Mendelson..." autofocus>
  <button id="search-btn" style="min-width: 110px;">Explorer</button>
</div>

<div class="seed-chips">
  <button class="seed-chip" data-artist="Shellac">Shellac</button>
  <button class="seed-chip" data-artist="Chat Pile">Chat Pile</button>
  <button class="seed-chip" data-artist="Mendelson">Mendelson</button>
  <button class="seed-chip" data-artist="Beak>">Beak&gt;</button>
  <button class="seed-chip" data-artist="Ghost Dubs">Ghost Dubs</button>
  <button class="seed-chip" data-artist="Programme">Programme</button>
</div>

<div id="status"></div>
<div id="candidates"></div>
<div id="current-artist"></div>
<div id="errors"></div>
<div id="sections"></div>

<div class="sources-footer">
  Sources :
  <a href="https://musicbrainz.org/doc/MusicBrainz_API" target="_blank">MusicBrainz</a> &middot;
  <a href="https://listenbrainz.readthedocs.io/" target="_blank">ListenBrainz</a> &middot;
  <a href="https://www.last.fm/api" target="_blank">Last.fm</a>.
</div>

</div>

<script>
function escapeHtml(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
function setStatus(msg, kind) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = kind || '';
}
function artistCard(name, meta, sourceClass) {
  return `<div class="result-card ${sourceClass}">
    <div class="info">
      <div class="name">${escapeHtml(name)}</div>
      ${meta ? `<div class="meta">${escapeHtml(meta)}</div>` : ''}
    </div>
    <button class="explore-btn" data-artist="${escapeHtml(name)}">&rarr;</button>
  </div>`;
}
function sectionWrap(titleHtml, bodyHtml, count) {
  return `<div class="section">
    <div class="section-head">
      <h3>${titleHtml}</h3>
      <span class="count">${count} resultats</span>
    </div>${bodyHtml}
  </div>`;
}

async function search(name) {
  if (!name || !name.trim()) return;
  name = name.trim();
  setStatus('Recherche... (peut prendre 30s si le serveur dormait)');
  document.getElementById('sections').innerHTML = '';
  document.getElementById('current-artist').innerHTML = '';
  document.getElementById('candidates').innerHTML = '';
  document.getElementById('errors').innerHTML = '';

  let result;
  try {
    const r = await fetch(`/api/search?name=${encodeURIComponent(name)}`);
    result = await r.json();
  } catch (e) {
    setStatus(`Erreur : ${e.message}`, 'error');
    return;
  }

  if (result.errors && result.errors.length > 0) {
    document.getElementById('errors').innerHTML =
      `<div class="errors">! ${result.errors.map(escapeHtml).join(' / ')}</div>`;
  }

  if (result.candidates_only) {
    const candList = result.candidates.slice(0, 6).map((a, i) => {
      const disambig = a.disambiguation ? ` - ${a.disambiguation}` : '';
      const country = a.country ? ` (${a.country})` : '';
      const ls = a['life-span'] || {};
      const period = ls.begin ? ` - ${ls.begin}${ls.end ? '-' + ls.end : '-'}` : '';
      return `<button class="candidate-btn" data-mbid="${escapeHtml(a.id)}">${escapeHtml(a.name)}${escapeHtml(disambig)}${escapeHtml(country)}${escapeHtml(period)}</button>`;
    }).join('');
    document.getElementById('candidates').innerHTML = `
      <div class="candidates">
        <div class="label">Plusieurs artistes correspondent - choisis :</div>
        ${candList}
      </div>`;
    document.querySelectorAll('.candidate-btn').forEach(btn => {
      btn.addEventListener('click', () => exploreByMbid(btn.dataset.mbid));
    });
    setStatus(`${result.candidates.length} candidats.`, 'warn');
    return;
  }

  if (result.lastfm_only) {
    renderLastfmOnly(name, result.lastfm);
    return;
  }

  renderFull(result);
}

async function exploreByMbid(mbid) {
  setStatus('Recuperation...');
  document.getElementById('sections').innerHTML = '';
  document.getElementById('candidates').innerHTML = '';
  document.getElementById('errors').innerHTML = '';
  let result;
  try {
    const r = await fetch(`/api/explore?mbid=${encodeURIComponent(mbid)}`);
    result = await r.json();
  } catch (e) {
    setStatus(`Erreur : ${e.message}`, 'error');
    return;
  }
  if (result.errors && result.errors.length > 0) {
    document.getElementById('errors').innerHTML =
      `<div class="errors">! ${result.errors.map(escapeHtml).join(' / ')}</div>`;
  }
  renderFull(result);
}

function renderFull(result) {
  const a = result.artist;
  const ls = a['life-span'] || {};
  const tags = (result.tags || []).slice(0, 6);
  document.getElementById('current-artist').innerHTML = `
    <div class="current-artist">
      <div class="label">Point de depart - MusicBrainz</div>
      <div class="name">${escapeHtml(a.name)}</div>
      <div class="meta">
        ${a.disambiguation ? escapeHtml(a.disambiguation) + ' - ' : ''}${a.country ? a.country + ' - ' : ''}${ls.begin || ''}${ls.end ? '-' + ls.end : (ls.begin ? '-' : '')}
      </div>
      ${tags.length ? `<div class="tag-row">
        ${tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
      </div>` : ''}
    </div>`;

  const sections = [];

  if (result.mb_relations && result.mb_relations.length > 0) {
    const items = result.mb_relations.slice(0, 15).map(r =>
      artistCard(r.name, r.relation_label, 'source-mb'));
    sections.push(sectionWrap(
      `Liens MusicBrainz <span class="source-note">- faits documentes</span>`,
      `<div class="results">${items.join('')}</div>`, result.mb_relations.length));
  }

  if (result.mb_labels && result.mb_labels.length > 0) {
    const buttons = result.mb_labels.map(l =>
      `<button class="label-btn" data-label="${escapeHtml(l)}">${escapeHtml(l)}</button>`).join('');
    sections.push(sectionWrap(
      `Labels associes <span class="source-note">- porte d'entree vers la scene</span>`,
      `<div class="label-list">${buttons}</div>`, result.mb_labels.length));
  }

  if (result.listenbrainz && result.listenbrainz.length > 0) {
    const items = result.listenbrainz.slice(0, 15).map(a => {
      const score = a.score || a.similarity || 0;
      const scoreStr = score ? `score ${Math.round(score * 100) / 100}` : '';
      const n = a.name || a.artist_name || a.comment;
      if (!n) return '';
      return artistCard(n, scoreStr, 'source-lb');
    }).filter(Boolean);
    if (items.length) {
      sections.push(sectionWrap(
        `ListenBrainz <span class="source-note">- filtrage collaboratif</span>`,
        `<div class="results">${items.join('')}</div>`, items.length));
    }
  }

  if (result.lastfm && result.lastfm.length > 0) {
    const items = result.lastfm.slice(0, 12).map(a => {
      const match = parseFloat(a.match) || 0;
      const meta = match ? `match ${Math.round(match * 100)}%` : '';
      return artistCard(a.name, meta, 'source-lfm');
    });
    sections.push(sectionWrap(
      `Last.fm <span class="source-note">- coocurrence d'ecoute</span>`,
      `<div class="results">${items.join('')}</div>`, items.length));
  }

  if (sections.length === 0) {
    setStatus(`Trouve "${a.name}" mais aucune relation/similarite.`, 'warn');
    return;
  }
  setStatus(`${sections.length} axe(s) de decouverte`);
  document.getElementById('sections').innerHTML = sections.join('');
  wireUpButtons();
}

function renderLastfmOnly(name, lfm) {
  document.getElementById('current-artist').innerHTML = `
    <div class="current-artist">
      <div class="label">Last.fm uniquement</div>
      <div class="name">${escapeHtml(name)}</div>
    </div>`;
  const items = lfm.slice(0, 12).map(a => {
    const match = parseFloat(a.match) || 0;
    const meta = match ? `match ${Math.round(match * 100)}%` : '';
    return artistCard(a.name, meta, 'source-lfm');
  });
  document.getElementById('sections').innerHTML = sectionWrap(
    `Last.fm <span class="source-note">- seule source</span>`,
    `<div class="results">${items.join('')}</div>`, items.length);
  setStatus(`${items.length} resultats`);
  wireUpButtons();
}

function wireUpButtons() {
  document.querySelectorAll('.explore-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const a = btn.dataset.artist;
      document.getElementById('artist-input').value = a;
      search(a);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
  document.querySelectorAll('.label-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const l = btn.dataset.label;
      window.open(`https://musicbrainz.org/search?query=${encodeURIComponent(l)}&type=label`, '_blank');
    });
  });
}

document.getElementById('search-btn').addEventListener('click', () =>
  search(document.getElementById('artist-input').value));
document.getElementById('artist-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') search(e.target.value);
});
document.querySelectorAll('.seed-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    const a = btn.dataset.artist;
    document.getElementById('artist-input').value = a;
    search(a);
  });
});
</script>
</body>
</html>
'''

ROBOTS_TXT = "User-agent: *\nDisallow: /\n"


def build_explore_result(mb_artist):
    mbid = mb_artist['id']
    name = mb_artist['name']
    errors = []

    mb_detail, err = mb_get_relations(mbid)
    if err:
        errors.append(f'MusicBrainz relations: {err}')
        mb_detail = {}

    lb_sim, err = lb_similar_artists(mbid)
    if err:
        errors.append(f'ListenBrainz: {err}')

    lfm_sim, err = lastfm_similar(name)
    if err:
        errors.append(f'Last.fm: {err}')

    tags_list = mb_detail.get('tags', []) if mb_detail else []
    genres_list = mb_detail.get('genres', []) if mb_detail else []
    tags = [t['name'] for t in sorted(tags_list, key=lambda x: -x.get('count', 0))[:5]]
    genres = [g['name'] for g in sorted(genres_list, key=lambda x: -x.get('count', 0))[:4]]
    all_tags = list(dict.fromkeys(genres + tags))

    type_labels = {
        'member of band': 'membre du groupe',
        'collaboration': 'collaboration',
        'supporting musician': 'musicien additionnel',
        'subgroup': 'sous-groupe',
        'is person': 'projet solo',
        'tribute': 'tribute',
    }
    relations = []
    labels_set = []
    for rel in (mb_detail or {}).get('relations', []):
        if rel.get('target-type') == 'artist' and rel.get('artist'):
            relations.append({
                'name': rel['artist']['name'],
                'relation_label': type_labels.get(rel.get('type', ''), rel.get('type', 'liee'))
            })
        elif rel.get('target-type') == 'label' and rel.get('label'):
            ln = rel['label']['name']
            if ln not in labels_set:
                labels_set.append(ln)

    return {
        'artist': mb_artist,
        'tags': all_tags,
        'mb_relations': relations,
        'mb_labels': labels_set[:8],
        'listenbrainz': lb_sim or [],
        'lastfm': lfm_sim or [],
        'errors': errors,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path}')

    def _send(self, code, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_auth(self):
        body = 'Authentification requise.'.encode('utf-8')
        self.send_response(401)
        self.send_header('WWW-Authenticate', f'Basic realm="{AUTH_REALM}"')
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/health':
            self._send(200, {'status': 'ok'})
            return
        if parsed.path == '/robots.txt':
            self._send(200, ROBOTS_TXT, 'text/plain; charset=utf-8')
            return

        auth_header = self.headers.get('Authorization', '')
        if not check_auth(auth_header):
            self._require_auth()
            return

        if parsed.path == '/' or parsed.path == '/index.html':
            self._send(200, INDEX_HTML, 'text/html; charset=utf-8')
            return

        if parsed.path == '/api/search':
            name = (params.get('name') or [''])[0]
            if not name:
                self._send(400, {'error': 'missing name'})
                return
            candidates, err = mb_search_artist(name)
            errors = [f'MusicBrainz: {err}'] if err else []

            if not candidates:
                lfm, lerr = lastfm_similar(name)
                if lerr:
                    errors.append(f'Last.fm: {lerr}')
                if lfm:
                    self._send(200, {'lastfm_only': True, 'lastfm': lfm, 'errors': errors})
                    return
                self._send(200, {'lastfm_only': True, 'lastfm': [], 'errors': errors
                                 + [f'Aucune source ne connait "{name}"']})
                return

            exact = [a for a in candidates if a['name'].lower() == name.lower()]
            if len(candidates) == 1 or exact:
                target = exact[0] if exact else candidates[0]
                result = build_explore_result(target)
                result['errors'] = errors + result.get('errors', [])
                self._send(200, result)
                return

            self._send(200, {
                'candidates_only': True,
                'candidates': candidates,
                'errors': errors,
            })
            return

        if parsed.path == '/api/explore':
            mbid = (params.get('mbid') or [''])[0]
            if not mbid:
                self._send(400, {'error': 'missing mbid'})
                return
            data, err = http_get_json(f'{MB_BASE}/artist/{mbid}?fmt=json')
            if err or not data:
                self._send(200, {'errors': [f'MusicBrainz: {err or "unknown"}']})
                return
            result = build_explore_result(data)
            self._send(200, result)
            return

        self._send(404, {'error': 'not found'})


def main():
    if not APP_PASSWORD:
        print('=' * 60)
        print('  ATTENTION : APP_PASSWORD non defini.')
        print('  Le service refusera toutes les requetes.')
        print('  Configure APP_PASSWORD dans Render > Environment.')
        print('=' * 60)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print('=' * 60)
    print(f'  Explorateur musical - ecoute sur 0.0.0.0:{PORT}')
    print(f'  Utilisateur : {APP_USERNAME}')
    print(f'  Mot de passe : {"configure" if APP_PASSWORD else "MANQUANT"}')
    print('=' * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nArret.')
        server.shutdown()


if __name__ == '__main__':
    main()
