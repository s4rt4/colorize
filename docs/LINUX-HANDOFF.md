# Linux: serah-terima untuk agent di mesin Linux

Dukungan Linux untuk Colorize **sudah dikerjakan di Windows** (branch `linux-support`).
CI GitHub Actions sudah menjalankan seluruh tes di Ubuntu, membuat build Linux, dan
menjalankan smoke test di lingkungan bersih (Qt *offscreen*). Yang tersisa hanya hal yang
**butuh desktop Linux sungguhan**: layar, Wayland, menu aplikasi.

Tugas Anda sengaja dibuat kecil: **jalankan pemeriksaan di bawah, laporkan hasilnya, dan
hanya perbaiki yang gagal.** Jangan refactor, jangan ubah perilaku Windows, jangan tambah
fitur atau format paket baru (Flatpak/AppImage/.deb) kecuali diminta.

## Yang sudah selesai (jangan dikerjakan ulang)

| Bagian | File | Status |
|---|---|---|
| Profil ICC dari folder XDG (rekursif) | `colorize/core/cmyk.py` (`system_profile_dirs`) | dites di CI (ghostscript) |
| Ambil warna layar via xdg-desktop-portal di Wayland | `colorize/ui/screen_sampler.py` (`PortalScreenshot`, `split_desktop`) | logika dites dengan portal tiruan; **D-Bus sungguhan belum pernah dijalankan** |
| Font cadangan per platform | `colorize/app.py` (`FALLBACK_UI_FONT`) | selesai |
| Build Linux: tar.gz + `.desktop` + ikon + `install.sh` | `tools/build.py`, `packaging/colorize.spec`, `packaging/linux/` | build + smoke test lulus di CI |
| CI Ubuntu + Windows | `.github/workflows/ci.yml` | lihat tab Actions |

## Persiapan (sekitar 5 menit)

```sh
git clone https://github.com/s4rt4/colorize.git && cd colorize
git checkout linux-support
sudo apt install python3-venv libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3 ghostscript
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pyinstaller
.venv/bin/python -m pytest -q          # harus lulus semua, sama seperti di CI
```

(Fedora: `sudo dnf install mesa-libEGL libxkbcommon-x11 xcb-util-cursor dbus-libs ghostscript`.)

## Pemeriksaan manual

Jalankan aplikasi dari sumber: `.venv/bin/python -m colorize`. Cek `echo $XDG_SESSION_TYPE`
untuk tahu sesi Anda Wayland atau X11. Idealnya diuji di **keduanya** (di layar login GNOME
bisa dipilih "Ubuntu on Xorg").

### 1. Ambil warna dari layar (Shift+I): prioritas utama

- **Wayland:**
  - Tekan Shift+I. Desktop mungkin meminta izin tangkapan layar sekali. Lalu layar membeku
    dan kaca pembesar muncul.
  - Klik sebuah warna yang diketahui (misalnya buka gambar berwarna solid #FF0000 di aplikasi
    lain). Warna depan harus menjadi warna itu (toleransi ±1 per kanal).
  - Pastikan tidak ada file tangkapan layar yang tertinggal di `~/Pictures` atau
    `~/Pictures/Screenshots`.
  - Esc membatalkan.
- **X11:** sama, tanpa dialog izin (jalur `grabWindow` biasa).
- **Bila gagal di Wayland**, kemungkinan penyebabnya dan arah perbaikan:
  - *Tidak terjadi apa-apa*: sinyal `Response` dari portal tidak sampai ke slot. Pantau dengan
    `dbus-monitor --session "interface='org.freedesktop.portal.Request'"`. Periksa koneksi
    di `PortalScreenshot.request` (signature slot `pyqtSlot(QDBusMessage)`).
  - *Overlay tidak menutupi layar atau muncul di posisi salah*: overlay memakai
    `showFullScreen()` di Wayland (lihat `ScreenSampler._show`). Bila multi-monitor
    bermasalah, cukup catat; single monitor yang wajib jalan.
  - *Warna meleset*: cek `split_desktop` (skala gambar portal dibanding geometri layar).

### 2. Tampilan dan panel docking

- Ganti tema (Shift+F1/F2), ganti workspace (Window › Workspace), tekan Tab.
- **Lepas panel jadi jendela terapung** (tarik tab panel keluar), lalu tarik kembali.
- Bila docking rusak di Wayland, coba `QT_QPA_PLATFORM=xcb .venv/bin/python -m colorize`.
  Kalau itu memperbaikinya, tambahkan **di `colorize/app.py` sebelum `QApplication` dibuat**:
  pada Linux dengan sesi Wayland dan tanpa `QT_QPA_PLATFORM` dari pengguna, set
  `os.environ["QT_QPA_PLATFORM"] = "xcb"`. **Tetapi** jalur xcb di Wayland membuat Shift+I
  tetap harus lewat portal; logika `needs_portal()` sudah menangani ini (memeriksa
  `XDG_SESSION_TYPE`/`WAYLAND_DISPLAY`, bukan platform Qt).

### 3. Panel Print

- Buka panel Print (Window › Print). Daftar Profile harus berisi profil CMYK dari ghostscript
  (misalnya "Artifex CMYK SWOP Profile" atau "default_cmyk"). "Approximate (no profile)" tetap ada.

### 4. Build dan pemasangan

```sh
.venv/bin/python tools/build.py        # build + smoke test + dist/Colorize-<versi>-linux-x86_64.tar.gz
cd /tmp && tar xzf ~/colorize/dist/Colorize-*-linux-*.tar.gz && ./Colorize/install.sh
```

- Build sengaja **tidak** membawa pustaka sistem (driver grafis, X11/xcb, Wayland,
  fontconfig, D-Bus, glib) dan tidak membawa GTK. Lihat `HOST_LIBS` di
  `packaging/colorize.spec`. Smoke test di CI berjalan *offscreen*, jadi pemuatan plugin
  xcb/wayland baru teruji di sini. Bila aplikasi hasil build gagal start karena sebuah
  `lib….so` tidak ditemukan:
  - Pustaka sistem (misalnya `libxcb-icccm.so.4`): pasang paketnya lewat apt, lalu tambahkan
    namanya ke daftar `apt install` di README (bagian *Linux*).
  - Bukan pustaka sistem: hapus prefiksnya dari `HOST_LIBS`.
- Colorize muncul di menu aplikasi dengan ikon. Buka dari menu.
- Klik kanan sebuah PNG di file manager: "Open With" harus menawarkan Colorize, dan file terbuka.
- `./Colorize/install.sh --uninstall` menghapus entri menu.
- Smoke test dengan layar sungguhan juga harus lulus (`tools/build.py` meneruskan
  `DISPLAY`/`WAYLAND_DISPLAY`).

### 5. Lokasi data

Setelah membuka aplikasi sekali, pastikan:
- pengaturan ada di `~/.config/Colorize/Colorize.ini`,
- library dan log ada di `~/.local/share/Colorize/Colorize/`.

Bila lokasinya berbeda, **perbaiki README** (bagian *Linux*), jangan kodenya.

## Cara melapor

Tambahkan bagian **Hasil** di akhir file ini: satu baris per pemeriksaan (1-5), isinya
lulus atau gagal beserta distro, desktop, dan sesi (misalnya *Ubuntu 26.04, GNOME, Wayland*).
Untuk yang gagal, sertakan pesan error, potongan `~/.local/share/Colorize/Colorize/colorize.log`,
dan perbaikan yang dibuat.

Perbaikan di-commit ke branch `linux-support`. Pastikan
`.venv/bin/python -m pytest -q` tetap lulus sebelum push, lalu push dan pastikan CI hijau.
Penggabungan ke `main` dan rilis dilakukan oleh pemilik repo.
