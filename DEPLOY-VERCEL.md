# Deploy ke Vercel (lewat GitHub) — Panduan Lengkap

Panduan ini menjelaskan cara meng-host **frontend dashboard** di **Vercel**
(dari repo **GitHub**), sementara **backend Python + FL Studio MCP** tetap
berjalan di komputer lokal Anda. Termasuk solusi untuk masalah **Mixed Content**
(blokir HTTPS→HTTP oleh browser).

---

## Arsitektur akhir

```
 +-----------------------+        HTTPS        +--------------------------+
 |  Vercel (GitHub)      |  -----------------> |  Cloudflare Tunnel       |
 |  frontend dashboard   |   fetch /api/prompt |  https://xxx.trycloudflare.com
 |  https://ombar-       |                     +------------+-------------+
 |   fl-ai.vercel.app    |                                  |
 +-----------------------+                                  |  (localhost)
                                                            v
                                          +---------------------------------+
                                          |  FastAPI backend  :8080         |
                                          |  + MCP bridge -> :9787 -> FL    |
                                          +---------------------------------+
```

> **Kenapa perlu tunnel?** Vercel wajib HTTPS. Browser **memblokir** request
> `http://localhost:8080` dari halaman HTTPS (mixed content). Tunnel
> Cloudflare memberi backend Anda URL HTTPS publik gratis tanpa signup.

---

## Langkah 1 — Siapkan repo GitHub

### Opsi A: Buat repo baru berisi frontend saja (paling bersih)

1. Buka https://github.com/new
2. Repository name: `ombar-fl-ai-frontend`
3. **Public** (gratis untuk Vercel)
4. Jangan centang "Add README" (kita akan push isi folder)
5. Klik **Create repository**

6. Di komputer Anda, copy **isi folder `frontend/`** ke folder repo baru:
   ```bat
   mkdir ombar-fl-ai-frontend
   xcopy /E /I "F:\BERTY\...\ombar-flai-studio\frontend\*" ombar-fl-ai-frontend
   cd ombar-fl-ai-frontend
   git init
   git add .
   git commit -m "OMBAR FL-AI Studio dashboard"
   git branch -M main
   git remote add origin https://github.com/USERNAME/ombar-fl-ai-frontend.git
   git push -u origin main
   ```

### Opsi B: Repo berisi seluruh proyek, deploy hanya folder frontend

Push seluruh folder `ombar-flai-studio` ke GitHub, lalu di Vercel set
**Root Directory = `frontend`** (lihat Langkah 3).

---

## Langkah 2 — Hubungkan ke Vercel

1. Buka https://vercel.com dan login dengan akun **GitHub** (gratis)
2. Klik **Add New… → Project**
3. Pilih repo `ombar-fl-ai-frontend` dari daftar
4. **Framework Preset**: Other (Vercel auto-detect static site)
   - Build Command: *(kosong)*
   - Output Directory: `.` (titik) — atau biarkan kosong
   - Install Command: *(kosong)*
5. Jika Anda pakai Opsi B (repo utuh), buka **Settings → General → Root Directory** dan isi `frontend`
6. Klik **Deploy**

Tunggu ~20 detik. Vercel memberi URL seperti:
`https://ombar-fl-ai-frontend.vercel.app`

Buka URL itu → dashboard akan tampil, tapi status backend masih **merah**
karena belum terhubung ke backend lokal Anda. Lanjut Langkah 3.

---

## Langkah 3 — Jalankan backend lokal + tunnel

Di komputer Anda (FL Studio terbuka):

1. **Start MCP daemon + FastAPI backend** (seperti biasa):
   - Double-click `launchers\OMBAR_FL-AI_Studio_Launcher.bat`
   - Pastikan jendela `OMBAR - FastAPI Backend :8080` aktif

2. **Start Cloudflare Tunnel** (beri backend Anda URL HTTPS publik):
   - Double-click `launchers\start_tunnel.bat`
   - Script otomatis download `cloudflared.exe` (sekali saja, ~50MB)
   - Tunggu sampai muncul baris seperti:
     ```
     https://random-words-1234.trycloudflare.com
     ```
   - **Copy URL HTTPS itu** (tanpa port tambahan)

   > URL tunnel berubah setiap kali restart. Untuk URL tetap, daftar
   > akun Cloudflare + pakai *named tunnel* (gratis).

3. **Hubungkan dashboard Vercel ke backend**:
   - Buka URL Vercel Anda (`https://ombar-fl-ai-frontend.vercel.app`)
   - Di kanan, kolom **Backend URL**, ganti `http://localhost:8080`
     dengan URL tunnel, contoh:
     ```
     https://random-words-1234.trycloudflare.com
     ```
   - Tekan Enter / klik di luar kolom
   - Status pill **Backend**, **MCP**, **FL Studio** akan jadi **hijau**
   - Ketik prompt → "Kirim ke FL Studio" → FL Studio Anda merespons!

---

## Troubleshooting Vercel

| Gejala | Penyebab & Solusi |
|--------|-------------------|
| Banner kuning "Mixed Content terdeteksi" | Backend URL masih `http://localhost`. Ganti dengan URL tunnel HTTPS dari Langkah 3. |
| Status backend merah setelah pakai tunnel | Tunnel belum jalan, atau URL salah. Pastikan jendela `start_tunnel.bat` masih aktif dan copy URL persis (termasuk `https://`). |
| `ERR_CONNECTION_REFUSED` di console | Backend lokal tidak jalan. Start dulu `OMBAR_FL-AI_Studio_Launcher.bat`. |
| `CORS error` di console | Sudah ditangani `server.py` (allow all). Jika masih muncul, pastikan backend versi v1.3.0+. |
| WebSocket reconnect endlessly | Tunnel Cloudflare mendukung WebSocket. Pastikan URL tunnel dipakai konsisten (HTTP dan WS pakai host yang sama — `app.js` otomatis konversi). |
| Deploy Vercel gagal "No output" | Set Output Directory = `.` (titik) di Vercel settings. |
| Perubahan frontend tidak muncul | Push ke GitHub → Vercel auto-deploy ~20 detik. Hard-refresh browser (Ctrl+Shift+R). |
| Tunnel URL berubah tiap restart | Wajar (free tier). Pakai *named tunnel* Cloudflare untuk URL tetap, atau pakai ngrok dengan domain tetap (berbayar). |

---

## Tanpa tunnel: alternatif "Allow insecure content"

Jika tidak ingin pakai tunnel, Anda bisa izinkan browser memanggil HTTP
localhost dari halaman HTTPS Vercel:

### Chrome / Edge
1. Buka dashboard Vercel Anda
2. Klik ikon **gembok** di kiri address bar
3. **Site settings**
4. Scroll ke **Insecure content**
5. Ubah dari "Block" → **Allow**
6. Kembali ke dashboard, refresh

### Firefox
1. Buka `about:config`
2. Cari `dom.security.https_only_mode`
3. Set `false` (matikan HTTPS-Only) — atau tambahkan exception per-site

> Catatan: opsi ini hanya berlaku untuk browser Anda sendiri. Tunnel
> (Langkah 3) adalah solusi yang bekerja untuk siapa pun yang membuka
> dashboard Anda.

---

## Checklist akhir

- [ ] Frontend di-push ke GitHub (folder `frontend/` atau repo terpisah)
- [ ] Vercel deploy sukses, URL `https://xxx.vercel.app` bisa dibuka
- [ ] Backend lokal jalan (`launchers\OMBAR_FL-AI_Studio_Launcher.bat`)
- [ ] Tunnel jalan (`launchers\start_tunnel.bat`) — URL HTTPS terlihat
- [ ] Kolom Backend URL di dashboard diisi URL tunnel
- [ ] Ketiga status pill hijau
- [ ] Prompt terkirim → FL Studio merespons

Selamat! Dashboard OMBAR FL-AI Studio Anda sekarang live di Vercel dan
mengontrol FL Studio lokal lewat MCP.
