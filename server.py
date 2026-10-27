import http.server
import socketserver
import json
import os
import errno
import hashlib
import secrets
import time
from dotenv import load_dotenv
from groq import Groq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))
PORT = int(os.getenv('PORT', 3004))
USERS_FILE = 'users.json'
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')

# ── Groq clients ──────────────────────────────────────────────────────────────
# groq_client  → used by /api/recommend  (wardrobe outfits)
# groq_client2 → used by /api/recommend2 (stats & travel)
# Both use the same key

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
groq_client2 = groq_client

print(f"Loaded GROQ_API_KEY: {bool(GROQ_API_KEY)}")

# ── HTML file map ─────────────────────────────────────────────────────────────
HTML_FILES = {
    '/':        'wardrobe-final (1).html',
    '/app':     'wardrobe-final (1).html',
    '/login':   'login.html',
    '/stats':   'stats.html',
    '/weather': 'weather.html',
    '/packing': 'packing.html',
}
PROTECTED_ROUTES = {'/app', '/stats', '/weather', '/packing'}

# ── Session store ─────────────────────────────────────────────────────────────
sessions = {}
SESSION_TTL = 60 * 60 * 8  # 8 hours


def _load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _wardrobe_file(username):
    safe = "".join(c for c in username if c.isalnum() or c in "_-")
    return f'wardrobe_{safe}.json'


def _history_file(username):
    safe = "".join(c for c in username if c.isalnum() or c in "_-")
    return f'history_{safe}.json'


def _load_json(path, default):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return default


def _save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _groq_error_response(error):
    status_code = getattr(error, 'status_code', None)
    if status_code == 401:
        message = 'Groq rejected the API key. Replace GROQ_API_KEY in .env with an active key, then restart the server.'
    elif status_code == 403:
        message = 'Groq denied access (HTTP 403). Check the key’s project permissions and IP/network restrictions; disable any blocking VPN, proxy, or firewall, then retry.'
    elif status_code == 404:
        message = 'Groq could not find the requested model. Check that the configured model is currently available to your account.'
    elif status_code == 429:
        message = 'Groq rate or usage limit reached. Check your account limits and try again later.'
    elif status_code is None:
        message = 'Could not connect to Groq. Check your internet connection, VPN, proxy, and firewall settings.'
    else:
        message = f'Groq could not complete the request (HTTP {status_code}). Check Groq service status and account settings.'

    print(f"Groq request failed: {type(error).__name__} (HTTP {status_code or 'n/a'})")
    return 502, message


def _create_session(username):
    token = secrets.token_hex(32)
    sessions[token] = {"username": username, "expires": time.time() + SESSION_TTL}
    return token


def _get_user(token):
    if not token:
        return None
    s = sessions.get(token)
    if s and s["expires"] > time.time():
        return s["username"]
    if token in sessions:
        del sessions[token]
    return None


# ── Handler ───────────────────────────────────────────────────────────────────
class MyHandler(http.server.SimpleHTTPRequestHandler):

    def _token(self):
        for part in self.headers.get('Cookie', '').split(';'):
            part = part.strip()
            if part.startswith('session='):
                return part[8:]
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth[7:]
        return None

    def _json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length)

    def _serve_html(self, filename):
        if os.path.exists(filename):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open(filename, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f'File not found: {filename}'.encode())

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split('?')[0]

        if path in HTML_FILES:
            if path in PROTECTED_ROUTES:
                token = self._token()
                if not _get_user(token):
                    self.send_response(302)
                    self.send_header('Location', '/login')
                    self.end_headers()
                    return
            self._serve_html(HTML_FILES[path])
            return

        if path == '/api/me':
            u = _get_user(self._token())
            if not u:
                self._json(401, {'error': 'Unauthorized'})
            else:
                self._json(200, {'username': u})
            return

        if path == '/api/wardrobe':
            u = _get_user(self._token())
            if not u:
                self._json(401, {'error': 'Unauthorized'})
                return
            self._json(200, _load_json(_wardrobe_file(u), []))
            return

        if path == '/api/history':
            u = _get_user(self._token())
            if not u:
                self._json(401, {'error': 'Unauthorized'})
                return
            self._json(200, _load_json(_history_file(u), []))
            return

        super().do_GET()

    # ── POST ──────────────────────────────────────────────────────────────────
    def do_POST(self):
        path = self.path.split('?')[0]

        # Register
        if path == '/api/auth/register':
            try:
                b = json.loads(self._body())
                username = b.get('username', '').strip()
                password = b.get('password', '')
                if not username or not password:
                    self._json(400, {'error': 'Username and password required'})
                    return
                if len(username) < 3:
                    self._json(400, {'error': 'Username must be at least 3 characters'})
                    return
                if len(password) < 6:
                    self._json(400, {'error': 'Password must be at least 6 characters'})
                    return
                users = _load_users()
                if username in users:
                    self._json(409, {'error': 'Username already taken'})
                    return
                users[username] = {'password_hash': _hash_password(password), 'created_at': time.time()}
                _save_users(users)
                token = _create_session(username)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Lax')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'username': username, 'token': token}).encode())
            except Exception as e:
                self._json(500, {'error': str(e)})
            return

        # Login
        if path == '/api/auth/login':
            try:
                b = json.loads(self._body())
                username = b.get('username', '').strip()
                password = b.get('password', '')
                users = _load_users()
                user = users.get(username)
                if not user or user['password_hash'] != _hash_password(password):
                    self._json(401, {'error': 'Invalid username or password'})
                    return
                token = _create_session(username)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', f'session={token}; Path=/; HttpOnly; SameSite=Lax')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'username': username, 'token': token}).encode())
            except Exception as e:
                self._json(500, {'error': str(e)})
            return

        # Logout
        if path == '/api/auth/logout':
            token = self._token()
            if token and token in sessions:
                del sessions[token]
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Set-Cookie', 'session=; Path=/; Max-Age=0')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}).encode())
            return

        # All below require auth
        u = _get_user(self._token())
        if not u:
            self._json(401, {'error': 'Unauthorized'})
            return

        # Save wardrobe
        if path == '/api/wardrobe':
            try:
                items = json.loads(self._body())
                _save_json(_wardrobe_file(u), items)
                self._json(200, {'success': True})
            except Exception as e:
                self._json(400, {'error': str(e)})
            return

        # Log outfit history
        if path == '/api/history':
            try:
                b = json.loads(self._body())
                entry = {
                    'id': secrets.token_hex(8),
                    'outfit_name': b.get('outfit_name', 'My Outfit'),
                    'items': b.get('items', []),
                    'date_worn': b.get('date_worn', time.strftime('%Y-%m-%d')),
                    'occasion': b.get('occasion', ''),
                    'weather': b.get('weather', ''),
                    'notes': b.get('notes', ''),
                    'logged_at': time.time()
                }
                history = _load_json(_history_file(u), [])
                history.insert(0, entry)
                _save_json(_history_file(u), history)
                self._json(200, {'success': True, 'entry': entry})
            except Exception as e:
                self._json(400, {'error': str(e)})
            return

        # Delete history entry
        if path == '/api/history/delete':
            try:
                b = json.loads(self._body())
                history = _load_json(_history_file(u), [])
                history = [h for h in history if h.get('id') != b.get('id')]
                _save_json(_history_file(u), history)
                self._json(200, {'success': True})
            except Exception as e:
                self._json(400, {'error': str(e)})
            return

        # AI Recommend (wardrobe outfits)
        if path == '/api/recommend':
            try:
                b = json.loads(self._body())
                wardrobe_desc = b.get('wardrobe', '')
                occasion = b.get('occasion', 'casual')
                weather = b.get('weather', 'sunny')
                custom_prompt = b.get('_custom_prompt', None)

                if not groq_client:
                    self._json(500, {'error': 'Groq API key not configured. Add GROQ_API_KEY to your .env file.'})
                    return

                if custom_prompt:
                    prompt = custom_prompt
                else:
                    # Extract just the item names for the AI to choose from
                    item_names = [item.split(':')[1].strip().split(' (')[0].strip() for item in wardrobe_desc.split('\n') if item.strip()]
                    item_list = '\n'.join(f'- {name}' for name in item_names)
                    
                    prompt = f"""You are a professional fashion stylist. Create 3 complete outfit combinations from this wardrobe for a {occasion} occasion in {weather} weather.

Available items (use these exact names):
{item_list}

IMPORTANT: Respond with ONLY a valid JSON array. No explanations, no markdown, no backticks. Just the JSON array like this:

[
  {{
    "name": "Outfit name",
    "items": ["exact item name 1", "exact item name 2", "exact item name 3"],
    "reasoning": "Why these items work together"
  }}
]

Rules:
- Use ONLY the exact item names listed above
- Each outfit needs at least one top and one bottom
- Consider color coordination and style compatibility
- Match the occasion and weather"""

                try:
                    completion = groq_client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {'role': 'system', 'content': 'You are a professional fashion stylist. Always respond with valid JSON only, no markdown formatting.'},
                            {'role': 'user', 'content': prompt}
                        ],
                        temperature=0.7,
                        max_tokens=2048
                    )
                except Exception as e:
                    status, message = _groq_error_response(e)
                    self._json(status, {'error': message})
                    return

                ai_response = completion.choices[0].message.content
                print("AI API called successfully for outfit recommendations")
                print(f"AI response: {ai_response[:200]}...")  # Print first 200 chars
                self._json(200, {'result': ai_response})
            except Exception as e:
                self._json(500, {'error': str(e)})
            return

        # AI Recommend2 (stats & travel features)
        if path == '/api/recommend2':
            try:
                b = json.loads(self._body())
                prompt = b.get('prompt', '')

                if not groq_client2:
                    self._json(500, {'error': 'Groq API key not configured. Add GROQ_API_KEY to your .env file.'})
                    return

                try:
                    completion = groq_client2.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {'role': 'system', 'content': 'You are a helpful assistant. Always respond with valid JSON only, no markdown formatting.'},
                            {'role': 'user', 'content': prompt}
                        ],
                        temperature=0.7,
                        max_tokens=2048
                    )
                except Exception as e:
                    status, message = _groq_error_response(e)
                    self._json(status, {'error': message})
                    return

                print("AI API called successfully for stats/travel recommendations")
                self._json(200, {'result': completion.choices[0].message.content})
            except Exception as e:
                self._json(500, {'error': str(e)})
            return

        self._json(404, {'error': 'Not found'})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")


def _create_http_server():
    try:
        return socketserver.TCPServer(("", PORT), MyHandler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE or "PORT" in os.environ:
            raise
        print(f"Port {PORT} is already in use; trying the next available port.")

    for port in range(PORT + 1, 65536):
        try:
            return socketserver.TCPServer(("", port), MyHandler)
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise

    raise OSError(errno.EADDRINUSE, "No available ports found")


with _create_http_server() as httpd:
    actual_port = httpd.server_address[1]
    print(f"StyleAI running at http://localhost:{actual_port}/")
    print("Pages: /login  /app  (Stats & Travel are tabs inside /app)")
    print("Data stored per-user in wardrobe_<user>.json & history_<user>.json")

    if groq_client:
        print(f"Groq API ready -> /api/recommend & /api/recommend2 ({GROQ_MODEL})")
    else:
        print("WARNING: GROQ_API_KEY not set in .env; AI features will not work.")

    httpd.serve_forever()
