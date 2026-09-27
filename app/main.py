import customtkinter as ctk
from tkinter import ttk, messagebox, simpledialog
import os, json, time, threading, subprocess, re, statistics, webbrowser
from collections import deque
from datetime import datetime
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)
GAMES_FILE = os.path.join(DATA, "games.json")
HISTORY_FILE = os.path.join(DATA, "sessions.json")

SEEDS = [
    ("Brookhaven RP","4924922222"),("Blox Fruits","2753915549"),("Adopt Me!","920587237"),
    ("DOORS","6516141723"),("Murder Mystery 2","142823291"),("Tower of Hell","1962086868"),
    ("Jailbreak","606849621"),("Arsenal","286090429"),("BedWars","6872265039"),
    ("Pet Simulator 99","8737899170"),("Dress To Impress","15101393044"),
    ("The Strongest Battlegrounds","10449761463"),("Blade Ball","13772394625"),
    ("Da Hood","2788229376"),("Natural Disaster Survival","189707"),
    ("Work at a Pizza Place","192800"),("MeepCity","370731277"),("Royale High","735030788"),
    ("Evade","9872472334"),("Rainbow Friends","7991339063"),("Fisch","16732694052"),
    ("RIVALS","17625359962"),("Build A Boat For Treasure","537413528"),
    ("King Legacy","4520749081"),("Anime Defenders","17017769292"),
    ("Anime Vanguards","16146832113"),("Phantom Forces","292439477"),
    ("Vehicle Simulator","171391948"),("Driving Empire","3351674303"),
    ("Car Crushers 2","654732683"),
]

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

class App:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root = ctk.CTk()
        self.root.title("Roblox Gaming Launcher")
        self.root.geometry("1320x820")
        self.root.minsize(1050, 680)
        self.running = True

        self.games = load_json(GAMES_FILE, [{"name": n, "place_id": p} for n,p in SEEDS])
        self.history = load_json(HISTORY_FILE, [])
        self.selected = None
        self.current_page = "Home"
        self.servers = []
        self.server_cursor = None
        self.loading_games = False
        self.loading_servers = False

        self.samples = deque(maxlen=360)
        self.losses = deque(maxlen=360)
        self.icmp = None
        self.roblox_ping = None
        self.roblox_server = None
        self.spikes = 0
        self.lock = threading.Lock()

        self.build_shell()
        self.show_home()

        threading.Thread(target=self.network_worker, daemon=True).start()
        threading.Thread(target=self.roblox_worker, daemon=True).start()
        threading.Thread(target=self.catalog_worker, daemon=True).start()
        self.root.after(250, self.ui_tick)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_shell(self):
        self.sidebar = ctk.CTkFrame(self.root, width=235, corner_radius=0, fg_color="#0b1018")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkLabel(self.sidebar, text="ROBLOX", font=("Segoe UI", 28, "bold"),
                     text_color="#eef4ff").pack(anchor="w", padx=25, pady=(28,0))
        ctk.CTkLabel(self.sidebar, text="GAMING LAUNCHER", font=("Segoe UI", 11, "bold"),
                     text_color="#4d8dff").pack(anchor="w", padx=27, pady=(0,28))

        self.nav_buttons = {}
        for name, icon in [("Home","⌂"),("Games","▦"),("Servers","◈"),("Network","⌁"),
                           ("History","◷"),("Settings","⚙")]:
            b = ctk.CTkButton(self.sidebar, text=f"{icon}   {name}", anchor="w",
                              height=43, corner_radius=9, fg_color="transparent",
                              hover_color="#182335", text_color="#8795a8",
                              font=("Segoe UI", 13, "bold"),
                              command=lambda n=name: self.navigate(n))
            b.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[name] = b

        status = ctk.CTkFrame(self.sidebar, fg_color="#101722", corner_radius=12)
        status.pack(side="bottom", fill="x", padx=14, pady=18)
        ctk.CTkLabel(status, text="LIVE MONITOR", font=("Segoe UI", 10, "bold"),
                     text_color="#8795a8").pack(anchor="w", padx=14, pady=(12,0))
        self.side_ping = ctk.CTkLabel(status, text="-- ms", font=("Segoe UI", 21, "bold"),
                                      text_color="#43d19e")
        self.side_ping.pack(anchor="w", padx=14)
        self.side_status = ctk.CTkLabel(status, text="Starting network monitor…",
                                        font=("Segoe UI", 10), text_color="#8795a8")
        self.side_status.pack(anchor="w", padx=14, pady=(0,12))

        self.main = ctk.CTkFrame(self.root, fg_color="#090d14", corner_radius=0)
        self.main.pack(side="left", fill="both", expand=True)
        self.topbar = ctk.CTkFrame(self.main, height=68, fg_color="#090d14", corner_radius=0)
        self.topbar.pack(fill="x", padx=24, pady=(15,0))
        self.topbar.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(self.topbar, text="Home",
                                        font=("Segoe UI", 25, "bold"), text_color="#eef4ff")
        self.title_label.grid(row=0,column=0,sticky="w")
        ctk.CTkLabel(self.topbar, text="●  LIVE", text_color="#43d19e",
                     font=("Segoe UI", 11, "bold")).grid(row=0,column=1,padx=(10,5))
        self.top_ping = ctk.CTkLabel(self.topbar, text="Internet -- ms", text_color="#8795a8",
                                     font=("Segoe UI", 11, "bold"))
        self.top_ping.grid(row=0,column=2,padx=12)
        self.top_loss = ctk.CTkLabel(self.topbar, text="Loss --", text_color="#8795a8",
                                     font=("Segoe UI", 11, "bold"))
        self.top_loss.grid(row=0,column=3,padx=12)
        self.content = ctk.CTkFrame(self.main, fg_color="#090d14", corner_radius=0)
        self.content.pack(fill="both", expand=True, padx=24, pady=(0,20))

    def navigate(self, page):
        self.current_page = page
        for n,b in self.nav_buttons.items():
            b.configure(fg_color="#182b46" if n == page else "transparent",
                        text_color="#eef4ff" if n == page else "#8795a8")
        {"Home":self.show_home,"Games":self.show_games,"Servers":self.show_servers,
         "Network":self.show_network,"History":self.show_history,"Settings":self.show_settings}[page]()

    def clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def section(self, title, subtitle=""):
        self.title_label.configure(text=title)
        self.clear()
        if subtitle:
            ctk.CTkLabel(self.content, text=subtitle, text_color="#8795a8",
                         font=("Segoe UI", 12)).pack(anchor="w", pady=(0,16))

    def card(self, parent, title, value, subtitle="", color=None):
        f = ctk.CTkFrame(parent, fg_color="#101722", border_color="#202c3d",
                         border_width=1, corner_radius=14)
        ctk.CTkLabel(f, text=title.upper(), text_color="#8795a8",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(14,0))
        ctk.CTkLabel(f, text=value, text_color=color or "#eef4ff",
                     font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=16, pady=(3,0))
        ctk.CTkLabel(f, text=subtitle, text_color="#8795a8",
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(0,14))
        return f

    def show_home(self):
        self.section("Gaming Dashboard","Live metrics continue updating while you switch tabs.")
        cards=ctk.CTkFrame(self.content,fg_color="transparent");cards.pack(fill="x")
        for i in range(4):cards.grid_columnconfigure(i,weight=1)
        self.home_cards={}
        for i,(key,t,s) in enumerate([
            ("internet","INTERNET BASELINE","ICMP to 1.1.1.1 / 8.8.8.8"),
            ("roblox","ROBLOX NETWORK PING","From Roblox client logs when available"),
            ("jitter","JITTER","Last 30 network samples"),
            ("loss","PACKET LOSS","Rolling window")]):
            self.home_cards[key]=self.card(cards,t,"--",s)
            self.home_cards[key].grid(row=0,column=i,sticky="nsew",padx=5)
        body=ctk.CTkFrame(self.content,fg_color="transparent");body.pack(fill="both",expand=True,pady=(18,0))
        body.grid_columnconfigure(0,weight=3);body.grid_columnconfigure(1,weight=2)
        left=ctk.CTkFrame(body,fg_color="#101722",corner_radius=14);left.grid(row=0,column=0,sticky="nsew",padx=(0,8))
        right=ctk.CTkFrame(body,fg_color="#101722",corner_radius=14);right.grid(row=0,column=1,sticky="nsew",padx=(8,0))
        ctk.CTkLabel(left,text="Current session",font=("Segoe UI",18,"bold"),text_color="#eef4ff").pack(anchor="w",padx=20,pady=(18,2))
        self.home_game=ctk.CTkLabel(left,text=self.selected["name"] if self.selected else "No game selected",
                                     font=("Segoe UI",15,"bold"),text_color="#8795a8")
        self.home_game.pack(anchor="w",padx=20,pady=(12,2))
        self.home_server=ctk.CTkLabel(left,text="Server: --",font=("Segoe UI",12),text_color="#8795a8")
        self.home_server.pack(anchor="w",padx=20,pady=2)
        ctk.CTkButton(left,text="Open Games",height=40,command=lambda:self.navigate("Games")).pack(anchor="w",padx=20,pady=20)
        ctk.CTkLabel(right,text="Ping explained",font=("Segoe UI",18,"bold"),text_color="#eef4ff").pack(anchor="w",padx=20,pady=(18,8))
        ctk.CTkLabel(right,text=("Internet baseline and Roblox Network Ping are different measurements. "
            "A low internet ping does not guarantee a low Roblox server ping."),wraplength=350,
            justify="left",text_color="#8795a8",font=("Segoe UI",12)).pack(anchor="w",padx=20)
        ctk.CTkButton(right,text="Open Roblox",height=40,command=self.open_roblox).pack(anchor="w",padx=20,pady=20)
        self.update_home_live()

    def update_home_live(self):
        if self.current_page!="Home" or not hasattr(self,"home_cards"):return
        vals={"internet":f"{self.icmp:.0f} ms" if self.icmp is not None else "--",
              "roblox":f"{self.roblox_ping:.0f} ms" if self.roblox_ping is not None else "--",
              "jitter":self.jitter_text(),"loss":self.loss_text()}
        for key,value in vals.items():
            labels=self.home_cards[key].winfo_children()
            if len(labels)>=2:labels[1].configure(text=value)

    def show_games(self):
        self.section("Game Library",f"{len(self.games)} games saved locally. Search without blocking the UI.")
        bar=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=12);bar.pack(fill="x",pady=(0,10))
        self.game_search=ctk.CTkEntry(bar,placeholder_text="Search games…",height=40)
        self.game_search.pack(side="left",fill="x",expand=True,padx=12,pady=12)
        self.game_search.bind("<KeyRelease>",lambda e:self.render_games())
        ctk.CTkButton(bar,text="Refresh catalog",height=40,command=self.refresh_catalog).pack(side="left",padx=6)
        ctk.CTkButton(bar,text="+ Add game",height=40,command=self.add_game).pack(side="left",padx=(0,12))
        self.game_status=ctk.CTkLabel(self.content,text="Ready",text_color="#8795a8")
        self.game_status.pack(anchor="w",padx=5,pady=(0,6))
        frame=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=12);frame.pack(fill="both",expand=True)
        style=ttk.Style()
        try:style.theme_use("clam")
        except Exception:pass
        style.configure("Treeview",background="#101722",fieldbackground="#101722",foreground="#eef4ff",
                        rowheight=42,borderwidth=0,font=("Segoe UI",11))
        style.configure("Treeview.Heading",background="#151e2b",foreground="#8795a8",
                        font=("Segoe UI",10,"bold"),relief="flat")
        style.map("Treeview",background=[("selected","#234a7d")],foreground=[("selected","white")])
        self.game_tree=ttk.Treeview(frame,columns=("game","id"),show="headings",selectmode="browse")
        self.game_tree.heading("game",text="GAME");self.game_tree.heading("id",text="PLACE ID")
        self.game_tree.column("game",width=430);self.game_tree.column("id",width=230)
        self.game_tree.pack(side="left",fill="both",expand=True,padx=(12,0),pady=12)
        sb=ttk.Scrollbar(frame,orient="vertical",command=self.game_tree.yview);sb.pack(side="right",fill="y",padx=(0,12),pady=12)
        self.game_tree.configure(yscrollcommand=sb.set)
        self.game_tree.bind("<<TreeviewSelect>>",self.game_selected)
        self.game_tree.bind("<Double-1>",lambda e:self.join_selected())
        self.render_games()

    def render_games(self):
        if not hasattr(self,"game_tree"):return
        q=self.game_search.get().strip().lower() if hasattr(self,"game_search") else ""
        for item in self.game_tree.get_children():self.game_tree.delete(item)
        shown=[g for g in self.games if not q or q in g.get("name","").lower()]
        for g in shown:
            self.game_tree.insert("", "end",values=(g.get("name",""),g.get("place_id","")))
        if hasattr(self,"game_status"):self.game_status.configure(text=f"{len(shown)} matching games • Double-click to open servers")

    def game_selected(self,event=None):
        ids=self.game_tree.selection()
        if not ids:return
        v=self.game_tree.item(ids[0],"values")
        self.selected={"name":v[0],"place_id":str(v[1])}
        self.game_status.configure(text=f"Selected: {self.selected['name']}")
        self.side_status.configure(text=f"Selected: {self.selected['name']}")

    def join_selected(self):
        if self.selected:self.navigate("Servers")
        else:messagebox.showinfo("Choose a game","Select a game first.")

    def add_game(self):
        n=simpledialog.askstring("Add game","Game name:")
        if not n:return
        p=simpledialog.askstring("Add game","Roblox Place ID:")
        if not p or not p.isdigit():return
        self.games.append({"name":n.strip(),"place_id":p.strip()});save_json(GAMES_FILE,self.games);self.render_games()

    def refresh_catalog(self):
        if self.loading_games:return
        self.loading_games=True
        if hasattr(self,"game_status"):self.game_status.configure(text="Refreshing catalog in background…")
        threading.Thread(target=self.catalog_worker_once,daemon=True).start()

    def catalog_worker(self):
        time.sleep(1)
        self.catalog_worker_once()

    def catalog_worker_once(self):
        try:
            r=requests.get("https://api.rolimons.com/games/v1/gamelist",timeout=15);r.raise_for_status()
            data=r.json().get("games",{});fresh=[]
            for pid,v in data.items():
                if isinstance(v,list) and len(v)>1 and str(pid).isdigit():
                    fresh.append({"name":str(v[0]),"place_id":str(pid),"players":int(v[1] or 0)})
            fresh.sort(key=lambda x:x.get("players",0),reverse=True)
            old={g["place_id"]:g for g in self.games}
            for g in fresh[:150]:old[g["place_id"]]=g
            new=list(old.values());new.sort(key=lambda x:x.get("players",0),reverse=True)
            self.root.after(0,lambda:self.finish_catalog(new[:200]))
        except Exception as e:self.root.after(0,lambda:self.finish_catalog(None,str(e)))

    def finish_catalog(self,new,error=None):
        self.loading_games=False
        if new:self.games=new;save_json(GAMES_FILE,self.games)
        if hasattr(self,"game_status"):
            self.game_status.configure(text=(f"Catalog updated • {len(self.games)} games" if new else f"Catalog refresh failed: {error}"))
            self.render_games()

    def show_servers(self):
        self.section("Server Browser","Real public server data. Per-server Roblox ping is not available before joining.")
        top=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=12);top.pack(fill="x",pady=(0,10))
        ctk.CTkLabel(top,text=self.selected["name"] if self.selected else "No game selected",
                     font=("Segoe UI",18,"bold"),text_color="#eef4ff").pack(side="left",padx=18,pady=15)
        self.server_status=ctk.CTkLabel(top,text="Ready",text_color="#8795a8");self.server_status.pack(side="left")
        ctk.CTkButton(top,text="Find best available",height=38,command=self.find_best_server).pack(side="right",padx=6,pady=10)
        ctk.CTkButton(top,text="Refresh",height=38,command=lambda:self.load_servers(True)).pack(side="right",padx=6,pady=10)
        frame=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=12);frame.pack(fill="both",expand=True)
        style=ttk.Style();style.configure("Server.Treeview",background="#101722",fieldbackground="#101722",
            foreground="#eef4ff",rowheight=43,font=("Segoe UI",11))
        self.server_tree=ttk.Treeview(frame,columns=("players","free","score","id"),show="headings")
        for c,h,w in [("players","PLAYERS",120),("free","FREE SLOTS",130),("score","HEURISTIC SCORE",160),("id","SERVER ID",350)]:
            self.server_tree.heading(c,text=h);self.server_tree.column(c,width=w)
        self.server_tree.pack(fill="both",expand=True,padx=12,pady=12)
        self.server_tree.bind("<Double-1>",lambda e:self.join_tree_server())
        if self.selected:self.load_servers()

    def load_servers(self,refresh=False):
        if not self.selected or self.loading_servers:return
        if refresh:self.servers=[];self.server_cursor=None
        self.loading_servers=True
        if hasattr(self,"server_status"):self.server_status.configure(text="Loading servers in background…")
        threading.Thread(target=self.server_worker,args=(self.selected["place_id"],self.server_cursor),daemon=True).start()

    def server_worker(self,place,cursor):
        try:
            params={"sortOrder":"Desc","limit":100}
            if cursor:params["cursor"]=cursor
            r=requests.get(f"https://games.roblox.com/v1/games/{place}/servers/Public",params=params,
                           timeout=15,headers={"User-Agent":"RobloxGamingLauncher/4.0"})
            r.raise_for_status();d=r.json()
            self.root.after(0,lambda:self.finish_servers(d.get("data",[]),d.get("nextPageCursor")))
        except Exception as e:self.root.after(0,lambda:self.finish_servers([],None,str(e)))

    def finish_servers(self,data,cursor,error=None):
        self.loading_servers=False
        if error:
            if hasattr(self,"server_status"):self.server_status.configure(text=f"Server load failed: {error}")
            return
        self.servers.extend(data);self.server_cursor=cursor
        if hasattr(self,"server_tree"):
            for i in self.server_tree.get_children():self.server_tree.delete(i)
            for s in sorted(self.servers,key=self.server_score,reverse=True):
                players=int(s.get("playing",0) or 0);maxp=int(s.get("maxPlayers",0) or 0)
                self.server_tree.insert("", "end",values=(f"{players}/{maxp}",max(0,maxp-players),
                    f"{self.server_score(s):.0f}",s.get("id","")[:32]))
            self.server_status.configure(text=f"{len(self.servers)} public servers loaded")

    def server_score(self,s):
        players=int(s.get("playing",0) or 0);maxp=int(s.get("maxPlayers",0) or 0)
        free=max(0,maxp-players);base=max(0,100-min(self.icmp or 250,250)*.2)
        return base+min(free,15)*2

    def find_best_server(self):
        if not self.servers:self.load_servers();return
        self.launch_server(max(self.servers,key=self.server_score))

    def join_tree_server(self):
        ids=self.server_tree.selection()
        if not ids:return
        sid=self.server_tree.item(ids[0],"values")[3]
        for s in self.servers:
            if s.get("id","").startswith(sid):self.launch_server(s);return

    def launch_server(self,s):
        if not self.selected:return
        try:
            os.startfile(f"roblox://placeId={self.selected['place_id']}&gameInstanceId={s['id']}")
            self.roblox_server=s.get("id");self.side_status.configure(text=f"Joining {self.selected['name']}")
            self.save_session()
        except Exception as e:messagebox.showerror("Join failed",str(e))

    def show_network(self):
        self.section("Network Monitor","The monitor keeps running even when this tab is closed.")
        grid=ctk.CTkFrame(self.content,fg_color="transparent");grid.pack(fill="x")
        for i in range(3):grid.grid_columnconfigure(i,weight=1)
        self.net_cards={}
        for i,(k,t) in enumerate([("p","INTERNET BASELINE"),("j","JITTER"),("l","PACKET LOSS")]):
            self.net_cards[k]=self.card(grid,t,"--","Live background measurement");self.net_cards[k].grid(row=0,column=i,sticky="nsew",padx=5)
        box=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=14);box.pack(fill="both",expand=True,pady=(16,0))
        ctk.CTkLabel(box,text="Live diagnostics",font=("Segoe UI",18,"bold"),text_color="#eef4ff").pack(anchor="w",padx=20,pady=(18,8))
        self.net_detail=ctk.CTkTextbox(box,height=260,fg_color="#0c121b",text_color="#8795a8")
        self.net_detail.pack(fill="both",expand=True,padx=20,pady=(0,20));self.update_network_page()

    def update_network_page(self):
        if self.current_page!="Network":return
        vals={"p":f"{self.icmp:.0f} ms" if self.icmp is not None else "--","j":self.jitter_text(),"l":self.loss_text()}
        for k,v in vals.items():
            labels=self.net_cards[k].winfo_children()
            if len(labels)>=2:labels[1].configure(text=v)
        self.net_detail.delete("1.0","end")
        self.net_detail.insert("end",f"Internet baseline: {vals['p']}\nRoblox Network Ping: {self.roblox_ping:.0f} ms\n" if self.roblox_ping is not None else f"Internet baseline: {vals['p']}\nRoblox Network Ping: --\n")
        self.net_detail.insert("end",f"Jitter: {vals['j']}\nPacket loss: {vals['l']}\nPing spikes detected: {self.spikes}\n")

    def show_history(self):
        self.section("Session History","Saved locally after a Roblox join.")
        box=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=14);box.pack(fill="both",expand=True)
        t=ctk.CTkTextbox(box,fg_color="#101722",text_color="#8795a8");t.pack(fill="both",expand=True,padx=16,pady=16)
        for h in reversed(self.history[-100:]):
            t.insert("end",f"{h.get('time','')} | {h.get('game','No game')} | avg {h.get('avg','--')} | worst {h.get('worst','--')} | loss {h.get('loss','--')}\n")

    def show_settings(self):
        self.section("Settings","Safe Windows gaming options.")
        f=ctk.CTkFrame(self.content,fg_color="#101722",corner_radius=14);f.pack(fill="x",padx=5)
        ctk.CTkLabel(f,text="Windows power plan",font=("Segoe UI",18,"bold"),text_color="#eef4ff").pack(anchor="w",padx=20,pady=(18,3))
        ctk.CTkLabel(f,text="Only changes the Windows power plan.",text_color="#8795a8").pack(anchor="w",padx=20)
        ctk.CTkButton(f,text="High Performance",command=lambda:self.power("SCHEME_MIN")).pack(anchor="w",padx=20,pady=18)
        ctk.CTkButton(f,text="Restore Balanced",command=lambda:self.power("SCHEME_BALANCED")).pack(anchor="w",padx=20,pady=(0,20))

    def power(self,scheme):
        try:subprocess.run(["powercfg","/setactive",scheme],capture_output=True);messagebox.showinfo("Power plan","Power plan updated.")
        except Exception as e:messagebox.showerror("Power plan",str(e))

    def open_roblox(self):
        try:os.startfile("roblox-player:")
        except Exception:webbrowser.open("https://www.roblox.com/")

    def ping(self,host):
        try:
            p=subprocess.run(["ping","-n","1","-w","800",host],capture_output=True,text=True,timeout=2)
            m=re.search(r"time[=<]\s*(\d+)\s*ms",p.stdout,re.I)
            return float(m.group(1)) if m else None
        except Exception:return None

    def network_worker(self):
        hosts=["1.1.1.1","8.8.8.8"];i=0
        while self.running:
            v=self.ping(hosts[i%2]);i+=1
            with self.lock:
                self.icmp=v;self.losses.append(0 if v is not None else 1)
                if v is not None:self.samples.append(v)
                if len(self.samples)>=8:
                    avg=statistics.mean(list(self.samples)[-30:])
                    if v>max(100,avg*2.5) and v-avg>40:self.spikes+=1
            time.sleep(.7)

    def roblox_worker(self):
        path=os.path.expandvars(r"%LOCALAPPDATA%\Roblox\logs");last_path=None;last_mtime=0
        while self.running:
            try:
                if os.path.isdir(path):
                    files=[os.path.join(path,x) for x in os.listdir(path) if x.lower().endswith(".log")]
                    if files:
                        p=max(files,key=os.path.getmtime);mt=os.path.getmtime(p)
                        if p!=last_path or mt!=last_mtime:
                            last_path, last_mtime=p, mt
                            with open(p,"r",encoding="utf-8",errors="ignore") as f:txt=f.read()[-900000:]
                            vals=re.findall(r"(?:NetworkPing|Network Ping)[^0-9]{0,30}(\d+(?:\.\d+)?)",txt,re.I)
                            if vals:self.roblox_ping=float(vals[-1])
                            a=re.findall(r"Server Address[^0-9]*(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?",txt,re.I)
                            if a:self.roblox_server=a[-1][0]+((":"+a[-1][1]) if a[-1][1] else "")
            except Exception:pass
            time.sleep(1.5)

    def jitter_text(self):
        with self.lock:x=list(self.samples)[-30:]
        if len(x)<2:return "--"
        return f"{statistics.mean(abs(x[i]-x[i-1]) for i in range(1,len(x))):.1f} ms"

    def loss_text(self):
        with self.lock:x=list(self.losses)
        return f"{(statistics.mean(x)*100 if x else 0):.1f}%"

    def update_live_labels(self):
        self.top_ping.configure(text=f"Internet {self.icmp:.0f} ms" if self.icmp is not None else "Internet --")
        self.top_loss.configure(text=f"Loss {self.loss_text()}")
        self.side_ping.configure(text=f"{self.icmp:.0f} ms" if self.icmp is not None else "-- ms")
        self.side_status.configure(text=(f"Monitoring • Roblox ping {self.roblox_ping:.0f} ms" if self.roblox_ping is not None else "Monitoring • Roblox ping unavailable"))
        self.update_home_live();self.update_network_page()

    def ui_tick(self):
        if not self.running:return
        try:self.update_live_labels()
        except Exception:pass
        self.root.after(300,self.ui_tick)

    def save_session(self):
        with self.lock:x=list(self.samples)
        rec={"time":datetime.now().strftime("%Y-%m-%d %H:%M"),
             "game":self.selected["name"] if self.selected else "No game",
             "avg":f"{statistics.mean(x):.0f} ms" if x else "--",
             "worst":f"{max(x):.0f} ms" if x else "--","loss":self.loss_text()}
        self.history.append(rec);self.history=self.history[-200:];save_json(HISTORY_FILE,self.history)

    def close(self):
        self.running=False
        try:self.save_session()
        except Exception:pass
        self.root.destroy()

if __name__=="__main__":
    App().root.mainloop()
