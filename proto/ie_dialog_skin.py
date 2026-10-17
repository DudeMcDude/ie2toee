#!/usr/bin/env python3
"""Export an Infinity Engine dialogue-window skin for Temple+ from the player's own install.

Reads the GUI resources of a classic (IWD/BG/IWD2 CHU) or Enhanced Edition (UI.MENU + BGEE.lua) install and writes,
into the player's ToEE module:

  art/interface/dialog_ie/<skin>/skin.json      layout (panel-relative rects), font, colours, art paths
  art/interface/dialog_ie/<skin>/*.tga           panel background (from MOS), buttons and scrollbar (from BAM)
  art/interface/dialog_ie/skins.json             which conversations use which skin (per module and per dialog id)
  art/interface/dialog_ie/portraits/<cre>.tga    IE portraits of converted speakers (when their CRE has one)
  fonts/*.ttf                                    the dialogue font: EE TTF copied, classic BAM font converted (iebamfont)

Two layouts are produced:
  iwdee   the EE "WORLD_DIALOG" menu: bordered panel at the bottom, portrait, NPC text, reply list, log-history toggle,
          Continue / End Dialogue button below the panel
  iwd     the classic expanded message window (CHU window with the GUIWBTP3-style background): one scrolling text area
          holding the conversation log, the current NPC line and the numbered replies
Everything is derived from the player's files at install time; nothing here (or in the output) gets redistributed.
Formats from IESDP (CHU V1, MOS V1/V2, BAM V1/V2); the EE menu syntax is read as plain text.

Usage:
  ie_dialog_skin.py <IE install> <out dir> [--skin iwdee|iwd|auto] [--default SKIN] [--dialog ID[:SKIN]]...
                    [--portrait ID:CRE]... [--lang en_US]
"""
import argparse, json, os, re, struct, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iefs import IEGame
from iegui import Chu, Bam, decode_mos, pvrz_loader_for
from ieformats import cstr

ART = 'art/interface/dialog_ie'


# ----------------------------------------------------------------------------- EE menu text
def _tokens(src):
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif src.startswith('--', i):                       # Lua-style comment line
            j = src.find('\n', i); i = n if j < 0 else j
        elif c == '`':                                      # raw Lua chunk between menus
            j = src.find('`', i + 1); i = n if j < 0 else j + 1
        elif c in '"\'':
            j = src.find(c, i + 1)
            j = n if j < 0 else j
            yield ('str', src[i + 1:j]); i = j + 1
        elif c in '{}':
            yield (c, c); i += 1
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in '{}"\'`':
                j += 1
            yield ('word', src[i:j]); i = j


def parse_menu(src):
    """UI.MENU -> list of blocks {'kind', 'props': {key: [values]}, 'children': [...]} (top level: menus)."""
    root = {'kind': 'root', 'props': {}, 'children': []}
    stack, line = [root], []
    for kind, val in _tokens(src):
        if kind == '{':
            name = line[-1] if line else 'block'
            blk = {'kind': name.lower(), 'props': {}, 'children': []}
            stack[-1]['children'].append(blk); stack.append(blk); line = []
        elif kind == '}':
            if len(stack) > 1:
                stack.pop()
            line = []
        else:
            line.append(val)
            # property lines: keyword followed by values; store by first word, keep appending
            if len(line) >= 2 and kind != 'word' or (len(line) >= 2 and line[0].lower() in ('area', 'offset', 'align')):
                pass
            stack[-1].setdefault('_raw', []).append((kind, val))
    for blk in _walk(root):
        blk['props'] = _props(blk.pop('_raw', []))
    return root['children']


_KEYS = {'name', 'area', 'offset', 'align', 'text', 'bam', 'mosaic', 'scrollbar', 'rectangle', 'enabled', 'frame',
         'bitmap', 'sequence', 'sequenceonce', 'clickable', 'tooltip', 'rowheight', 'table', 'var', 'width', 'action',
         'on', 'pulse', 'actiondrag', 'actionenter', 'actionexit', 'onopen', 'onclose', 'ignoreesc', 'hidehighlight',
         'glow', 'pad', 'fill', 'actionalt', 'actiondbl', 'opacity', 'icon', 'count', 'usefontzoom'}


def _props(raw):
    props, key = {}, None
    for kind, val in raw:
        if kind == 'word' and val.lower() in _KEYS:
            key = val.lower(); props.setdefault(key, [])
        elif key:
            props[key].append(val)
    return props


def _walk(b):
    yield b
    for c in b['children']:
        yield from _walk(c)


def find_menu(menus, name):
    for m in menus:
        if m['kind'] == 'menu' and m['props'].get('name', [''])[0] == name:
            return m
    return None


def item(menu, name):
    for b in _walk(menu):
        if b['props'].get('name', [''])[0] == name:
            return b
    return None


def area(b):
    return [int(v) for v in b['props']['area'][:4]]


def lua_tables(src):
    """fontcolors['X'] = 'AABBGGRR' and styles.<name> = { color=..., font=..., point=... } from BGEE.lua."""
    colors = dict(re.findall(r"fontcolors\['(.)'\]\s*=\s*'([0-9A-Fa-f]{8})'", src))
    styles = {}
    m = re.search(r'\bstyles\s*=\s*\{', src)
    if m:
        for sm in re.finditer(r'(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}', src[m.end():m.end() + 20000]):
            fields = dict(re.findall(r"(\w+)\s*=\s*'?([^,'\n]+)'?", sm.group(2)))
            styles[sm.group(1)] = {k: v.strip() for k, v in fields.items()}
    return colors, styles


def abgr_to_argb(s):
    """EE colour strings are AABBGGRR (comment in BGEE.lua) -> AARRGGBB for Temple+."""
    a, b, g, r = s[0:2], s[2:4], s[4:6], s[6:8]
    return (a + r + g + b).upper()


# ----------------------------------------------------------------------------- art helpers
def save_tga(rgba, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.ascontiguousarray(rgba), 'RGBA').save(path, format='TGA', compression=None)


def crop_alpha(rgba):
    ys, xs = np.nonzero(rgba[..., 3] > 0)
    if not len(ys):
        return rgba
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def nine_slice(src, w, h, l=18, t=8, r=18, b=18):
    """Resize a framed panel to w x h keeping its border: corners copied, edges and centre stretched."""
    sh, sw = src.shape[:2]
    img = Image.fromarray(src)
    out = Image.new('RGBA', (w, h))

    def part(x0, y0, x1, y1, dw, dh):
        p = img.crop((x0, y0, x1, y1))
        return p if p.size == (dw, dh) else p.resize((max(dw, 1), max(dh, 1)), Image.BILINEAR)
    cols = [(0, l, 0, l), (l, sw - r, l, w - r), (sw - r, sw, w - r, w)]
    rows = [(0, t, 0, t), (t, sh - b, t, h - b), (sh - b, sh, h - b, h)]
    for sx0, sx1, dx0, dx1 in cols:
        for sy0, sy1, dy0, dy1 in rows:
            out.paste(part(sx0, sy0, sx1, sy1, dx1 - dx0, dy1 - dy0), (dx0, dy0))
    return np.asarray(out)


class Exporter:
    def __init__(self, root, out, lang='en_US'):
        self.g = IEGame(root)
        self.pvrz = pvrz_loader_for(self.g)
        self.out = out
        self.ee = self.g.exists('ui', 'menu')
        self.lang = lang
        self.written = []

    def path(self, *p):
        return os.path.join(self.out, 'modules', 'ToEE', *p)

    def vfs(self, skin, name):  # path as Temple+ sees it
        return '%s/%s/%s' % (ART, skin, name) if skin else '%s/%s' % (ART, name)

    def tga(self, rgba, skin, name):
        save_tga(rgba, self.path(*self.vfs(skin, name).split('/')))
        self.written.append(self.vfs(skin, name))
        return self.vfs(skin, name).replace('/', '\\')

    def mos(self, ref):
        return decode_mos(self.g.read(ref, 'mos'), self.pvrz)

    def bam(self, ref):
        return Bam(self.g.read(ref, 'bam'), self.pvrz)

    def bam_frames(self, skin, ref, cycle, frames, prefix, crop=True):
        b = self.bam(ref)
        paths = []
        for k, fi in enumerate(frames):
            f = b.frame(cycle, fi)
            if f is None:
                break
            paths.append(self.tga(crop_alpha(f) if crop else f, skin, '%s_%d.tga' % (prefix, k)))
        return paths

    def tlk_strings(self):
        try:
            from iescript import Tlk, find_tlk
            p = find_tlk(self.g.root, lang=self.lang)
            t = Tlk.load(p) if p else None
        except Exception:
            t = None
        end = t.get(9371) if t else ''
        cont = t.get(9372) if t else ''
        return (cont or 'Continue'), (end or 'End Dialogue')

    def guiw_message_window(self):
        """Classic expanded message window: the GUIW.CHU window whose background is the big message panel
        (GUIWBTP3 in IWD) or, failing that, the window with the tallest text area."""
        chu = Chu(self.g.read('guiw', 'chu'))
        best = None
        for w in chu.windows:
            tas = [c for c in w['controls'] if c['type'] == 'textarea']
            if not tas or not w['mos']:
                continue
            score = (w['mos'].lower() == 'guiwbtp3', max(c['h'] for c in tas))
            if best is None or score > best[0]:
                best = (score, w)
        return best[1] if best else None

    def scrollbar_art(self, skin, ref):
        b = self.bam(ref)
        names = ['up', 'up_pressed', 'down', 'down_pressed', 'knob', 'trough']
        out = {}
        for k, n in enumerate(names):
            f = b.frame(0, k)
            if f is not None:
                out[n] = self.tga(crop_alpha(f), skin, 'scroll_%s.tga' % n)
        return out

    # ------------------------------------------------------------------ skins
    def skin_iwd(self, font_face, font_point, colors):
        skin = 'iwd'
        w = self.guiw_message_window()
        if not w:
            raise RuntimeError('no message window in GUIW.CHU')
        ta = max((c for c in w['controls'] if c['type'] == 'textarea'), key=lambda c: c['h'])
        sb = next((c for c in w['controls'] if c['type'] == 'scrollbar' and c['id'] == ta.get('scrollbar')), None)
        btn = next((c for c in w['controls'] if c['type'] == 'button'), None)
        panel = self.mos(w['mos'])
        js = {
            'name': skin, 'layout': 'log',
            'source': 'GUIW.CHU window %d (%s)' % (w['id'], w['mos']),
            'design': self.chu_extent(),
            'panel': {'image': self.tga(panel, skin, 'panel.tga'), 'w': int(panel.shape[1]), 'h': int(panel.shape[0]),
                      'bottom': 58},
            'text': {'rect': [ta['x'], ta['y'], ta['w'], ta['h']]},
            'font': dict(font_face, point=font_point, fallback='Junicode'),
            'colors': colors,
        }
        if sb:
            js['scrollbar'] = {'rect': [sb['x'], sb['y'], sb['w'], sb['h']], 'art': self.scrollbar_art(skin, sb['bam'])}
        if btn:
            js['history_button'] = {'rect': [btn['x'], btn['y'], btn['w'], btn['h']],
                                    'frames': self.bam_frames(skin, btn['bam'], btn['cycle'],
                                                              [btn['frames']['up'], btn['frames']['down']], 'hist')}
        return skin, js

    def skin_iwdee(self, colors, styles, fontcolors):
        skin = 'iwdee'
        menus = parse_menu(self.g.read('ui', 'menu').decode('latin-1'))
        dm, cm = find_menu(menus, 'WORLD_DIALOG'), find_menu(menus, 'WORLD_DIALOG_CONFIRM')
        bg = area(item(dm, 'worldDialogBackground'))
        por = area(item(dm, 'worldDialogPortraitArea'))
        npc = area(item(dm, 'worldNPCDialog'))
        lst = area(item(dm, 'worldPlayerDialogChoicesList'))
        msg = area(item(dm, 'worldDialogMessageBox'))
        hb = item(dm, 'worldDialogShowMessagesButton')
        offset = [int(v) for v in dm['props'].get('offset', ['0', '0'])[:2]]
        # EE draws this panel as an engine "rectangle" style; rebuild it from the install's own framed message-window
        # background (same frame art the classic layout uses), resized to the menu's area.
        w = self.guiw_message_window()
        src = self.mos(w['mos'])
        panel = nine_slice(src, bg[2], bg[3])
        hist = nine_slice(src, msg[2] + 2 * msg[0] - 0, msg[3] + 16)
        cont_btn = next(b for b in _walk(cm) if b['kind'] == 'button')
        cb = area(cont_btn)
        cont_bam = cont_btn['props']['bam'][0]
        cont, end = self.tlk_strings()
        btn_style = styles.get('button', {})
        js = {
            'name': skin, 'layout': 'panel',
            'source': 'UI.MENU WORLD_DIALOG / WORLD_DIALOG_CONFIRM; background rebuilt from %s' % w['mos'],
            'design': [1024, 768],                          # EE menus are laid out for 1024x768 and up
            'panel': {'image': self.tga(panel, skin, 'panel.tga'), 'w': bg[2], 'h': bg[3], 'bottom': -offset[1]},
            'portrait': {'rect': por},
            'npc_text': {'rect': npc},
            'replies': {'rect': lst, 'gap': 2},
            'history': {'image': self.tga(hist, skin, 'history.tga'), 'rect': [0, msg[1] - 8, bg[2], msg[3] + 16],
                        'text_rect': [msg[0], 8, msg[2], msg[3]]},
            'continue': {'rect': [-(cb[2] // 2), -cb[3], cb[2], cb[3]],     # bottom-centre of the screen
                         'frames': self.bam_frames(skin, cont_bam, 0, [0, 1, 2, 3], 'continue', crop=False),
                         'text_continue': cont, 'text_end': end,
                         'font': dict(self.font_face(btn_style.get('font', 'STONESML')),
                                      point=float(btn_style.get('point', 14)), upper=btn_style.get('upper') == '1'),
                         'color': abgr_to_argb(fontcolors.get(btn_style.get('color', 'B'), 'FFCECECE'))},
            'font': dict(self.font_face(styles.get('gamelog', {}).get('font', 'POSTANTI')),
                         point=float(styles.get('gamelog', {}).get('point', 12)), fallback='Junicode'),
            'colors': colors,
        }
        if hb is not None and hb['props'].get('bam'):
            a = area(hb)
            js['history_button'] = {'rect': a, 'frames': self.bam_frames(skin, hb['props']['bam'][0], 0, [0, 1], 'hist')}
            # the EE wraps the NPC text short of this button; keep the first lines clear of it
            if npc[1] < a[1] + a[3] and npc[0] + npc[2] > a[0]:
                js['npc_text']['rect'] = [npc[0], npc[1], a[0] - npc[0] - 4, npc[3]]
        sbref = item(dm, 'worldNPCDialog')['props'].get('scrollbar', ['GUISCRC'])[0]
        js['scrollbar'] = {'art': self.scrollbar_art(skin, sbref)}
        return skin, js

    def font_face(self, ref):
        """EE fonts are TTF resources: copy the player's file into fonts/ and return {'face': family, 'file': path}
        (Temple+ adds the file itself when the module folder wasn't mounted yet at its startup font scan)."""
        data = self.g.read(ref.lower(), 'ttf')
        dst = self.path('fonts', 'ie_%s.ttf' % ref.lower())
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        self.written.append('fonts/ie_%s.ttf' % ref.lower())
        return {'face': ttf_family(data) or ref, 'file': 'fonts\\ie_%s.ttf' % ref.lower()}

    def bam_font_face(self):
        """Classic: convert the message window's BAM font (CHU text area font, usually NORMAL) to fonts/ie_<ref>.ttf.
        point = the bitmap line height, so 1 font pixel = 1 GUI pixel at the CHU design resolution."""
        from iebamfont import bam_to_ttf
        ref = 'normal'
        try:
            w = self.guiw_message_window()
            ta = max((c for c in w['controls'] if c['type'] == 'textarea'), key=lambda c: c['h'])
            ref = (ta.get('font') or ref).lower()
        except Exception:
            pass
        try:
            data = self.g.read(ref, 'bam')
        except Exception:
            return {'face': 'Junicode'}, 12.0
        family = 'IE %s' % ref.upper()
        dst = self.path('fonts', 'ie_%s.ttf' % ref)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        m = bam_to_ttf(Bam(data), family, dst)
        self.written.append('fonts/ie_%s.ttf' % ref)
        return {'face': family, 'file': 'fonts\\ie_%s.ttf' % ref, 'source': ref.upper() + '.BAM'}, float(m['line_px'])

    def chu_extent(self):
        """GUI resolution the classic CHU layout was made for (bottom-right corner of its windows)."""
        chu = Chu(self.g.read('guiw', 'chu'))
        return [max(w['x'] + w['w'] for w in chu.windows), max(w['y'] + w['h'] for w in chu.windows)]

    def run(self, which, dialogs, default, portraits):
        skins = {}
        if self.ee:
            fontcolors, styles = lua_tables(self.g.read('bgee', 'lua').decode('latin-1'))
            menu_src = self.g.read('ui', 'menu').decode('latin-1')
            m = re.search(r'gsub\(text,\s*"%\^0x([0-9A-Fa-f]{8})"\s*,\s*"\^0x([0-9A-Fa-f]{8})"', menu_src)
            reply, reply_sel = (m.group(1), m.group(2)) if m else ('ff212eff', 'FFFFFFFF')
            gl = styles.get('gamelog', {})
            colors = {'npc_text': abgr_to_argb(fontcolors.get(gl.get('color', 'B'), 'FFCECECE')),
                      'npc_name': abgr_to_argb(fontcolors.get('$', 'FF82E6FF')),
                      'reply': abgr_to_argb(reply), 'reply_hover': abgr_to_argb(reply_sel),
                      'reply_down': abgr_to_argb(reply_sel),
                      'history_pc': abgr_to_argb(fontcolors.get('9', 'FFCDD6D9')),
                      'history_npc': abgr_to_argb(fontcolors.get(gl.get('color', 'B'), 'FFCECECE'))}
            face, point = self.font_face(gl.get('font', 'POSTANTI')), float(gl.get('point', 12))
        else:
            # classic engines hard-code their text colours; these are the defaults, editable in skin.json
            colors = {'npc_text': 'FFE0E0E0', 'npc_name': 'FFFFE682', 'reply': 'FFFF2E21', 'reply_hover': 'FFFFFFFF',
                      'reply_down': 'FFFFFFFF', 'history_pc': 'FFA0A0A0', 'history_npc': 'FFC8C8C8'}
            face, point = self.bam_font_face()      # classic fonts are BAM bitmaps -> pixel-outline TTF
        if which in ('iwdee', 'auto', 'all') and self.ee:
            k, js = self.skin_iwdee(colors, styles, fontcolors); skins[k] = js
        if which in ('iwd', 'all') or (which == 'auto' and not self.ee):
            k, js = self.skin_iwd(face, point, colors); skins[k] = js
        for k, js in skins.items():
            self.write_json(js, k, 'skin.json')
        sel = {'default': default or '', 'dialogs': {}, 'portraits': {}}
        first = next(iter(skins), '')
        for d in dialogs:
            ident, _, sk = d.partition(':')
            sel['dialogs'][str(int(ident))] = sk or first
        for p in portraits:
            ident, _, cre = p.partition(':')
            tex = self.portrait(cre)
            if tex:
                sel['portraits'][str(int(ident))] = tex
        sel_path = self.path(*ART.split('/'), 'skins.json')
        if os.path.exists(sel_path):                         # merge with earlier runs
            old = json.load(open(sel_path))
            for key in ('dialogs', 'portraits'):
                old.setdefault(key, {}).update(sel[key])
            if default:
                old['default'] = default
            sel = old
        self.write_json(sel, '', 'skins.json')
        return skins, sel

    def portrait(self, cre):
        d = self.g.read(cre, 'cre')
        if d[:8] != b'CRE V1.0':
            return None
        for off in (0x34, 0x3C):                             # small, large portrait resrefs
            ref = cstr(d[off:off + 8]).lower()
            if ref and ref != 'none' and self.g.exists(ref, 'bmp'):
                import io
                img = np.asarray(Image.open(io.BytesIO(self.g.read(ref, 'bmp'))).convert('RGBA'))
                return self.tga(img, 'portraits', '%s.tga' % cre.lower())
        return None

    def write_json(self, obj, skin, name):
        p = self.path(*self.vfs(skin, name).split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(obj, open(p, 'w'), indent=1)
        self.written.append(self.vfs(skin, name))


def ttf_family(data):
    """Family name (name id 1) from a TrueType 'name' table."""
    try:
        n = struct.unpack_from('>H', data, 4)[0]
        for i in range(n):
            tag, _, off, ln = struct.unpack_from('>4sIII', data, 12 + i * 16)
            if tag == b'name':
                cnt, soff = struct.unpack_from('>HH', data, off + 2)
                best = None
                for k in range(cnt):
                    pid, eid, lid, nid, l, o = struct.unpack_from('>6H', data, off + 6 + k * 12)
                    if nid != 1:
                        continue
                    raw = data[off + soff + o:off + soff + o + l]
                    s = raw.decode('utf-16-be', 'replace') if pid in (0, 3) else raw.decode('latin-1')
                    if pid == 3 or best is None:
                        best = s
                return best
    except struct.error:
        pass
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('install'); ap.add_argument('out')
    ap.add_argument('--skin', default='auto', choices=['auto', 'all', 'iwdee', 'iwd'])
    ap.add_argument('--default', default='', help='skin for every conversation of the module (default: none)')
    ap.add_argument('--dialog', action='append', default=[], help='DIALOG_ID[:SKIN] (ToEE dlg/script id)')
    ap.add_argument('--portrait', action='append', default=[], help='DIALOG_ID:CRE (use the CRE\'s IE portrait)')
    ap.add_argument('--lang', default='en_US')
    a = ap.parse_args(argv)
    ex = Exporter(a.install, a.out, a.lang)
    skins, sel = ex.run(a.skin, a.dialog, a.default, a.portrait)
    for k, js in skins.items():
        print('skin %s: %s' % (k, js['source']))
    print('selection:', json.dumps(sel))
    print('%d files under %s' % (len(ex.written), os.path.join(a.out, 'modules', 'ToEE')))


if __name__ == '__main__':
    main()
