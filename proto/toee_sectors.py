"""Read ToEE .sec files (tile flags/materials) into a global subtile grid."""
import glob, os, struct
import numpy as np

AA = struct.pack('<I', 0xAA0004)


def read_sec_tiles(path):
    b = open(path, 'rb').read()
    p = b.find(AA)
    off = p - 4 - 65536          # tiles end with an int (roof flag) before 0xAA0004
    t = np.frombuffer(b, np.uint8, 65536, off).reshape(4096, 16)
    flags = t[:, 4:8].copy().view('<u4').reshape(64, 64)   # [ly, lx]
    return t[:, 0].reshape(64, 64), flags


def load_map_subtiles(mapdir, missing='walk'):
    """Return kind[3*960, 3*960] indexed [3u+i, 3v+j]: 0 walk, 1 block, 2 flyover; -1 = no sector."""
    K = np.full((2880, 2880), -1, np.int8)
    M = np.full((960, 960), 255, np.uint8)
    for f in glob.glob(os.path.join(mapdir, '*.sec')):
        sid = int(os.path.basename(f)[:-4]); sx, sy = sid & 0x3ffffff, sid >> 26
        mat, fl = read_sec_tiles(f)
        fl = fl.T  # [lx, ly] = [u, v]
        M[sx * 64:(sx + 1) * 64, sy * 64:(sy + 1) * 64] = mat.T
        for i in range(3):
            for j in range(3):
                s = i + 3 * j
                k = np.where(fl & (0x200 << s), 1, np.where(fl & (0x40000 << s), 2, 0))
                K[sx * 192 + i:(sx + 1) * 192:3, sy * 192 + j:(sy + 1) * 192:3] = k
    return K, M
