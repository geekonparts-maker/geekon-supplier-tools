# GeekOn Label Tools

Label printing tools for suppliers — print product labels with correct,
scannable barcodes on thermal label printers.

供应商标签打印工具 — 在热敏标签打印机上打印带有正确条码的产品标签。

Εργαλεία εκτύπωσης ετικετών για προμηθευτές.

---

## ⬇️ Download / 下载

### **[→ Get the app here / 点击这里下载](../../releases/tag/latest)**

| | |
|---|---|
| 📱 **Android tablet / phone** | `GeekOnLabels.apk` — prints **directly** over Bluetooth or WiFi |
| 💻 **Windows PC** | `GeekOnSupplierLabels-windows.zip` — prints directly over USB, Bluetooth or WiFi |
| 🌐 **Any device** | `supplier-labels.html` — opens in a browser, saves the label as an image |

---

## 📱 Android — quick start / 快速开始

1. Download and install `GeekOnLabels.apk`
   (allow *install from unknown sources* if asked)
2. Pair your printer in **Settings → Bluetooth** first
   (WiFi printers: no pairing — just type the printer's IP in the app)
3. Open the app → pick the printer at the top → type the SKU → tap **Print**

1. 下载并安装 `GeekOnLabels.apk`（如提示，请允许「安装未知来源应用」）
2. 先在 **设置 → 蓝牙** 中配对打印机（WiFi 打印机：在应用里直接输入 IP 地址）
3. 打开应用 → 顶部选择打印机 → 输入 SKU → 点击「打印」

---

## Features / 功能

- **Label sizes**: 25×15mm by default, plus 28×20, 30×20, 40×30, 50×30 with one
  tap — or type any size in mm
  标签尺寸：默认 25×15mm，也可选择或输入其他尺寸
- **Code 128 barcode or QR code**, with the SKU printed underneath, using
  correct quiet zones so it always scans
  条形码 Code 128 或二维码，下方显示 SKU
- **Batch printing**: one line per label — `SKU;text;quantity`
  批量打印：每行一个标签
- **Live preview** before printing / 实时预览
- **中文 / English / Ελληνικά**
- Works **fully offline** — no internet, no account, no server
  完全离线工作，无需联网

## Supported printers / 支持的打印机

- **TSPL** printers: Xprinter (XP-236B etc.), Gprinter and compatible
- **ZPL** printers: Zebra (ZD220, ZD230 etc.)
- Connection: USB · Bluetooth · WiFi/Ethernet (port 9100)

## For developers

- `supplier-labels.py` — Windows/desktop app (Python + tkinter;
  `pip install pillow qrcode`)
- `supplier-labels.html` — single-file web UI; doubles as the Android app's UI
- `android/` — Android wrapper (WebView + Bluetooth SPP / TCP printing)

Both the APK and the Windows build are produced automatically by GitHub Actions
and published to the [latest release](../../releases/tag/latest).
