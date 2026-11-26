"""Regional travel picker for converted world exits (Temple+ Python 2.7)."""
from toee import *
import heapq
import os

ROOT = 'ie_regional_map'
ART = 'art/interface/ie2toee/atlas/'
_window = None
_source = None
_buttons = {}
_labels = {}


def destinations(source):
    import ie_travel_data as data
    import ie_runtime
    import ie_atlas_data as atlas
    # Follow unlocked regional links. The last link supplies the original arrival entrance.
    queue, arrivals = [(0, source)], {}
    hours = {source: 0}
    while queue:
        elapsed, origin = heapq.heappop(queue)
        if elapsed > hours[origin]:
            continue
        for route in data.AREAS[origin]['regions']:
            dst = route.get('dest_area')
            if not route.get('world_jump') or dst not in atlas.LOCATIONS:
                continue
            if atlas.LOCATIONS[dst][0] != atlas.LOCATIONS[source][0]:
                continue
            gate = route.get('requires_global')
            if gate and not ie_runtime.get_var(None, gate, 'GLOBAL'):
                continue
            cost = elapsed + route.get('travel_hours', 0)
            if dst in hours and hours[dst] <= cost:
                continue
            hours[dst] = cost
            arrivals[dst] = (route, cost)
            heapq.heappush(queue, (cost, dst))
    return arrivals


def close():
    global _source
    _source = None
    if _window is not None:
        _window.hide()


def active():
    return _source is not None


def select(area):
    import ie_travel, ie_travel_data as data
    if _source is None:
        return False
    if data.BY_MAP.get(game.leader.map) != _source or game.combat_is_active():
        close()
        return False
    arrival = destinations(_source).get(area)
    if arrival is None:
        return False
    close()
    route, hours = arrival
    ie_travel.travel(route, hours)
    return True


def _screen():
    cfg = {}
    path = os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'TemplePlus', 'TemplePlus.ini')
    if os.path.isfile(path):
        with open(path) as source:
            for line in source:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    cfg[key.lower()] = value
    return int(cfg.get('renderwidth') or 1024), int(cfg.get('renderheight') or 768)


def _make():
    import tpgui
    import ie_atlas_data as atlas
    global _window, _title, _chart, _map_box
    w, h = _screen()
    _window = tpgui._add_root_container(ROOT, w, h)
    _window.hide()
    backdrop = _window.add_image('art/interface/ie2toee/cs_bar.tga')
    backdrop.width, backdrop.height = w, h
    shield = tpgui._add_button(ROOT, ROOT + '_background', w, h)
    shield.set_click_handler(lambda: None)
    margin, side = 20, min(230, w // 3)
    _map_box = (margin, margin + 42, w - side - 3 * margin, h - 2 * margin - 42)
    panel = tpgui._add_container(ROOT, ROOT + '_chart', w, h)
    _chart = panel.add_image(ART + 'chart%d.tga' % min(atlas.SIZES))
    x = w - side - margin
    title = panel.add_text('World Map', 'priory-title')
    title.x, title.y, title.width = margin, margin, 95
    _title = panel.add_text('')
    _title.x, _title.y, _title.width = margin + 115, margin, side
    for area in sorted(atlas.LOCATIONS):
        marker = tpgui._add_button(ROOT, ROOT + '_pin_' + area, 24, 24)
        style = marker.style
        style.image_normal = ART + area + '.tga'
        style.image_hovered = ART + area + '_hover.tga'
        style.image_pressed = style.image_normal
        marker.style = style
        action = lambda dest=area: select(dest)
        marker.set_click_handler(action)
        label = tpgui._add_button(ROOT, ROOT + '_label_' + area, 120, 20)
        label_style = label.style
        label_style.image_normal = 'art/interface/ie2toee/cs_wash.tga'
        label_style.image_hovered = 'art/interface/ie2toee/cs_bar.tga'
        label_style.text_style = 'chargen-button-text'
        label.style = label_style
        label.set_text(atlas.LOCATIONS[area][1])
        label.set_click_handler(action)
        _labels[area] = label
        row = tpgui._add_button(ROOT, ROOT + '_row_' + area, side, 32)
        row.set_style_id('chargen-button')
        row.width, row.height = side, 32
        row.x = x
        row.set_text(atlas.LOCATIONS[area][1])
        row.set_click_handler(action)
        _buttons[area] = (marker, row)
    cancel = tpgui._add_button(ROOT, ROOT + '_close', side, 32)
    cancel.set_style_id('chargen-button')
    cancel.x, cancel.y, cancel.width, cancel.height = x, h - margin - 32, side, 32
    cancel.set_text('Cancel')
    cancel.set_click_handler(close)


def show(source):
    import ie_atlas_data as atlas
    global _source
    if source not in atlas.LOCATIONS or game.combat_is_active():
        return
    if _window is None:
        _make()
    page, name = atlas.LOCATIONS[source][:2]
    cw, ch = atlas.SIZES[page]
    x, y, w, h = _map_box
    scale = min(w / float(cw), h / float(ch))
    width, height = int(cw * scale), int(ch * scale)
    x, y = x + (w - width) // 2, y + (h - height) // 2
    _chart.set_image(ART + 'chart%d.tga' % page)
    _chart.x, _chart.y, _chart.width, _chart.height = x, y, width, height
    _title.set_text('Current location: ' + name)
    available = destinations(source)
    row_y = 120
    for area in sorted(_buttons, key=lambda a: atlas.LOCATIONS[a][1]):
        marker, row = _buttons[area]
        marker.visible = area == source or area in available
        label = _labels[area]
        label.visible = marker.visible
        row.visible = area in available
        marker.disabled = area == source
        if marker.visible:
            ax, ay, aw, ah = atlas.LOCATIONS[area][2:]
            marker.x, marker.y = x + int(ax * scale), y + int(ay * scale)
            marker.width, marker.height = max(1, int(aw * scale)), max(1, int(ah * scale))
            label.width = min(w, max(86, 10 + len(atlas.LOCATIONS[area][1]) * 7))
            label.height = 22
            label.x = max(x, min(x + width - label.width, marker.x + (marker.width - label.width) // 2))
            label.y = min(y + height - label.height, marker.y + marker.height + 1)
        if row.visible:
            hours = available[area][1]
            label = atlas.LOCATIONS[area][1]
            row.set_text('%s (%dh)' % (label, hours) if hours else label)
            row.width, row.height = _title.width, 32
            row.y = row_y
            row_y += 38
    _source = source
    _window.show()
    _window.bring_to_front()
    print('IE_ATLAS %s offers %s' % (source, sorted(available)))
