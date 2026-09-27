# Roblox Gaming Launcher

A Windows Roblox launcher with a modern multi-tab GUI, saved game library, public-server browser, continuous network monitoring, lag-spike detection, session history, and safe gaming optimization.

## Features

- Searchable Game Library
- Add/remove Roblox games by Place ID
- Selected-game Home dashboard
- JOIN BEST SERVER
- Public server browser using Roblox's public server listing API
- Join a specific public server when Roblox accepts the gameInstanceId URI
- Continuous ping monitoring instead of a one-time test
- Average ping, jitter, packet loss, spikes, worst ping
- Live graph
- CPU/RAM monitoring
- Session history saved in data/sessions.json
- Safe Windows high-performance power-plan toggle
- 20-second connection test
- Settings for monitor interval and automatic optimization
- SETUP.bat and ROBLOX_LAUNCHER.bat

## Important server limitation

Normal desktop apps do not reliably receive the real IP/latency of every Roblox game server. The server browser therefore shows public server metadata and a selection score based on available slots plus your current network health. It does **not** fake an exact per-server ping.

## Install

1. Run SETUP.bat once.
2. Run ROBLOX_LAUNCHER.bat.
3. Open Game Library and select/add a game.
4. Use Find Servers or JOIN BEST SERVER.

## Data

Game library: data/games.json
Session history: data/sessions.json
