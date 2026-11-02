"""Generated UI textures the converted module needs (nothing from the IE game): the cutscene letterbox
(ie_cutscene._letterbox) <module>/art/interface/ie2toee/cs_bar.tga (opaque black) and cs_wash.tga (black, ~25% alpha)."""
import os, struct, sys

def _tga(w, h, a):
    return struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, 32, 8 | 0x20) + bytes([0, 0, 0, a]) * (w * h)

def write_ui_art(module_dir):
    d = os.path.join(module_dir, 'art', 'interface', 'ie2toee'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'cs_bar.tga'), 'wb').write(_tga(16, 16, 255))
    open(os.path.join(d, 'cs_wash.tga'), 'wb').write(_tga(16, 16, 64))

if __name__ == '__main__':
    write_ui_art(sys.argv[1])
