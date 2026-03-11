from http.server import BaseHTTPRequestHandler
import os, tempfile, traceback
try:
    from music21 import converter, environment
    us = environment.UserSettings()
    us['musicxmlPath'] = ''
    us['musescoreDirectPNGPath'] = ''
    READY = True
except Exception as e:
    READY = False
    READY_ERR = str(e)
class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()
    def do_POST(self):
        if not READY:
            self._err(500, f'music21 not available: {READY_ERR}')
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            midi_bytes = self.rfile.read(length)
            if not midi_bytes or not midi_bytes[:4] == b'MThd':
                self._err(400, 'Invalid MIDI file (missing MThd header)')
                return
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                f.write(midi_bytes)
                tmp_mid = f.name
            tmp_xml = tmp_mid.replace('.mid', '.musicxml')
            try:
                score = converter.parse(tmp_mid)
                score.write('musicxml', fp=tmp_xml)
                with open(tmp_xml, 'r', encoding='utf-8') as f:
                    xml = f.read()
                body = xml.encode('utf-8')
                self.send_response(200)
                self._cors()
                self.send_header('Content-Type', 'application/xml; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            finally:
                for p in [tmp_mid, tmp_xml]:
                    try: os.unlink(p)
                    except: pass
        except Exception:
            self._err(500, traceback.format_exc())
    def _err(self, code, msg):
        body = msg.encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    def log_message(self, *args):
        pass
