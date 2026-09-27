import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess, threading, time, socket, os, re, json, webbrowser, statistics
from collections import deque
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(BASE), "data")
GAMES_FILE = os.path.join(DATA, "games.json")
HISTORY_FILE = os.path.join(DATA, "sessions.json")
os.makedirs(DATA, exist_ok=True)

DEFAULT_GAMES = [
    {"name": "Brookhaven RP", "place_id": "4924922222", "favorite": False},
    {"name": "Blox Fruits", "place_id": "2753915549", "favorite": False},
    {"name": "DOORS", "place_id": "6516141723", "favorite": False},
    {"name": "Adopt Me!", "place_id": "920587237", "favorite": False},
]

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class RobloxLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Roblox Gaming Launcher")
        self.root.geometry("1180x760")
        self.root.minsize(1000, 650)
        self.running = True
        self.monitoring = True
        self.samples = deque(maxlen=300)
        self.losses = deque(maxlen=300)
        self.spikes = deque(maxlen=200)
        self.games = load_json(GAMES_FILE, DEFAULT_GAMES)
        self.history = load_json(HISTORY_FILE, [])
        self.selected_game = None
        self.servers = []
        self.server_loading = False
        self.session_start = datetime.now()
        self.session_spikes = 0
        self.last_ping = None
        self.status_var = tk.StringVar(value="Ready")
        self.ping_var = tk.StringVar(value="--")
        self.avg_var = tk.StringVar(value="--")
        self.jitter_var = tk.StringVar(value="--")
        self.loss_var = tk.StringVar(value="0%")
        self.cpu_var = tk.StringVar(value="--")
        self.ram_var = tk.StringVar(value="--")
        self.game_var = tk.StringVar(value="No game selected")
        self.build_ui()
        self.refresh_games()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.root.after(1000, self.refresh_system)

    def build_ui(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Card.TLabelframe", padding=10)
        style.configure("CardValue.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        header = ttk.Frame(self.root, padding=(18, 14, 18, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Roblox Gaming Launcher", style="Title.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status_var).pack(side="right")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=8)
        self.home = ttk.Frame(self.notebook, padding=14)
        self.library = ttk.Frame(self.notebook, padding=14)
        self.servers_tab = ttk.Frame(self.notebook, padding=14)
        self.monitor_tab = ttk.Frame(self.notebook, padding=14)
        self.history_tab = ttk.Frame(self.notebook, padding=14)
        self.settings_tab = ttk.Frame(self.notebook, padding=14)
        for tab, name in [(self.home,"Home"),(self.library,"Game Library"),(self.servers_tab,"Servers"),(self.monitor_tab,"Live Monitor"),(self.history_tab,"History"),(self.settings_tab,"Settings")]:
            self.notebook.add(tab, text=name)
        self.build_home()
        self.build_library()
        self.build_servers()
        self.build_monitor()
        self.build_history()
        self.build_settings()

    def metric_card(self, parent, title, variable, row, col):
        f = ttk.LabelFrame(parent, text=title, style="Card.TLabelframe")
        f.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        ttk.Label(f, textvariable=variable, style="CardValue.TLabel").pack()
        return f

    def build_home(self):
        top = ttk.LabelFrame(self.home, text="Selected game", padding=12)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.game_var, font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(top, text="JOIN BEST SERVER", style="Accent.TButton", command=self.join_best).pack(side="right", padx=5)
        ttk.Button(top, text="Browse Servers", command=lambda: self.notebook.select(self.servers_tab)).pack(side="right", padx=5)

        cards = ttk.Frame(self.home)
        cards.pack(fill="x", pady=12)
        for i in range(4): cards.columnconfigure(i, weight=1)
        self.metric_card(cards, "Current Ping", self.ping_var, 0, 0)
        self.metric_card(cards, "Average", self.avg_var, 0, 1)
        self.metric_card(cards, "Jitter", self.jitter_var, 0, 2)
        self.metric_card(cards, "Packet Loss", self.loss_var, 0, 3)

        actions = ttk.LabelFrame(self.home, text="Quick actions", padding=12)
        actions.pack(fill="x", pady=5)
        ttk.Button(actions, text="Open Roblox", command=self.launch_roblox).pack(side="left", padx=5)
        ttk.Button(actions, text="Gaming Optimize", command=self.optimize).pack(side="left", padx=5)
        ttk.Button(actions, text="Reset Optimizer", command=self.reset_optimize).pack(side="left", padx=5)
        ttk.Button(actions, text="20s Connection Test", command=self.run_test).pack(side="left", padx=5)

        info = ttk.LabelFrame(self.home, text="How it works", padding=12)
        info.pack(fill="both", expand=True, pady=10)
        ttk.Label(info, justify="left", wraplength=900, text=
            "Choose a Roblox game from your library, then use JOIN BEST SERVER to fetch public servers and pick a suitable one. "
            "The launcher continuously measures your connection while you play, so sudden lag spikes are recorded instead of relying on one ping test. "
            "Exact Roblox game-server latency/IP is not exposed reliably to normal desktop apps, so the server browser never pretends that a displayed value is an exact server ping."
        ).pack(anchor="nw")

    def build_library(self):
        bar = ttk.Frame(self.library)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search games:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_games())
        ttk.Entry(bar, textvariable=self.search_var, width=45).pack(side="left", padx=8)
        ttk.Button(bar, text="Add Game", command=self.add_game).pack(side="right")
        ttk.Button(bar, text="Remove Selected", command=self.remove_game).pack(side="right", padx=5)

        self.game_list = ttk.Treeview(self.library, columns=("name","place","fav"), show="headings", height=18)
        self.game_list.heading("name", text="Game")
        self.game_list.heading("place", text="Place ID")
        self.game_list.heading("fav", text="Favorite")
        self.game_list.column("name", width=420)
        self.game_list.column("place", width=180)
        self.game_list.column("fav", width=100)
        self.game_list.pack(fill="both", expand=True, pady=10)
        self.game_list.bind("<<TreeviewSelect>>", self.select_game)
        ttk.Label(self.library, text="Tip: Add any Roblox game by its Place ID. Search filters your saved library.").pack(anchor="w")

    def build_servers(self):
        top = ttk.Frame(self.servers_tab)
        top.pack(fill="x")
        ttk.Label(top, textvariable=self.game_var, font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Button(top, text="Find Servers", command=self.find_servers).pack(side="right")
        ttk.Button(top, text="Join Selected", command=self.join_selected_server).pack(side="right", padx=5)
        ttk.Button(top, text="Join Best", command=self.join_best).pack(side="right", padx=5)

        cols = ("id","players","max","fps","age","score")
        self.server_tree = ttk.Treeview(self.servers_tab, columns=cols, show="headings")
        heads = {"id":"Server ID","players":"Players","max":"Max","fps":"FPS","age":"Ping/Info","score":"Selection Score"}
        widths = {"id":350,"players":90,"max":80,"fps":90,"age":180,"score":150}
        for c in cols:
            self.server_tree.heading(c, text=heads[c])
            self.server_tree.column(c, width=widths[c])
        self.server_tree.pack(fill="both", expand=True, pady=10)
        ttk.Label(self.servers_tab, text="Scores prioritize available slots and your current network health. Roblox does not expose reliable exact public-server ping to this app.").pack(anchor="w")

    def build_monitor(self):
        cards = ttk.Frame(self.monitor_tab)
        cards.pack(fill="x")
        for i in range(2): cards.columnconfigure(i, weight=1)
        self.metric_card(cards, "CPU", self.cpu_var, 0, 0)
        self.metric_card(cards, "RAM", self.ram_var, 0, 1)

        self.canvas = tk.Canvas(self.monitor_tab, height=330, background="#101318", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=10)
        bottom = ttk.Frame(self.monitor_tab)
        bottom.pack(fill="both", expand=True)
        ttk.Label(bottom, text="Live event log").pack(anchor="w")
        self.log = tk.Text(bottom, height=8, state="disabled", font=("Consolas",9))
        self.log.pack(fill="both", expand=True)
        self.log_msg("Continuous network monitoring started.")

    def build_history(self):
        ttk.Button(self.history_tab, text="Refresh", command=self.refresh_history).pack(anchor="e")
        self.history_tree = ttk.Treeview(self.history_tab, columns=("time","game","avg","worst","loss","spikes"), show="headings")
        for c,t in [("time","Date"),("game","Game"),("avg","Avg Ping"),("worst","Worst"),("loss","Loss"),("spikes","Spikes")]:
            self.history_tree.heading(c,text=t)
        self.history_tree.pack(fill="both", expand=True, pady=10)
        self.refresh_history()

    def build_settings(self):
        self.auto_opt = tk.BooleanVar(value=False)
        self.interval_var = tk.DoubleVar(value=0.5)
        ttk.Checkbutton(self.settings_tab, text="Automatically enable high-performance power plan when launching", variable=self.auto_opt).pack(anchor="w", pady=8)
        ttk.Label(self.settings_tab, text="Ping monitor interval (seconds)").pack(anchor="w")
        ttk.Spinbox(self.settings_tab, from_=0.25, to=2.0, increment=0.05, textvariable=self.interval_var, width=10).pack(anchor="w", pady=5)
        ttk.Label(self.settings_tab, wraplength=850, justify="left", text=
            "Safe optimization only changes the Windows power plan. No registry hacks, security disabling, or network adapter modifications are performed. "
            "Server discovery uses Roblox's public server listing when available."
        ).pack(anchor="w", pady=15)

    def log_msg(self, msg):
        def add():
            self.log.configure(state="normal")
            self.log.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(0, add)

    def ping(self, host):
        try:
            p = subprocess.run(["ping","-n","1","-w","800",host], capture_output=True, text=True, timeout=2)
            m = re.search(r"(?:time[=<]\s*)(\d+)\s*ms", p.stdout, re.I)
            return float(m.group(1)) if m else None
        except Exception:
            return None

    def monitor_loop(self):
        hosts = ["1.1.1.1","8.8.8.8"]
        i = 0
        while self.monitoring:
            v = self.ping(hosts[i % 2]); i += 1
            if v is None:
                self.losses.append(1); self.last_ping = None
                self.root.after(0, self.update_monitor_ui)
            else:
                self.losses.append(0); self.last_ping = v
                self.samples.append((time.time(),v))
                recent = [x[1] for x in list(self.samples)[-30:]]
                avg = statistics.mean(recent) if recent else v
                jitter = statistics.mean([abs(recent[j]-recent[j-1]) for j in range(1,len(recent))]) if len(recent)>1 else 0
                if v > max(100, avg*2.5) and v-avg > 40:
                    self.spikes.append((time.time(),v)); self.session_spikes += 1
                    self.log_msg(f"PING SPIKE: {v:.0f} ms (recent avg {avg:.0f} ms)")
                self.root.after(0, self.update_monitor_ui)
            try: delay = max(0.25, float(self.interval_var.get()))
            except Exception: delay = 0.5
            time.sleep(delay)

    def update_monitor_ui(self):
        vals = [v for _,v in self.samples]
        recent = vals[-30:]
        avg = statistics.mean(recent) if recent else None
        jitter = statistics.mean([abs(recent[i]-recent[i-1]) for i in range(1,len(recent))]) if len(recent)>1 else 0
        loss = (sum(self.losses)/len(self.losses)*100) if self.losses else 0
        self.ping_var.set("--" if self.last_ping is None else f"{self.last_ping:.0f} ms")
        self.avg_var.set("--" if avg is None else f"{avg:.0f} ms")
        self.jitter_var.set(f"{jitter:.1f} ms")
        self.loss_var.set(f"{loss:.1f}%")
        self.status_var.set("LIVE • Monitoring" if self.last_ping is not None else "LIVE • Packet loss")
        self.draw_graph()

    def draw_graph(self):
        if not hasattr(self,"canvas"): return
        c=self.canvas; c.delete("all")
        w=max(c.winfo_width(),400); h=max(c.winfo_height(),250)
        vals=[v for _,v in list(self.samples)[-120:]]
        if not vals:
            c.create_text(w/2,h/2,text="Waiting for measurements...",fill="white")
            return
        mx=max(max(vals),100)
        step=w/max(1,len(vals)-1)
        pts=[]
        for i,v in enumerate(vals):
            x=i*step; y=h-25-(v/mx)*(h-50)
            pts.extend((x,y))
        if len(pts)>=4: c.create_line(*pts,fill="#58a6ff",width=2,smooth=True)
        c.create_text(10,10,anchor="nw",text=f"{len(vals)} samples • scale {mx:.0f} ms",fill="#b8c0cc")

    def refresh_system(self):
        if psutil:
            try:
                self.cpu_var.set(f"{psutil.cpu_percent():.0f}%")
                self.ram_var.set(f"{psutil.virtual_memory().percent:.0f}%")
            except Exception: pass
        if self.running: self.root.after(1500,self.refresh_system)

    def refresh_games(self):
        q=self.search_var.get().lower() if hasattr(self,"search_var") else ""
        for item in self.game_list.get_children(): self.game_list.delete(item)
        for i,g in enumerate(self.games):
            if q and q not in g["name"].lower(): continue
            self.game_list.insert("", "end", iid=str(i), values=(g["name"],g["place_id"],"★" if g.get("favorite") else ""))

    def select_game(self, _=None):
        sel=self.game_list.selection()
        if not sel: return
        self.selected_game=self.games[int(sel[0])]
        self.game_var.set(self.selected_game["name"])
        self.status_var.set(f"Selected • {self.selected_game['name']}")

    def add_game(self):
        name=simpledialog.askstring("Add game","Game name:")
        if not name: return
        pid=simpledialog.askstring("Add game","Roblox Place ID:")
        if not pid or not pid.isdigit(): return messagebox.showerror("Invalid ID","Place ID must be numeric.")
        self.games.append({"name":name.strip(),"place_id":pid.strip(),"favorite":False})
        save_json(GAMES_FILE,self.games); self.refresh_games()

    def remove_game(self):
        sel=self.game_list.selection()
        if not sel: return
        g=self.games.pop(int(sel[0]))
        save_json(GAMES_FILE,self.games); self.selected_game=None; self.game_var.set("No game selected"); self.refresh_games()
        self.log_msg(f"Removed {g['name']} from library.")

    def fetch_servers(self, place_id):
        if requests is None: raise RuntimeError("requests is not installed. Run SETUP.bat.")
        url=f"https://games.roblox.com/v1/games/{place_id}/servers/Public?sortOrder=Asc&limit=100"
        r=requests.get(url,timeout=10,headers={"User-Agent":"RobloxGamingLauncher/2.0"})
        r.raise_for_status()
        return r.json().get("data",[])

    def find_servers(self):
        if not self.selected_game:
            return messagebox.showinfo("Choose a game","Select a game from Game Library first.")
        if self.server_loading: return
        self.server_loading=True
        self.status_var.set("Finding public servers...")
        for x in self.server_tree.get_children(): self.server_tree.delete(x)
        threading.Thread(target=self.server_worker,daemon=True).start()

    def server_worker(self):
        try:
            data=self.fetch_servers(self.selected_game["place_id"])
            self.servers=data
            self.root.after(0,self.show_servers)
        except Exception as e:
            self.root.after(0,lambda: messagebox.showerror("Server discovery failed",str(e)))
        finally:
            self.server_loading=False

    def server_score(self,s):
        playing=int(s.get("playing",0) or 0); maxp=int(s.get("maxPlayers",1) or 1)
        free=maxp-playing
        ping=self.last_ping if self.last_ping is not None else 999
        # This is a selection score, not a server ping.
        return max(0,100 - min(ping,200)*0.2) + min(free,10)*2 + (5 if playing < maxp else 0)

    def show_servers(self):
        self.server_tree.delete(*self.server_tree.get_children())
        ranked=sorted(self.servers,key=self.server_score,reverse=True)
        for s in ranked:
            sid=s.get("id","")
            self.server_tree.insert("", "end", iid=sid, values=(sid[:28]+"..." if len(sid)>28 else sid,s.get("playing","?"),s.get("maxPlayers","?"),s.get("fps","?"),f"current {self.last_ping:.0f} ms" if self.last_ping else "measuring",f"{self.server_score(s):.1f}"))
        self.status_var.set(f"Found {len(ranked)} public servers")
        self.log_msg(f"Loaded {len(ranked)} public servers for {self.selected_game['name']}.")

    def join_selected_server(self):
        sel=self.server_tree.selection()
        if not sel: return messagebox.showinfo("Choose a server","Select a server first.")
        self.launch_server(sel[0])

    def join_best(self):
        if not self.selected_game:
            return messagebox.showinfo("Choose a game","Select a game from Game Library first.")
        if not self.servers:
            self.find_servers()
            self.root.after(1500,self.join_best)
            return
        best=max(self.servers,key=self.server_score)
        self.launch_server(best.get("id"))

    def launch_server(self, server_id=None):
        if not self.selected_game: return
        pid=self.selected_game["place_id"]
        try:
            if server_id:
                uri=f"roblox://placeId={pid}&gameInstanceId={server_id}"
                os.startfile(uri)
                self.log_msg(f"Joining selected server for {self.selected_game['name']}.")
            else:
                os.startfile("roblox-player:")
                self.log_msg(f"Opening {self.selected_game['name']}.")
            if self.auto_opt.get(): self.optimize()
        except Exception as e:
            messagebox.showerror("Roblox launch failed",str(e))

    def launch_roblox(self):
        self.launch_server(None)

    def optimize(self):
        try:
            subprocess.run(["powercfg","/setactive","SCHEME_MIN"],capture_output=True)
            self.log_msg("High-performance Windows power plan requested.")
        except Exception as e: self.log_msg(f"Optimization failed: {e}")

    def reset_optimize(self):
        try:
            subprocess.run(["powercfg","/setactive","SCHEME_BALANCED"],capture_output=True)
            self.log_msg("Balanced power plan restored.")
        except Exception as e: self.log_msg(f"Reset failed: {e}")

    def run_test(self):
        self.log_msg("Running 20-second connection test...")
        def work():
            vals=[]
            for _ in range(20):
                v=self.ping("1.1.1.1")
                if v is not None: vals.append(v)
                time.sleep(1)
            if vals: self.log_msg(f"Test: avg {statistics.mean(vals):.0f} ms • min {min(vals):.0f} • max {max(vals):.0f} • replies {len(vals)}/20")
            else: self.log_msg("Test: no replies.")
        threading.Thread(target=work,daemon=True).start()

    def refresh_history(self):
        if not hasattr(self,"history_tree"): return
        self.history_tree.delete(*self.history_tree.get_children())
        for h in reversed(self.history[-100:]):
            self.history_tree.insert("", "end", values=(h.get("time",""),h.get("game",""),h.get("avg",""),h.get("worst",""),h.get("loss",""),h.get("spikes","")))

    def close(self):
        self.monitoring=False; self.running=False
        vals=[v for _,v in self.samples]
        if vals:
            self.history.append({
                "time":datetime.now().strftime("%Y-%m-%d %H:%M"),
                "game":self.selected_game["name"] if self.selected_game else "No game",
                "avg":f"{statistics.mean(vals):.0f} ms",
                "worst":f"{max(vals):.0f} ms",
                "loss":f"{(sum(self.losses)/len(self.losses)*100):.1f}%" if self.losses else "0%",
                "spikes":self.session_spikes
            })
            save_json(HISTORY_FILE,self.history[-200:])
        self.root.destroy()

if __name__ == "__main__":
    root=tk.Tk()
    RobloxLauncher(root)
    root.mainloop()
