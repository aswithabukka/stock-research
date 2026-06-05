# Host Stock Research on your Mac mini (always-on, free, access anywhere)

Goal: the Mac mini runs the dashboard 24/7; you and your husband open it from any
phone or laptop — at home or on cellular — through a free private network
(Tailscale). The AI analysis keeps working because the Mac mini has Claude Code
logged in.

Do all of this **on the Mac mini** (screen-share / keyboard on it once).

---

## 1. Prerequisites on the Mac mini (one time)

1. **Claude Code** — install it and log in once (this powers the free AI analysis):
   ```bash
   claude   # then follow the login prompt; close it once logged in
   ```
   Verify: `which claude` should print a path.

2. **Tailscale** — free personal account. Install the app from https://tailscale.com/download
   (or `brew install --cask tailscale`), open it, and **sign in**. Do the same
   sign-in (same account) on your iPhone and your husband's phone — that puts all
   your devices on one private network.

3. **Python 3** — macOS already has `python3`. Verify: `python3 --version`.

---

## 2. Put the app on the Mac mini (one time)

You AirDropped `stock-research.zip` from the other Mac. Unzip it into the skills
folder:

```bash
mkdir -p ~/.claude/skills
cd ~/Downloads          # wherever the AirDrop landed
unzip -o stock-research.zip -d ~/.claude/skills/
```

You should now have `~/.claude/skills/stock-research/app.py`.

---

## 3. Set a password (one time)

Pick your own password and write it to this file:

```bash
echo 'YourStrongPasswordHere' > ~/.claude/skills/stock-research/deploy/app_password.txt
chmod 600 ~/.claude/skills/stock-research/deploy/app_password.txt
```

Everyone (you + your husband) types this once per device; it's remembered for the
session. To change it later, edit that file and restart the service (Managing it,
below). Delete the file to turn the password off.

## 4. Build it + install the always-on service (one time)

```bash
chmod +x ~/.claude/skills/stock-research/deploy/run_server.sh

# Install the auto-start service (runs at login, restarts if it crashes):
cp ~/.claude/skills/stock-research/deploy/com.stockresearch.app.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.stockresearch.app.plist 2>/dev/null
launchctl load   ~/Library/LaunchAgents/com.stockresearch.app.plist
```

The first launch builds the Python environment automatically (takes a minute).
Confirm what it bound to:

```bash
tail -5 /tmp/stock_research.out.log    # look for: [run_server] binding to 100.x.x.x:8501
```

It binds **only** to your Tailscale IP (100.x) — so it is invisible on your home
Wi-Fi. If Tailscale wasn't up yet, it falls back to localhost-only and you should
restart the service once Tailscale is running (see Managing it).

> Keep the Mac mini awake: System Settings → Displays/Battery → **Prevent
> automatic sleeping when the display is off** (or "Prevent sleeping"). Enabling
> **automatic login** on the Mac mini is recommended so the service starts after
> a reboot without anyone signing in.

---

## 5. Get the address you'll use everywhere

On the Mac mini, find its Tailscale IP:

```bash
tailscale ip -4          # e.g. 100.101.102.103
```

Your app URL from **any** of your Tailscale devices (phone on cellular included):

```
http://<tailscale-ip>:8501
# e.g. http://100.101.102.103:8501
```

Research a company directly by adding it to the link:

```
http://100.101.102.103:8501/?q=https://www.apple.com
http://100.101.102.103:8501/?ticker=NVDA
```

> Note: because it's bound to the Tailscale IP, `http://localhost:8501` will NOT
> work on the Mac mini itself — use the Tailscale IP everywhere, even on the mini.
> The plain home-Wi-Fi LAN IP will NOT work either, by design (that's the point).

---

## 6. Make it feel like a mobile app

On your iPhone, open the URL in **Safari** → tap the **Share** icon → **Add to
Home Screen**. You get an app icon that opens full-screen. Do the same on your
husband's phone. Free, no App Store, no $99 developer fee.

---

## Managing it

```bash
# Restart after you update the code:
launchctl unload ~/Library/LaunchAgents/com.stockresearch.app.plist
launchctl load   ~/Library/LaunchAgents/com.stockresearch.app.plist

# Stop it for good:
launchctl unload ~/Library/LaunchAgents/com.stockresearch.app.plist

# Change the password (then restart):
echo 'NewPassword' > ~/.claude/skills/stock-research/deploy/app_password.txt

# Logs if something looks off:
tail -f /tmp/stock_research.err.log
```

## Security summary

This setup is hardened for private use:

- **Tailscale-only.** The server binds to your Tailscale IP, so it's invisible on
  your home Wi-Fi/LAN and never on the public internet. Tailscale traffic is
  end-to-end encrypted (WireGuard) and only your own signed-in devices can reach it.
- **Password gate.** Every visitor must enter the password in `app_password.txt`.
- **Secure Streamlit defaults.** XSRF + CORS protections are ON.
- **No secrets at risk.** No API keys; the AI runs on your local Claude login. The
  agent is limited to web search/fetch only — it cannot read your files or run
  commands. No personal financial data is stored.

**Do NOT** port-forward on your router, or use Tailscale Funnel / ngrok /
Cloudflare Tunnel — those would put it on the public internet and undo the above.

## Troubleshooting: can't connect?

Run through this when the page won't load (especially away from home):

1. **Is the Mac mini on and awake?** It's the host — it must be powered on,
   online, and not asleep. (System Settings → enable "Prevent automatic sleeping".)
2. **Is Tailscale ON on your phone?** Open the Tailscale app → the toggle should be
   green/connected. On the Mac mini, Tailscale should also show "Connected".
3. **Are you using the Tailscale address?** It must be `http://100.x.x.x:8501`
   (from `tailscale ip -4` on the mini). `localhost` and your home Wi-Fi IP will
   NOT work — that's by design.
4. **Is the app running on the mini?** On the mini:
   `curl -s -o /dev/null -w "%{http_code}\n" http://$(tailscale ip -4):8501` → want `200`.
   If not, restart it (see Managing it) and check `tail -5 /tmp/stock_research.err.log`.
5. **Wrong/forgotten password?** Reset it: `echo 'NewPass' > deploy/app_password.txt`
   then restart the service.
6. **Phone has no internet at all** (airplane mode / no signal) → nothing can
   connect. Any working internet (cellular or Wi-Fi) is fine as long as Tailscale is on.
7. **"Binding to 127.0.0.1" in the log** means Tailscale wasn't up when the app
   started → start Tailscale on the mini, then restart the service.

## Notes / limits

- **AI analysis needs the Mac mini awake and logged into Claude Code.** If the
  agent tab errors, run `claude` once on the Mac mini to confirm you're still
  signed in.
- Tailscale free tier covers personal use for up to 3 users / 100 devices — plenty
  for the two of you.
- Keep `app_password.txt` private (it's chmod 600 and git-ignored).
