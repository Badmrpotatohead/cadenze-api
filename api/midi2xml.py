from http.server import BaseHTTPRequestHandler
import os, tempfile, traceback
try:
    from music21 import converter, environment, stream, instrument
    us = environment.UserSettings()
    us['musicxmlPath'] = ''
    us['musescoreDirectPNGPath'] = ''
    READY = True
except Exception as e:
    READY = False
    READY_ERR = str(e)
def midi_to_grand_staff(score):
    """Reduce a multi-part score to a 2-part piano grand staff."""
    try:
        # Collect all notes/chords from all parts into treble and bass
        treble_part = stream.Part()
        bass_part = stream.Part()

        treble_part.insert(0, instrument.Piano())
        bass_part.insert(0, instrument.Piano())
        # Split notes by pitch: C4 (midi 60) and above → treble, below → bass
        SPLIT = 60
        all_notes = []
        for part in score.parts:
            for el in part.flatten().notesAndRests:
                all_notes.append(el)
        # Sort by offset
        all_notes.sort(key=lambda n: float(n.offset))
        for el in all_notes:
            from music21 import note, chord
            if isinstance(el, note.Rest):
                treble_part.append(el)
            elif isinstance(el, note.Note):
                if el.pitch.midi >= SPLIT:
                    treble_part.append(el)
                else:
                    bass_part.append(el)
            elif isinstance(el, chord.Chord):
                # Split chord: high notes treble, low notes bass
                treble_notes = [n for n in el.notes if n.pitch.midi >= SPLIT]
                bass_notes   = [n for n in el.notes if n.pitch.midi < SPLIT]
                if treble_notes:
                    c = chord.Chord(treble_notes, quarterLength=el.quarterLength)
                    c.offset = el.offset
                    treble_part.append(c)
                if bass_notes:
                    c = chord.Chord(bass_notes, quarterLength=el.quarterLength)
                    c.offset = el.offset
                    bass_part.append(c)
        grand = stream.Score()
        grand.insert(0, treble_part)
        grand.insert(0, bass_part)
        return grand
    except Exception as e:
        # If reduction fails, return original score
        print(f'Grand staff reduction failed: {e}, returning original')
        return score
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
                # Parse MIDI
                score = converter.parse(tmp_mid)
                # Reduce to grand staff (treble + bass)
                score = midi_to_grand_staff(score)
                # Write MusicXML
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
