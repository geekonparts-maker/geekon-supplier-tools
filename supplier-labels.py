# -*- coding: utf-8 -*-
"""
GeekOn Supplier Labels
======================
Αυτόνομο πρόγραμμα εκτύπωσης ετικετών για προμηθευτές / Standalone label
printing tool for suppliers.

- Ετικέτες 25×15mm (προσαρμόσιμο) στα πρότυπα GeekOn: SKU → Code 128 ή QR
- Απευθείας εκτύπωση (χωρίς driver γραφικών) σε:
    • Xprinter / TSPL εκτυπωτές (π.χ. XP-236B)
    • Zebra / ZPL εκτυπωτές (ZD220, ZD230 κ.ά.)
- Ζωντανή προεπισκόπηση, λίστα μαζικής εκτύπωσης (SKU;Κείμενο;Ποσότητα)
- Δουλεύει τελείως τοπικά — χωρίς internet, χωρίς server.

Εκτελείται ως έτοιμο .exe (PyInstaller) ή με Python 3.10+ και:
    pip install pillow qrcode
"""

import json
import os
import subprocess
import sys
import threading

from PIL import Image, ImageDraw, ImageFont, ImageTk

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

try:
    import qrcode
    HAS_QR = True
except Exception:
    HAS_QR = False

VERSION = "1.0.0"
DPM = 8  # κουκκίδες ανά mm (203 dpi)


# ---------------------------------------------------------------------------
# Ρυθμίσεις
# ---------------------------------------------------------------------------
def config_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "GeekOnSupplierLabels")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.expanduser("~")
    return os.path.join(d, "config.json")


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Code 128
# ---------------------------------------------------------------------------
_C128 = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232", "2331112",
]


def code128_widths(data):
    if not data:
        return []
    if data.isdigit() and len(data) % 2 == 0:
        start = 105
        values = [int(data[i:i + 2]) for i in range(0, len(data), 2)]
    else:
        start = 104
        values = []
        for ch in data:
            o = ord(ch)
            if not 32 <= o <= 126:
                o = ord("?")
            values.append(o - 32)
    check = start
    for i, v in enumerate(values, start=1):
        check += v * i
    codes = [start] + values + [check % 103, 106]
    out = []
    for c in codes:
        out.extend(int(d) for d in _C128[c])
    return out


# ---------------------------------------------------------------------------
# Γραμματοσειρές
# ---------------------------------------------------------------------------
def _font(px, bold=False):
    names = (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["arial.ttf", "DejaVuSans.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except Exception:
            pass
    try:
        return ImageFont.load_default(px)
    except Exception:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Σχεδίαση ετικέτας (αμιγώς ασπρόμαυρη, 1 pixel = 1 κουκκίδα 203dpi)
# ---------------------------------------------------------------------------
def render_label(w_mm, h_mm, sku, text="", bc_type="bar", show_sku=True):
    W, H = round(w_mm * DPM), round(h_mm * DPM)
    img = Image.new("L", (W, H), 255)
    dr = ImageDraw.Draw(img)
    pad = round(1.2 * DPM)
    avail_w = W - 2 * pad
    sku = (sku or "").strip()
    text = (text or "").strip()

    # ---- μετρήσεις μπλοκ
    text_px = max(14, min(26, H // 5))
    sku_px = max(14, min(22, H // 6))
    gap = 4
    blocks_h = 0
    if text:
        blocks_h += text_px + gap
    qr_img = None
    widths = None
    mod = 0
    bar_h = 0
    if sku:
        if bc_type == "qr" and HAS_QR:
            q = qrcode.QRCode(border=0, box_size=1,
                              error_correction=qrcode.constants.ERROR_CORRECT_L)
            q.add_data(sku)
            q.make(fit=True)
            m = q.get_matrix()
            n = len(m)
            side_limit = min(avail_w, H - 2 * pad - blocks_h
                             - ((sku_px + 2) if show_sku else 0))
            mod = max(2, min(10, side_limit // n))
            qr_img = (m, n)
            blocks_h += n * mod + ((sku_px + 2) if show_sku else 0)
        else:
            widths = code128_widths(sku)
            total = sum(widths)
            # πάχος γραμμής: το μεγαλύτερο που χωράει ΜΑΖΙ με quiet zones
            mod = 4
            while mod > 1 and total * mod + 2 * max(10 * mod, 16) > avail_w:
                mod -= 1
            bar_h = H - 2 * pad - blocks_h - ((sku_px + 2) if show_sku else 0)
            bar_h = max(24, bar_h)
            blocks_h += bar_h + ((sku_px + 2) if show_sku else 0)

    y = max(pad, (H - blocks_h) // 2)

    if text:
        f = _font(text_px, bold=True)
        tw = dr.textlength(text, font=f)
        while tw > avail_w and text_px > 10:
            text_px -= 2
            f = _font(text_px, bold=True)
            tw = dr.textlength(text, font=f)
        dr.text(((W - tw) // 2, y), text, font=f, fill=0)
        y += text_px + gap

    if sku and qr_img:
        m, n = qr_img
        size = n * mod
        x0 = (W - size) // 2
        for r in range(n):
            for c in range(n):
                if m[r][c]:
                    dr.rectangle([x0 + c * mod, y + r * mod,
                                  x0 + c * mod + mod - 1, y + r * mod + mod - 1],
                                 fill=0)
        y += size
    elif sku and widths:
        total = sum(widths)
        bw = total * mod
        x = max(pad, (W - bw) // 2)
        dark = True
        for wd in widths:
            seg = wd * mod
            if dark:
                dr.rectangle([x, y, x + seg - 1, y + bar_h - 1], fill=0)
            x += seg
            dark = not dark
        y += bar_h

    if sku and show_sku:
        f = _font(sku_px, bold=True)
        tw = dr.textlength(sku, font=f)
        while tw > avail_w and sku_px > 10:
            sku_px -= 2
            f = _font(sku_px, bold=True)
            tw = dr.textlength(sku, font=f)
        dr.text(((W - tw) // 2, y + 2), sku, font=f, fill=0)

    # καθαρό ασπρόμαυρο
    return img.point(lambda v: 0 if v < 176 else 255, mode="L")


# ---------------------------------------------------------------------------
# Γλώσσες εκτυπωτών: TSPL (Xprinter) και ZPL (Zebra)
# ---------------------------------------------------------------------------
def _pack_bits(img, one_is_black):
    W, H = img.size
    px = img.load()
    row_bytes = (W + 7) // 8
    out = bytearray(row_bytes * H)
    for yy in range(H):
        base = yy * row_bytes
        for xx in range(W):
            black = px[xx, yy] < 128
            bit = black if one_is_black else (not black)
            if bit:
                out[base + (xx >> 3)] |= 0x80 >> (xx & 7)
    return bytes(out), row_bytes


def _mm(v):
    """25.0 -> «25», 24.5 -> «24.5» (κάποια firmware δεν δέχονται περιττά δεκαδικά)."""
    return str(int(round(v))) if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def tspl_bytes(img, w_mm, h_mm, gap_mm=2, copies=1, density=12):
    data, row_bytes = _pack_bits(img, one_is_black=False)  # TSPL: 1 = λευκό
    head = (f"SIZE {_mm(w_mm)} mm,{_mm(h_mm)} mm\r\n"
            f"GAP {_mm(gap_mm)} mm,0\r\n"
            f"DENSITY {density}\r\nSPEED 2\r\nDIRECTION 1\r\nCLS\r\n"
            f"BITMAP 0,0,{row_bytes},{img.size[1]},0,").encode("ascii")
    tail = (f"\r\nPRINT {max(1, copies)},1\r\n").encode("ascii")
    return head + data + tail


def zpl_bytes(img, copies=1):
    data, row_bytes = _pack_bits(img, one_is_black=True)   # ZPL: 1 = μαύρο
    total = row_bytes * img.size[1]
    hexdata = data.hex().upper()
    z = (f"^XA^PW{img.size[0]}^LL{img.size[1]}^LH0,0"
         f"^FO0,0^GFA,{total},{total},{row_bytes},{hexdata}^FS"
         f"^PQ{max(1, copies)}^XZ")
    return z.encode("ascii")


def detect_language(printer_name):
    n = (printer_name or "").lower()
    if port_of(printer_name) or host_of(printer_name):
        return "tspl"
    if any(k in n for k in ("xprinter", "xp-", "gprinter", "gp-", "pos-")):
        return "tspl"
    if any(k in n for k in ("zebra", "zdesigner", "zd2", "zpl")):
        return "zpl"
    return "tspl"


# ---------------------------------------------------------------------------
# Εκτυπωτές / RAW εκτύπωση
# ---------------------------------------------------------------------------
def list_com_ports():
    """Θύρες COM των Windows — έτσι εμφανίζεται ο εκτυπωτής όταν συνδεθεί
    μέσω Bluetooth (εξερχόμενη σειριακή θύρα)."""
    ports = []
    if sys.platform != "win32":
        return ports
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_SerialPort | "
             "ForEach-Object { $_.DeviceID + ' — ' + $_.Description }"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in out.stdout.splitlines():
            line = line.strip()
            if line.upper().startswith("COM"):
                ports.append(line)
    except Exception:
        pass
    return ports


def host_of(entry):
    """«192.168.1.50» ή «192.168.1.50:9100» -> (ip, port), αλλιώς None.
    Έτσι δηλώνεται δικτυακός εκτυπωτής (WiFi / Ethernet)."""
    e = (entry or "").strip()
    if not e or e[0].isalpha():
        return None
    host, _, p = e.partition(":")
    parts = host.split(".")
    if len(parts) != 4 or not all(x.isdigit() and 0 <= int(x) <= 255 for x in parts):
        return None
    try:
        port = int(p) if p else 9100
    except ValueError:
        port = 9100
    return host, port


def print_to_network(host, port, data: bytes):
    import socket
    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(data)


def port_of(entry):
    """«COM5 — Standard Serial over Bluetooth» -> «COM5» (αλλιώς None)."""
    e = (entry or "").strip()
    head = e.split(" ")[0].rstrip(":")
    if head.upper().startswith("COM") and head[3:].isdigit():
        return head.upper()
    return None


def print_to_com(port, data: bytes, baud=9600):
    """Απευθείας αποστολή στη σειριακή/Bluetooth θύρα."""
    if sys.platform == "win32":
        # ρύθμιση θύρας και εγγραφή δυαδικών δεδομένων
        try:
            subprocess.run(["mode", f"{port}:", f"BAUD={baud}", "PARITY=n",
                            "DATA=8", "STOP=1", "to=off", "xon=off",
                            "odsr=off", "octs=off", "dtr=on", "rts=on",
                            "idsr=off"],
                           shell=True, capture_output=True, timeout=15)
        except Exception:
            pass
        with open(rf"\\.\{port}", "wb", buffering=0) as f:
            f.write(data)
    else:
        with open(f"/dev/{port.lower()}", "wb", buffering=0) as f:
            f.write(data)


def list_printers():
    printers = []
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Printer | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            printers = [p.strip() for p in out.stdout.splitlines() if p.strip()]
        except Exception:
            pass
        printers += list_com_ports()      # Bluetooth / σειριακές θύρες
    else:
        try:
            out = subprocess.run(["lpstat", "-e"], capture_output=True,
                                 text=True, timeout=10)
            printers = [p.strip() for p in out.stdout.splitlines() if p.strip()]
        except Exception:
            pass
    return printers


def print_raw(printer_name, data: bytes):
    if sys.platform != "win32":
        p = subprocess.run(["lp", "-d", printer_name, "-o", "raw"],
                           input=data, capture_output=True, timeout=30)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.decode(errors="replace"))
        return
    winspool = ctypes.WinDLL("winspool.drv")

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR),
                    ("pOutputFile", wintypes.LPWSTR),
                    ("pDatatype", wintypes.LPWSTR)]

    winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR,
                                      ctypes.POINTER(wintypes.HANDLE),
                                      ctypes.c_void_p]
    winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                          ctypes.POINTER(DOC_INFO_1)]
    winspool.StartDocPrinterW.restype = wintypes.DWORD
    winspool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_char_p,
                                      wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD)]
    handle = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer_name, ctypes.byref(handle), None):
        raise RuntimeError(f"Δεν άνοιξε ο εκτυπωτής / Cannot open printer: {printer_name}")
    try:
        doc = DOC_INFO_1("GeekOn Label", None, "RAW")
        if winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)) == 0:
            raise RuntimeError("Αποτυχία εργασίας εκτύπωσης / Print job failed")
        try:
            winspool.StartPagePrinter(handle)
            written = wintypes.DWORD(0)
            ok = winspool.WritePrinter(handle, data, len(data), ctypes.byref(written))
            winspool.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                raise RuntimeError("Δεν στάλθηκαν όλα τα δεδομένα / Not all data sent")
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def print_label(printer, language, img, w_mm, h_mm, gap_mm, copies, baud=9600):
    lang = language if language in ("tspl", "zpl") else detect_language(printer)
    data = (tspl_bytes(img, w_mm, h_mm, gap_mm, copies) if lang == "tspl"
            else zpl_bytes(img, copies))
    net = host_of(printer)
    com = port_of(printer)
    if net:
        print_to_network(net[0], net[1], data)   # WiFi / Ethernet
    elif com:
        print_to_com(com, data, baud)            # Bluetooth / σειριακή θύρα
    else:
        print_raw(printer, data)                 # εκτυπωτής των Windows (USB)



# ---------------------------------------------------------------------------
# Μεταφράσεις / Translations / 翻译
# ---------------------------------------------------------------------------
TR = {
    "el": {
        "printer": " Εκτυπωτής ", "hint": "Σύνδεση: USB (λίστα), Bluetooth (COM…) ή WiFi — γράψε τη διεύθυνση IP, π.χ. 192.168.1.50", "lang_lbl": "Γλώσσα εκτυπωτή:",
        "ui_lang": "Γλώσσα:",
        "presets": "Έτοιμα μεγέθη:", "label": " Ετικέτα ", "w": "Πλάτος (mm):", "h": "Ύψος (mm):",
        "gap": "Κενό μεταξύ ετικετών (mm):",
        "bar": "Barcode (Code 128)", "qr": "QR κώδικας",
        "show_sku": "Κωδικός SKU κάτω από το barcode",
        "print_fr": " Εκτύπωση ", "sku": "Κωδικός SKU:", "text": "Κείμενο:",
        "qty": "Τεμάχια:", "print_btn": "🖨  ΕΚΤΥΠΩΣΗ",
        "batch_lbl": "Λίστα (μία γραμμή ανά ετικέτα — SKU;Κείμενο;Τεμάχια):",
        "batch_btn": "🖨  Εκτύπωση λίστας",
        "preview": " Προεπισκόπηση ",
        "ready": "Έτοιμο.", "printed": "Τυπώθηκε ✓",
        "printed_n": "Τυπώθηκαν {n} ετικέτες ✓",
        "need_sku": "Γράψε πρώτα έναν κωδικό SKU",
        "empty_list": "Η λίστα είναι άδεια",
        "err": "Σφάλμα", "err_print": "Σφάλμα εκτύπωσης",
        "no_printer": "Δεν άνοιξε ο εκτυπωτής: {p}",
    },
    "en": {
        "printer": " Printer ", "hint": "Connection: USB (list), Bluetooth (COM…) or WiFi — type the IP address, e.g. 192.168.1.50", "lang_lbl": "Printer language:",
        "ui_lang": "Language:",
        "presets": "Quick sizes:", "label": " Label ", "w": "Width (mm):", "h": "Height (mm):",
        "gap": "Gap between labels (mm):",
        "bar": "Barcode (Code 128)", "qr": "QR code",
        "show_sku": "SKU text below barcode",
        "print_fr": " Print ", "sku": "SKU code:", "text": "Text:",
        "qty": "Quantity:", "print_btn": "🖨  PRINT",
        "batch_lbl": "Batch list (one line per label — SKU;Text;Qty):",
        "batch_btn": "🖨  Print list",
        "preview": " Preview ",
        "ready": "Ready.", "printed": "Printed ✓",
        "printed_n": "Printed {n} labels ✓",
        "need_sku": "Enter a SKU code first",
        "empty_list": "The list is empty",
        "err": "Error", "err_print": "Print error",
        "no_printer": "Cannot open printer: {p}",
    },
    "zh": {
        "printer": " 打印机 ", "hint": "连接方式: USB (列表)、蓝牙 (COM…) 或 WiFi — 输入 IP 地址, 例如 192.168.1.50", "lang_lbl": "打印机语言:",
        "ui_lang": "语言:",
        "presets": "常用尺寸:", "label": " 标签 ", "w": "宽度 (mm):", "h": "高度 (mm):",
        "gap": "标签间距 (mm):",
        "bar": "条形码 (Code 128)", "qr": "二维码",
        "show_sku": "条码下方显示 SKU",
        "print_fr": " 打印 ", "sku": "SKU 编码:", "text": "文字:",
        "qty": "数量:", "print_btn": "🖨  打印",
        "batch_lbl": "批量列表 (每行一个标签 — SKU;文字;数量):",
        "batch_btn": "🖨  打印列表",
        "preview": " 预览 ",
        "ready": "就绪。", "printed": "已打印 ✓",
        "printed_n": "已打印 {n} 张标签 ✓",
        "need_sku": "请先输入 SKU 编码",
        "empty_list": "列表为空",
        "err": "错误", "err_print": "打印错误",
        "no_printer": "无法打开打印机: {p}",
    },
}
UI_LANGS = [("Ελληνικά", "el"), ("English", "en"), ("中文", "zh")]


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    cfg = load_config()
    ui = cfg.get("ui_lang", "zh")           # προεπιλογή: κινέζικα
    if ui not in TR:
        ui = "zh"
    S = {"lang": ui}
    def T(key, **kw):
        s = TR[S["lang"]].get(key) or TR["en"].get(key, key)
        return s.format(**kw) if kw else s

    root = tk.Tk()
    root.title(f"GeekOn Supplier Labels  v{VERSION}")
    root.minsize(780, 580)
    # γραμματοσειρά που δείχνει σωστά ελληνικά ΚΑΙ κινέζικα
    for fam in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "DejaVu Sans"):
        try:
            import tkinter.font as tkfont
            if fam in tkfont.families():
                root.option_add("*Font", (fam, 10))
                break
        except Exception:
            pass

    main = ttk.Frame(root, padding=12)
    main.pack(fill="both", expand=True)
    tr = []                                  # (widget, κλειδί μετάφρασης)
    def reg(w, key):
        tr.append((w, key))
        return w

    # --- Εκτυπωτής ------------------------------------------------------
    fr_pr = reg(ttk.LabelFrame(main, padding=8), "printer")
    fr_pr.pack(fill="x", pady=(0, 8))
    printer_var = tk.StringVar(value=cfg.get("printer", ""))
    lang_var = tk.StringVar(value=cfg.get("language", "auto"))
    uilang_var = tk.StringVar(value=dict((v, k) for k, v in UI_LANGS)[S["lang"]])
    cmb = ttk.Combobox(fr_pr, textvariable=printer_var, width=34)
    cmb.grid(row=0, column=0, padx=(0, 6), sticky="we")

    def refresh():
        names = list_printers()
        cmb["values"] = names
        if names and not printer_var.get():
            xp = [n for n in names if detect_language(n) == "tspl"] or names
            printer_var.set(xp[0])
    ttk.Button(fr_pr, text="↻", width=3, command=refresh).grid(row=0, column=1)
    reg(ttk.Label(fr_pr), "lang_lbl").grid(row=0, column=2, padx=(14, 4))
    ttk.Combobox(fr_pr, textvariable=lang_var, state="readonly", width=8,
                 values=["auto", "tspl", "zpl"]).grid(row=0, column=3)
    reg(ttk.Label(fr_pr), "ui_lang").grid(row=0, column=4, padx=(14, 4))
    cmb_ui = ttk.Combobox(fr_pr, textvariable=uilang_var, state="readonly", width=10,
                          values=[n for n, _ in UI_LANGS])
    cmb_ui.grid(row=0, column=5)
    reg(ttk.Label(fr_pr, foreground="#666"), "hint").grid(
        row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))
    fr_pr.columnconfigure(0, weight=1)

    # --- Ετικέτα --------------------------------------------------------
    fr_lb = reg(ttk.LabelFrame(main, padding=8), "label")
    fr_lb.pack(fill="x", pady=(0, 8))
    w_var = tk.StringVar(value=str(cfg.get("w", 25)))
    h_var = tk.StringVar(value=str(cfg.get("h", 15)))
    gap_var = tk.StringVar(value=str(cfg.get("gap", 2)))
    type_var = tk.StringVar(value=cfg.get("bc_type", "bar"))
    show_var = tk.BooleanVar(value=cfg.get("show_sku", True))
    # γρήγορα μεγέθη — τα πεδία mm παραμένουν για ό,τι άλλο χρειαστεί
    reg(ttk.Label(fr_lb), "presets").grid(row=0, column=0, sticky="w")
    fr_ps = ttk.Frame(fr_lb)
    fr_ps.grid(row=0, column=1, columnspan=5, sticky="w", padx=(4, 0))
    for j, (pw, ph) in enumerate([(25, 15), (28, 20), (30, 20), (40, 30), (50, 30)]):
        ttk.Button(fr_ps, text=f"{pw}×{ph}", width=6,
                   command=(lambda a=pw, b=ph: (w_var.set(str(a)), h_var.set(str(b))))
                   ).grid(row=0, column=j, padx=(0, 4))
    for i, (key, var) in enumerate([("w", w_var), ("h", h_var), ("gap", gap_var)]):
        reg(ttk.Label(fr_lb), key).grid(row=1, column=2 * i, sticky="w", pady=(8, 0))
        ttk.Entry(fr_lb, textvariable=var, width=7).grid(row=1, column=2 * i + 1,
                                                         padx=(4, 16), pady=(8, 0))
    reg(ttk.Radiobutton(fr_lb, value="bar", variable=type_var), "bar").grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
    reg(ttk.Radiobutton(fr_lb, value="qr", variable=type_var,
                        state=("normal" if HAS_QR else "disabled")), "qr").grid(
        row=2, column=2, columnspan=2, sticky="w", pady=(8, 0))
    reg(ttk.Checkbutton(fr_lb, variable=show_var), "show_sku").grid(
        row=2, column=4, columnspan=2, sticky="w", pady=(8, 0))

    # --- Εκτύπωση + Προεπισκόπηση ---------------------------------------
    mid = ttk.Frame(main)
    mid.pack(fill="both", expand=True)
    fr_one = reg(ttk.LabelFrame(mid, padding=8), "print_fr")
    fr_one.pack(side="left", fill="both", expand=True, padx=(0, 8))
    sku_var = tk.StringVar(value=cfg.get("last_sku", ""))
    txt_var = tk.StringVar(value=cfg.get("last_text", ""))
    copies_var = tk.StringVar(value="1")
    reg(ttk.Label(fr_one), "sku").grid(row=0, column=0, sticky="w")
    ttk.Entry(fr_one, textvariable=sku_var, width=24,
              font=("Consolas", 12, "bold")).grid(row=0, column=1, sticky="we", padx=4)
    reg(ttk.Label(fr_one), "text").grid(row=1, column=0, sticky="w", pady=(6, 0))
    ttk.Entry(fr_one, textvariable=txt_var, width=24).grid(
        row=1, column=1, sticky="we", padx=4, pady=(6, 0))
    reg(ttk.Label(fr_one), "qty").grid(row=2, column=0, sticky="w", pady=(6, 0))
    ttk.Spinbox(fr_one, from_=1, to=999, textvariable=copies_var,
                width=6).grid(row=2, column=1, sticky="w", padx=4, pady=(6, 0))
    btn_print = reg(ttk.Button(fr_one), "print_btn")
    btn_print.grid(row=3, column=0, columnspan=2, sticky="we", pady=(12, 4), ipady=6)
    fr_one.columnconfigure(1, weight=1)

    reg(ttk.Label(fr_one), "batch_lbl").grid(row=4, column=0, columnspan=2,
                                             sticky="w", pady=(12, 2))
    batch = tk.Text(fr_one, height=6, width=32, font=("Consolas", 10))
    batch.grid(row=5, column=0, columnspan=2, sticky="nsew")
    fr_one.rowconfigure(5, weight=1)
    btn_batch = reg(ttk.Button(fr_one), "batch_btn")
    btn_batch.grid(row=6, column=0, columnspan=2, sticky="we", pady=(6, 0))

    fr_pv = reg(ttk.LabelFrame(mid, padding=8), "preview")
    fr_pv.pack(side="left", fill="both", expand=True)
    pv_label = ttk.Label(fr_pv, relief="solid", padding=2)
    pv_label.pack(padx=8, pady=8)
    status_var = tk.StringVar(value=T("ready"))
    ttk.Label(main, textvariable=status_var, foreground="#555").pack(fill="x", pady=(8, 0))

    def apply_lang():
        for w, key in tr:
            try:
                w.configure(text=T(key))
            except Exception:
                pass
        status_var.set(T("ready"))
    def on_uilang(*_a):
        code = dict(UI_LANGS).get(uilang_var.get(), "zh")
        S["lang"] = code
        cfg["ui_lang"] = code
        save_config(cfg)
        apply_lang()
    uilang_var.trace_add("write", on_uilang)

    def parse_mm(var, dflt, lo, hi):
        try:
            v = float(str(var.get()).replace(",", "."))
        except ValueError:
            return dflt
        return min(max(v, lo), hi)

    def current_img():
        w = parse_mm(w_var, 25, 15, 60)
        h = parse_mm(h_var, 15, 8, 60)
        return w, h, render_label(w, h, sku_var.get(), txt_var.get(),
                                  type_var.get(), show_var.get())

    _pending = [None]

    def draw_preview():
        _pending[0] = None
        try:
            _, _, img = current_img()
        except Exception as e:
            status_var.set(f"{T('err')}: {e}")
            return
        z = max(1, min(4, round(320 / img.size[0])))
        big = img.resize((img.size[0] * z, img.size[1] * z), Image.NEAREST)
        ph = ImageTk.PhotoImage(big)
        pv_label.configure(image=ph)
        pv_label.image = ph

    def schedule(*_a):
        if _pending[0]:
            root.after_cancel(_pending[0])
        _pending[0] = root.after(200, draw_preview)

    for v in (sku_var, txt_var, w_var, h_var, type_var, show_var):
        v.trace_add("write", schedule)

    def persist():
        cfg.update({"printer": printer_var.get(), "language": lang_var.get(),
                    "ui_lang": S["lang"],
                    "w": parse_mm(w_var, 25, 15, 60), "h": parse_mm(h_var, 15, 8, 60),
                    "gap": parse_mm(gap_var, 2, 0, 10),
                    "bc_type": type_var.get(), "show_sku": show_var.get(),
                    "last_sku": sku_var.get(), "last_text": txt_var.get()})
        save_config(cfg)

    def do_print_one():
        if not sku_var.get().strip() and not txt_var.get().strip():
            return status_var.set(T("need_sku"))
        try:
            w, h, img = current_img()
            print_label(printer_var.get(), lang_var.get(), img, w, h,
                        parse_mm(gap_var, 2, 0, 10),
                        int(float(copies_var.get() or 1)))
            persist()
            status_var.set(T("printed"))
        except Exception as e:
            messagebox.showerror(T("err"), str(e))
            status_var.set(T("err_print"))

    def do_print_batch():
        lines = [l.strip() for l in batch.get("1.0", "end").splitlines() if l.strip()]
        if not lines:
            return status_var.set(T("empty_list"))
        try:
            w = parse_mm(w_var, 25, 15, 60)
            h = parse_mm(h_var, 15, 8, 60)
            gap = parse_mm(gap_var, 2, 0, 10)
            n = 0
            for ln in lines:
                parts = [p.strip() for p in ln.split(";")]
                sku = parts[0]
                text = parts[1] if len(parts) > 1 else ""
                qty = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                img = render_label(w, h, sku, text, type_var.get(), show_var.get())
                print_label(printer_var.get(), lang_var.get(), img, w, h, gap, qty)
                n += qty
            persist()
            status_var.set(T("printed_n", n=n))
        except Exception as e:
            messagebox.showerror(T("err"), str(e))
            status_var.set(T("err_print"))

    btn_print.configure(command=do_print_one)
    btn_batch.configure(command=do_print_batch)
    root.protocol("WM_DELETE_WINDOW", lambda: (persist(), root.destroy()))
    apply_lang()
    refresh()
    draw_preview()
    root.mainloop()


if __name__ == "__main__":
    run_gui()
