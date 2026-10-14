# 🚀 Deploy to Oracle Cloud (Always Free) — Full Guide

Run the AI Shorts Generator **online, 24/7, for free**, without keeping your own
PC switched on. Oracle's **Always Free** tier gives you a small but capable
ARM virtual machine that is perfect for this app (FFmpeg, Python, SQLite).

> **Why not Vercel?** Vercel runs short-lived, stateless functions with no
> permanent disk and no FFmpeg. This app needs a **staying-on server** to run
> video encoding and keep uploads/outputs. A free VM is the right tool.

---

## What you get (free)

| Resource | Always Free amount |
|---|---|
| CPU | up to **2 ARM (Ampere A1) cores** |
| RAM | up to **12 GB** |
| Disk | **200 GB** block storage |
| Bandwidth | 10 TB/month out |
| Cost | **$0** — no credit card charges |

> ⚠️ Oracle quietly **reduced** the A1 free allowance over time (older docs say
> 4 cores / 24 GB). If your account only lets you pick 1 core / 6 GB, that still
> works for this app — just pick the largest option it allows.

---

## Step 1 — Create an Oracle Cloud account

1. Go to **https://www.oracle.com/cloud/free/** and sign up.
2. Choose a **Home Region** close to you. (Some popular regions are often
   "out of capacity" for ARM — see the tip in Step 3.)
3. A card is used for **identity verification only**; Always Free resources
   are not charged.

---

## Step 2 — Create the VM

1. In the console go to **Compute → Instances → Create instance**.
2. **Image:** *Ubuntu* (22.04 LTS or 24.04 LTS).
3. **Shape:** click *Change shape* → **Ampere** → `VM.Standard.A1.Flex`.
   Set **2 OCPUs / 12 GB** (or the max your account allows).
4. **Networking:** keep the default VCN + public subnet, ensure
   **Assign a public IPv4 address = Yes**.
5. **SSH keys:** choose *Generate a key pair* and **download the private key**
   (you need this to connect), OR paste your own public key.
6. Click **Create**. Copy the **Public IP address** of the instance.

> **"Out of host capacity" error?** This is the single most common ARM problem.
> Fixes: try a different **Availability Domain**, retry every few minutes, or
> use a different Home Region. It is not you — the free ARM capacity is popular.

---

## Step 3 — Open port 8000 (⚠️ the #1 gotcha)

The app runs on port **8000**. You must allow it in **two** places:

1. **The VM firewall** — handled automatically by `setup_server.sh` (ufw).
2. **The Oracle VCN Security List** — you must add this **manually**:

   - Console → **Networking → Virtual Cloud Networks** → your VCN →
     **Security Lists** → the default one.
   - **Add Ingress Rule**:
     - Source Type: `CIDR`
     - Source CIDR: `0.0.0.0/0`
     - IP Protocol: `TCP`
     - Destination Port Range: `8000`
   - Save.

If you skip this, the site will not load even though the app is running.

---

## Step 4 — Upload the project to the VM

You can do this from **Windows** (PowerShell) using the helper script, or
manually.

### Option A — helper script (recommended)

From the project root on your PC:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\upload.ps1 `
    -Server <YOUR_VM_PUBLIC_IP> `
    -Key C:\path\to\your\ssh-private-key.key `
    -RunSetup
```

This packages the app (skipping your local `venv`, `uploads`, `output` and the
Windows FFmpeg binaries), uploads it to `~/shorts-generator`, and runs the
server setup.

### Option B — manual (Git Bash / WSL on Windows)

```bash
# 1. Package without the heavy/irrelevant folders
tar --exclude='shorts-generator/backend/venv' \
    --exclude='shorts-generator/backend/uploads' \
    --exclude='shorts-generator/backend/output' \
    --exclude='shorts-generator/backend/ffmpeg_bin' \
    --exclude='.idea' \
    -czf /tmp/shorts.tar.gz shorts-generator

# 2. Upload
scp -i /path/to/key.key /tmp/shorts.tar.gz ubuntu@<VM_IP>:~/

# 3. Extract on the server
ssh -i /path/to/key.key ubuntu@<VM_IP> "tar -xzf ~/shorts.tar.gz -C ~"
```

> On Windows, `chmod 400 your-key.key` first if SSH complains the key
> permissions are too open. In PowerShell you can use:
> `icacls your-key.key /inheritance:r /grant:r "$($env:USERNAME):(R)"`

---

## Step 5 — Install everything on the server

Connect to the VM and run the setup:

```bash
ssh -i /path/to/key.key ubuntu@<VM_IP>
bash ~/shorts-generator/deploy/setup_server.sh
```

This will:

- install **Python 3**, **FFmpeg** and the **DejaVu fonts** (required for the
  video text overlays),
- create a virtual environment and install `requirements.txt`,
- open port 8000 in the VM firewall,
- **generate a login password** (saved to `/etc/shorts-generator.env`),
- install a **systemd service** so the app starts on boot and restarts on crash.

When it finishes it prints your URL **and your login password**:

```
http://<VM_IP>:8000
🔑 Login password:  Xy3k9Qz7Lm2Pw8Rt
```

Open that in any browser, enter the password, and you're in! 🎉

---

## Managing the running app

```bash
# See if it's running
sudo systemctl status shorts-generator

# Watch live logs
sudo journalctl -u shorts-generator -f

# Restart after changing code
sudo systemctl restart shorts-generator

# Stop / start
sudo systemctl stop shorts-generator
sudo systemctl start shorts-generator
```

Updating the app later: re-run `deploy\upload.ps1` (or the manual upload), then:

```bash
cd ~/shorts-generator/backend
source venv/bin/activate
pip install -r requirements.txt      # only if requirements changed
sudo systemctl restart shorts-generator
```

> Note: re-running `setup_server.sh` is safe (idempotent) and will also
> re-apply dependency installs.

---

## Optional extras

### AI hooks with Ollama (free, local)

The app already works without AI (uses built-in templates), but for
AI-rewritten hooks you can run Ollama on the VM:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

Then restart the app. Needs ~8 GB free RAM for `llama3` — fine on a 12 GB VM,
too heavy on a 6 GB VM.

### Auto subtitles with Whisper

Subtitles currently fall back to text-based when Whisper isn't installed.
To enable voice-recognition subtitles:

```bash
cd ~/shorts-generator/backend
source venv/bin/activate
pip install faster-whisper
sudo systemctl restart shorts-generator
```

First use downloads a model (~150 MB).

### A real domain + HTTPS (free)

Install Caddy as a reverse proxy for automatic HTTPS:

```bash
sudo apt install -y caddy
# /etc/caddy/Caddyfile:
#   yourdomain.com {
#       reverse_proxy localhost:8000
#   }
sudo systemctl restart caddy
```

Point your domain's DNS A record at the VM IP, then open port 80/443 in the
VCN Security List too.

---

## 🔐 Login & password

The app is protected by a **single shared password**. Anyone without it gets
bounced to a login screen (the API returns `401`).

- The password lives in **`/etc/shorts-generator.env`** (`APP_PASSWORD`).
- It's generated for you when you first run `setup_server.sh` and printed at
  the end — **save it somewhere safe**.
- Share it with anyone you want to give access (or just send them the URL +
  password).

### Change the password

```bash
# Edit the file, replace the APP_PASSWORD= line, save, then:
sudo nano /etc/shorts-generator.env
sudo systemctl restart shorts-generator
```

Changing the password instantly logs everyone out (existing sessions stop
working), then they sign in again with the new one.

### Running locally (no server)

Locally the app falls back to the default password `changeme` and prints a
warning. Override it like this:

```bash
# Windows (PowerShell)
$env:APP_PASSWORD="my-secret"; python app.py

# macOS / Linux
APP_PASSWORD=my-secret python app.py
```

### Behind HTTPS

If you add a domain + HTTPS (see below), also set `COOKIE_SECURE=1` in
`/etc/shorts-generator.env` so the session cookie is only sent over HTTPS, then
restart the service.

## Security note

The app is password-protected, but it's still a good idea to keep the URL
private: anyone with **both** the URL and the password can use your VM's CPU.
For a busy public link, consider changing the password periodically.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Site doesn't load, service is "active" | Add the **VCN ingress rule for TCP 8000** (Step 3). |
| Text on videos looks tiny/ugly | Make sure `fonts-dejavu-core` installed: `sudo apt install fonts-dejavu-core`, then restart. |
| `[WARN] FFmpeg check failed` | `sudo apt install ffmpeg` then `sudo systemctl restart shorts-generator`. |
| Video generation fails | Check logs: `sudo journalctl -u shorts-generator -n 100`. Very long/high-res videos may exceed the VM's CPU. |
| Still unreachable after the VCN rule | Oracle Ubuntu also ships iptables rules. The setup script adds one — verify with `sudo iptables -L INPUT -n --line-numbers \| grep 8000`. |
| `moviepy` / `VideoFileClip` complains about ffmpeg on ARM | Run `sudo systemctl edit shorts-generator`, add `Environment=IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg` under `[Service]`, then `sudo systemctl restart shorts-generator`. |
| "Out of host capacity" when creating VM | Try another Availability Domain / region, or retry later. |
| Login says "Too many failed attempts" | 8 wrong passwords within 5 minutes triggers a temporary lockout. Wait a few minutes and try again. |
| SSH: "permissions too open" on key | `chmod 400 key.key` (Git Bash) or the `icacls` command above. |
