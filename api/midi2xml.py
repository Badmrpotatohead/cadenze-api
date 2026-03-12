from http.server import BaseHTTPRequestHandler
import os, tempfile, traceback
try:
    from music21 import converter, environment, stream, note, chord, instrument
    us = environment.UserSettings()
    us['musicxmlPath'] = ''
    us['musescoreDirectPNGPath'] = ''
    READY = True
except Exception as e:
    READY = False
    READY_ERR = str(e)
SPLIT_MIDI = 60  # C4 — notes >= 60 go treble, < 60 go bass
def to_grand_staff(score):
    try:
        treble = stream.Part()
        bass = stream.Part()
        treble.insert(0, instrument.Piano())
        bass.insert(0, instrument.Piano())
        # Copy time/key signatures from first part
        first = score.parts[0] if score.parts else None
        if first:
            for el in first.flatten().getElementsByClass(['TimeSignature','KeySignature']):
                treble.insert(el.offset, el)
                bass.insert(el.offset, el)
        # Collect all notes from all parts
        for part in score.parts:
            for el in part.flatten().notesAndRests:
                if isinstance(el, note.Rest):
                    pass  # skip rests, music21 will fill
                elif isinstance(el, note.Note):
                    target = treble if el.pitch.midi >= SPLIT_MIDI else bass
                    n = note.Note(el.pitch, quarterLength=el.quarterLength)
                    target.insert(el.offset, n)
                elif isinstance(el, chord.Chord):
                    hi = [p for p in el.pitches if p.midi >= SPLIT_MIDI]
                    lo = [p for p in el.pitches if p.midi < SPLIT_MIDI]
                    if hi:
                        c = chord.Chord(hi, quarterLength=el.quarterLength)
                        treble.insert(el.offset, c)
                    if lo:
                        c = chord.Chord(lo, quarterLength=el.quarterLength)
                        bass.insert(el.offset, c)
        out = stream.Score()
        out.insert(0, treble)
        out.insert(0, bass)
        return out
    except Exception as e:
        print(f'to_grand_staff failed: {e}')
        return score  # fallback to original
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
            if not midi_bytes or midi_bytes[:4] != b'MThd':
                self._err(400, 'Invalid MIDI file (missing MThd header)')
                return
            with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
                f.write(midi_bytes)
                tmp_mid = f.name
            tmp_xml = tmp_mid.replace('.mid', '.musicxml')
            try:
                score = converter.parse(tmp_mid)
                score = to_grand_staff(score)
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
