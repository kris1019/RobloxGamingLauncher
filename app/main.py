
import customtkinter as ctk
from tkinter import messagebox, simpledialog
import os,json,time,threading,subprocess,re,statistics,requests
from collections import deque
from datetime import datetime

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DATA=os.path.join(ROOT,"data"); os.makedirs(DATA,exist_ok=True)
GAMES=os.path.join(DATA,"games.json"); HISTORY=os.path.join(DATA,"sessions.json")
SEEDS=[("Brookhaven RP","4924922222"),("Blox Fruits","2753915549"),("Adopt Me!","920587237"),("DOORS","6516141723"),("Murder Mystery 2","142823291"),("Tower of Hell","1962086868"),("Jailbreak","606849621"),("Arsenal","286090429"),("BedWars","6872265039"),("Pet Simulator 99","8737899170"),("Dress To Impress","15101393044"),("The Strongest Battlegrounds","10449761463"),("Blade Ball","13772394625"),("Da Hood","2788229376"),("Natural Disaster Survival","189707"),("Work at a Pizza Place","192800"),("MeepCity","370731277"),("Royale High","735030788"),("Evade","9872472334"),("Rainbow Friends","7991339063"),("Fisch","16732694052"),("RIVALS","17625359962"),("Build A Boat For Treasure","537413528"),("King Legacy","4520749081"),("Anime Defenders","17017769292"),("Anime Vanguards","16146832113"),("Phantom Forces","292439477"),("Vehicle Simulator","171391948"),("Driving Empire","3351674303"),("Car Crushers 2","654732683")]
def load(p,d):
    try:return json.load(open(p,encoding="utf8"))
    except:return d
def save(p,d):json.dump(d,open(p,"w",encoding="utf8"),indent=2,ensure_ascii=False)

class App:
    def __init__(self):
        ctk.set_appearance_mode("dark");ctk.set_default_color_theme("blue")
        self.root=ctk.CTk();self.root.title("Roblox Gaming Launcher");self.root.geometry("1280x820");self.root.minsize(1050,700)
        self.running=True;self.loading=False;self.games=load(GAMES,[{"name":n,"place_id":p} for n,p in SEEDS]);self.history=load(HISTORY,[])
        self.selected=None;self.servers=[];self.cursor=None;self.samples=deque(maxlen=360);self.loss=deque(maxlen=360);self.spikes=0
        self.icmp=None;self.rbx_ping=None;self.rbx_server=None
        self.ui();threading.Thread(target=self.net_loop,daemon=True).start();threading.Thread(target=self.rbx_monitor,daemon=True).start();threading.Thread(target=self.catalog_startup,daemon=True).start()
        self.root.after(700,self.tick);self.root.protocol("WM_DELETE_WINDOW",self.close)
    def ui(self):
        s=ctk.CTkFrame(self.root,width=220,corner_radius=0);s.pack(side="left",fill="y");s.pack_propagate(False)
        ctk.CTkLabel(s,text="ROBLOX\nGAMING",font=("Segoe UI",26,"bold")).pack(pady=(32,2));ctk.CTkLabel(s,text="LOW-LATENCY LAUNCHER",font=("Segoe UI",10)).pack(pady=(0,25))
        for t,f in [("⌂  Home",self.home),("🎮  Games",self.games_page),("🖥  Servers",self.servers_page),("📡  Network",self.network_page),("📊  History",self.history_page),("⚙  Settings",self.settings_page)]:
            ctk.CTkButton(s,text=t,anchor="w",height=42,fg_color="transparent",hover_color="#26384d",command=f).pack(fill="x",padx=12,pady=3)
        self.side=ctk.CTkLabel(s,text="-- ms",font=("Segoe UI",22,"bold"));self.side.pack(pady=(35,0));self.side2=ctk.CTkLabel(s,text="Monitoring",text_color="#8b949e");self.side2.pack()
        self.body=ctk.CTkFrame(self.root,fg_color="#0d1117",corner_radius=0);self.body.pack(side="left",fill="both",expand=True);self.home()
    def clear(self):
        for x in self.body.winfo_children():x.destroy()
    def head(self,t,s=""):
        ctk.CTkLabel(self.body,text=t,font=("Segoe UI",30,"bold")).pack(anchor="w",padx=30,pady=(25,0))
        if s:ctk.CTkLabel(self.body,text=s,text_color="#8b949e").pack(anchor="w",padx=32,pady=(2,16))
    def card(self,p,t,v,s):
        f=ctk.CTkFrame(p,corner_radius=14,fg_color="#161b22");f.pack(side="left",fill="both",expand=True,padx=5)
        ctk.CTkLabel(f,text=t,text_color="#8b949e").pack(anchor="w",padx=15,pady=(12,0));ctk.CTkLabel(f,text=v,font=("Segoe UI",23,"bold")).pack(anchor="w",padx=15);ctk.CTkLabel(f,text=s,text_color="#6e7681").pack(anchor="w",padx=15,pady=(0,12))
    def home(self):
        self.clear();self.head("Gaming Dashboard","Roblox-specific ping is separate from normal internet ping.")
        r=ctk.CTkFrame(self.body,fg_color="transparent");r.pack(fill="x",padx=25)
        self.card(r,"INTERNET BASELINE",f"{self.icmp:.0f} ms" if self.icmp else "--","ICMP to 1.1.1.1 / 8.8.8.8")
        self.card(r,"ROBLOX NETWORK PING",f"{self.rbx_ping:.0f} ms" if self.rbx_ping else "--","Detected from Roblox client logs")
        self.card(r,"JITTER",self.jitter(),"30-sample rolling");self.card(r,"PACKET LOSS",self.loss_text(),"rolling window")
        h=ctk.CTkFrame(self.body,corner_radius=18,fg_color="#161b22");h.pack(fill="x",padx=30,pady=18)
        ctk.CTkLabel(h,text=self.selected["name"] if self.selected else "Choose a game",font=("Segoe UI",24,"bold")).pack(anchor="w",padx=22,pady=(18,0))
        ctk.CTkLabel(h,text=f"Place ID {self.selected['place_id']}" if self.selected else "Games → select a game").pack(anchor="w",padx=22)
        b=ctk.CTkFrame(h,fg_color="transparent");b.pack(fill="x",padx=16,pady=18)
        ctk.CTkButton(b,text="⚡ FIND BEST SERVER",height=44,command=self.best).pack(side="left",padx=5);ctk.CTkButton(b,text="🖥 BROWSE SERVERS",height=44,command=self.servers_page).pack(side="left",padx=5);ctk.CTkButton(b,text="▶ OPEN ROBLOX",height=44,fg_color="#238636",command=self.open_roblox).pack(side="left",padx=5)
        self.logbox=ctk.CTkTextbox(self.body,height=220);self.logbox.pack(fill="both",expand=True,padx=30,pady=(0,25));self.logbox.insert("end","Launcher ready. Continuous monitoring is active.\n")
    def games_page(self):
        self.clear();self.head("Game Library",f"{len(self.games)} saved • refresh Discover to import 100+ current games")
        top=ctk.CTkFrame(self.body,fg_color="transparent");top.pack(fill="x",padx=28)
        self.search=ctk.CTkEntry(top,placeholder_text="Search games...",height=40);self.search.pack(side="left",fill="x",expand=True,padx=(0,8));self.search.bind("<KeyRelease>",lambda e:self.render_games())
        ctk.CTkButton(top,text="↻ Refresh 100+",command=self.refresh_catalog).pack(side="right",padx=4);ctk.CTkButton(top,text="+ Add",command=self.add_game).pack(side="right",padx=4)
        self.gs=ctk.CTkScrollableFrame(self.body,fg_color="transparent");self.gs.pack(fill="both",expand=True,padx=24,pady=15);self.render_games()
    def render_games(self):
        if not hasattr(self,"gs"):return
        for w in self.gs.winfo_children():w.destroy()
        q=self.search.get().lower() if hasattr(self,"search") else ""
        for g in self.games:
            if q and q not in g["name"].lower():continue
            f=ctk.CTkFrame(self.gs,corner_radius=12,fg_color="#161b22");f.pack(fill="x",pady=4)
            ctk.CTkLabel(f,text=g["name"],font=("Segoe UI",16,"bold")).pack(side="left",padx=15,pady=12);ctk.CTkLabel(f,text=f"ID {g['place_id']}",text_color="#8b949e").pack(side="left")
            ctk.CTkButton(f,text="Select",width=80,command=lambda x=g:self.select(x)).pack(side="right",padx=6);ctk.CTkButton(f,text="Join",width=70,fg_color="#238636",command=lambda x=g:self.select_and_best(x)).pack(side="right",padx=2)
    def select(self,g):self.selected=g;self.home()
    def select_and_best(self,g):self.selected=g;self.best()
    def add_game(self):
        n=simpledialog.askstring("Add game","Game name:");p=simpledialog.askstring("Add game","Place ID:")
        if n and p and p.isdigit():self.games.append({"name":n,"place_id":p});save(GAMES,self.games);self.render_games()
    def catalog_startup(self):self.refresh_catalog(True)
    def refresh_catalog(self,silent=False):
        def work():
            try:
                r=requests.get("https://api.rolimons.com/games/v1/gamelist",timeout=20);r.raise_for_status();d=r.json();a=[]
                for pid,v in d.get("games",{}).items():
                    if isinstance(v,list) and len(v)>1 and str(pid).isdigit():a.append({"name":str(v[0]),"place_id":str(pid),"players":int(v[1] or 0)})
                a.sort(key=lambda x:x.get("players",0),reverse=True);old={g["place_id"]:g for g in self.games}
                for g in a[:150]:old.setdefault(g["place_id"],g)
                self.games=list(old.values());save(GAMES,self.games)
                if not silent:self.root.after(0,self.render_games)
                self.log(f"Catalog: {len(a)} games available; top 150 imported.")
            except Exception as e:
                if not silent:self.root.after(0,lambda:messagebox.showerror("Catalog error",str(e)))
        threading.Thread(target=work,daemon=True).start()
    def servers_page(self):
        self.clear();self.head("Server Browser","Real public-server data. No fake per-server ping.")
        top=ctk.CTkFrame(self.body,fg_color="transparent");top.pack(fill="x",padx=28);ctk.CTkLabel(top,text=self.selected["name"] if self.selected else "Choose a game",font=("Segoe UI",20,"bold")).pack(side="left")
        ctk.CTkButton(top,text="Find Servers",command=self.load_servers).pack(side="right",padx=4);ctk.CTkButton(top,text="Load More",command=self.load_servers).pack(side="right",padx=4)
        self.ss=ctk.CTkLabel(self.body,text="Select a game.",text_color="#8b949e");self.ss.pack(anchor="w",padx=30,pady=8)
        self.sf=ctk.CTkScrollableFrame(self.body,fg_color="transparent");self.sf.pack(fill="both",expand=True,padx=24)
        if self.selected:self.load_servers()
    def load_servers(self):
        if not self.selected or self.loading:return
        self.loading=True;self.ss.configure(text="Loading Roblox public servers...")
        def work():
            try:
                u=f"https://games.roblox.com/v1/games/{self.selected['place_id']}/servers/Public";q={"sortOrder":"Desc","limit":100}
                if self.cursor:q["cursor"]=self.cursor
                r=requests.get(u,params=q,timeout=15,headers={"User-Agent":"RobloxGamingLauncher/3.1"})
                if r.status_code!=200:raise RuntimeError(f"HTTP {r.status_code}: {r.text[:250]}")
                d=r.json();self.servers+=d.get("data",[]);self.cursor=d.get("nextPageCursor");self.root.after(0,self.render_servers)
            except Exception as e:self.root.after(0,lambda:messagebox.showerror("Server browser error",str(e)))
            finally:self.loading=False
        threading.Thread(target=work,daemon=True).start()
    def render_servers(self):
        for w in self.sf.winfo_children():w.destroy()
        if not self.servers:self.ss.configure(text="Roblox returned no public servers.");return
        self.ss.configure(text=f"{len(self.servers)} servers loaded")
        for s in sorted(self.servers,key=self.score,reverse=True):
            f=ctk.CTkFrame(self.sf,corner_radius=12,fg_color="#161b22");f.pack(fill="x",pady=4);p=s.get("playing","?");m=s.get("maxPlayers","?");sid=s.get("id","")
            ctk.CTkLabel(f,text=f"{p}/{m} players",width=120,font=("Segoe UI",15,"bold")).pack(side="left",padx=12,pady=12);ctk.CTkLabel(f,text=f"Score {self.score(s):.0f}",width=100).pack(side="left")
            ctk.CTkLabel(f,text=sid[:28]+"...",text_color="#8b949e").pack(side="left",fill="x",expand=True);ctk.CTkButton(f,text="JOIN",width=80,command=lambda x=s:self.launch(x)).pack(side="right",padx=8)
    def score(self,s):
        free=max(0,int(s.get("maxPlayers",0) or 0)-int(s.get("playing",0) or 0));base=max(0,100-min(self.icmp or 999,250)*.22);return base+min(free,15)*2
    def best(self):
        if not self.selected:return messagebox.showinfo("Choose a game","Select a game first.")
        def work():
            try:
                u=f"https://games.roblox.com/v1/games/{self.selected['place_id']}/servers/Public";r=requests.get(u,params={"sortOrder":"Desc","limit":100},timeout=15,headers={"User-Agent":"RobloxGamingLauncher/3.1"});r.raise_for_status();a=r.json().get("data",[])
                if not a:raise RuntimeError("Roblox returned no public servers.")
                self.root.after(0,lambda:self.launch(max(a,key=self.score)))
            except Exception as e:self.root.after(0,lambda:messagebox.showerror("Best server",str(e)))
        threading.Thread(target=work,daemon=True).start()
    def launch(self,s):
        try:os.startfile(f"roblox://placeId={self.selected['place_id']}&gameInstanceId={s['id']}");self.log("Joining selected public server...")
        except Exception as e:messagebox.showerror("Join failed",str(e))
    def open_roblox(self):os.startfile("roblox-player:")
    def network_page(self):
        self.clear();self.head("Live Network","25 ms to Cloudflare is not the same measurement as Roblox Network Ping.")
        r=ctk.CTkFrame(self.body,fg_color="transparent");r.pack(fill="x",padx=25);self.card(r,"ICMP BASELINE",f"{self.icmp:.0f} ms" if self.icmp else "--","1.1.1.1 / 8.8.8.8");self.card(r,"ROBLOX NETWORK PING",f"{self.rbx_ping:.0f} ms" if self.rbx_ping else "--","from Roblox logs when exposed");self.card(r,"SERVER ADDRESS",self.rbx_server or "--","from Roblox client log");self.card(r,"LOSS",self.loss_text(),"rolling")
        t=ctk.CTkTextbox(self.body);t.pack(fill="both",expand=True,padx=30,pady=20);t.insert("end","Roblox measures Network Ping to the actual game server. This launcher separately measures an internet baseline. A low baseline and high Roblox ping can happen because the routes to those destinations are different.\n\nThe client log is checked automatically. If the current Roblox build does not expose a readable NetworkPing value in logs, the field stays -- instead of showing a fake number.")
    def history_page(self):
        self.clear();self.head("History","Saved locally.");t=ctk.CTkTextbox(self.body);t.pack(fill="both",expand=True,padx=30,pady=20)
        for h in reversed(self.history[-100:]):t.insert("end",f"{h.get('time')} | {h.get('game')} | avg {h.get('avg')} | worst {h.get('worst')} | loss {h.get('loss')} | spikes {h.get('spikes')}\n")
    def settings_page(self):
        self.clear();self.head("Settings","Safe Windows optimization only.");f=ctk.CTkFrame(self.body,corner_radius=14);f.pack(fill="x",padx=30,pady=15)
        ctk.CTkButton(f,text="High Performance Power Plan",command=lambda:self.power("SCHEME_MIN")).pack(anchor="w",padx=20,pady=20);ctk.CTkButton(f,text="Restore Balanced Plan",command=lambda:self.power("SCHEME_BALANCED")).pack(anchor="w",padx=20,pady=(0,20))
    def power(self,x):subprocess.run(["powercfg","/setactive",x],capture_output=True);self.log("Power plan changed.")
    def ping(self,h):
        try:
            p=subprocess.run(["ping","-n","1","-w","800",h],capture_output=True,text=True,timeout=2);m=re.search(r"time[=<]\s*(\d+)\s*ms",p.stdout,re.I);return float(m.group(1)) if m else None
        except:return None
    def net_loop(self):
        hs=["1.1.1.1","8.8.8.8"];i=0
        while self.running:
            v=self.ping(hs[i%2]);i+=1
            if v is None:self.loss.append(1)
            else:
                self.loss.append(0);self.icmp=v;self.samples.append(v);a=statistics.mean(list(self.samples)[-30:])
                if v>max(100,a*2.5) and v-a>40:self.spikes+=1;self.log(f"PING SPIKE {v:.0f} ms")
            time.sleep(.5)
    def rbx_monitor(self):
        d=os.path.expandvars(r"%LOCALAPPDATA%\Roblox\logs")
        while self.running:
            try:
                fs=[os.path.join(d,x) for x in os.listdir(d) if x.lower().endswith(".log")]
                if fs:
                    p=max(fs,key=os.path.getmtime);txt=open(p,encoding="utf8",errors="ignore").read()[-800000:]
                    a=re.findall(r"Server Address[^0-9]*(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?",txt,re.I)
                    if a:self.rbx_server=a[-1][0]+((":"+a[-1][1]) if a[-1][1] else "")
                    vals=[]
                    for pat in [r"NetworkPing[^0-9]{0,50}(\d+(?:\.\d+)?)",r"Network Ping[^0-9]{0,50}(\d+(?:\.\d+)?)"]:vals+=re.findall(pat,txt,re.I)
                    if vals:self.rbx_ping=float(vals[-1])
            except:pass
            time.sleep(2)
    def jitter(self):
        x=list(self.samples)[-30:];return "--" if len(x)<2 else f"{statistics.mean(abs(x[i]-x[i-1]) for i in range(1,len(x))):.1f} ms"
    def loss_text(self):return f"{statistics.mean(self.loss)*100:.1f}%" if self.loss else "0%"
    def tick(self):
        if hasattr(self,"side"):self.side.configure(text=f"{self.icmp:.0f} ms" if self.icmp else "-- ms")
        if self.running:self.root.after(700,self.tick)
    def log(self,msg):
        if hasattr(self,"logbox"):self.logbox.insert("end",f"[{datetime.now():%H:%M:%S}] {msg}\n");self.logbox.see("end")
        print(msg)
    def close(self):
        self.running=False
        if self.samples:self.history.append({"time":datetime.now().strftime("%Y-%m-%d %H:%M"),"game":self.selected["name"] if self.selected else "No game","avg":f"{statistics.mean(self.samples):.0f} ms","worst":f"{max(self.samples):.0f} ms","loss":self.loss_text(),"spikes":self.spikes});save(HISTORY,self.history[-200:])
        save(GAMES,self.games);self.root.destroy()

if __name__=="__main__":App().root.mainloop()
