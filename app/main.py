import tkinter as tk
from tkinter import ttk, messagebox
import subprocess, threading, time, socket, statistics, os, re
from collections import deque
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

class RobloxGamingLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Roblox Gaming Launcher")
        self.root.geometry("1050x680")
        self.root.minsize(900, 600)
        self.running = True
        self.samples = deque(maxlen=240)
        self.spikes = deque(maxlen=100)
        self.last_ping = None
        self.last_loss = 0.0
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.refresh_system()

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        top = ttk.Frame(self.root, padding=14)
        top.pack(fill="x")
        ttk.Label(top, text="⚡ Roblox Gaming Launcher", font=("Segoe UI", 20, "bold")).pack(side="left")
        self.status = tk.StringVar(value="Live monitoring")
        ttk.Label(top, textvariable=self.status).pack(side="right")

        buttons = ttk.Frame(self.root, padding=(14, 0, 14, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="▶ Launch Roblox", command=self.launch_roblox).pack(side="left", padx=4)
        ttk.Button(buttons, text="⚡ Gaming Optimize", command=self.optimize).pack(side="left", padx=4)
        ttk.Button(buttons, text="↻ Reset Optimizer", command=self.reset_optimizer).pack(side="left", padx=4)
        ttk.Button(buttons, text="📊 20s Connection Test", command=self.run_test).pack(side="left", padx=4)

        metrics = ttk.Frame(self.root, padding=14)
        metrics.pack(fill="x")
        self.vars = {}
        cards = [
            ("Current Ping","ping"),("Average","avg"),("Jitter","jitter"),
            ("Packet Loss","loss"),("Spikes","spikes"),("Worst","worst"),
            ("CPU","cpu"),("RAM","ram"),("GPU","gpu")
        ]
        for i,(label,key) in enumerate(cards):
            f=ttk.LabelFrame(metrics,text=label,padding=10)
            f.grid(row=i//3,column=i%3,sticky="nsew",padx=5,pady=5)
            self.vars[key]=tk.StringVar(value="--")
            ttk.Label(f,textvariable=self.vars[key],font=("Segoe UI",16,"bold")).pack()
            metrics.columnconfigure(i%3,weight=1)

        gf=ttk.LabelFrame(self.root,text="Live network monitor",padding=10)
        gf.pack(fill="both",expand=True,padx=19,pady=5)
        self.canvas=tk.Canvas(gf,background="#111318",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)

        bf=ttk.Frame(self.root,padding=(19,0,19,12))
        bf.pack(fill="x")
        self.log=tk.Text(bf,height=7,state="disabled",font=("Consolas",9))
        self.log.pack(fill="x")
        self.log_msg("Continuous monitoring started.")

    def log_msg(self,msg):
        def add():
            self.log.configure(state="normal")
            self.log.insert("end",f"[{datetime.now():%H:%M:%S}] {msg}\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(0,add)

    def ping(self,host):
        try:
            p=subprocess.run(["ping","-n","1","-w","800",host],capture_output=True,text=True,timeout=2)
            m=re.search(r"(?:time[=<])\s*(\d+)\s*ms",p.stdout,re.I)
            return float(m.group(1)) if m else None
        except Exception:
            return None

    def monitor_loop(self):
        hosts=["1.1.1.1","8.8.8.8"]
        i=0
        while self.running:
            value=self.ping(hosts[i%len(hosts)])
            i+=1
            if value is None:
                self.last_loss=1.0
                self.root.after(0,lambda:self.vars["loss"].set("100%"))
            else:
                self.last_loss=0.0
                self.last_ping=value
                self.samples.append((time.time(),value))
                recent=[x[1] for x in list(self.samples)[-30:]]
                avg=statistics.mean(recent)
                jitter=(statistics.mean([abs(recent[j]-recent[j-1]) for j in range(1,len(recent))])
                        if len(recent)>1 else 0)
                if value>max(100,avg*2.5) and value-avg>40:
                    self.spikes.append((time.time(),value))
                    self.log_msg(f"PING SPIKE: {value:.0f} ms (average {avg:.0f} ms)")
                self.root.after(0,self.update_metrics,avg,jitter)
            self.root.after(0,self.draw_graph)
            time.sleep(0.5)

    def update_metrics(self,avg,jitter):
        vals=[x[1] for x in self.samples]
        self.vars["ping"].set("--" if self.last_ping is None else f"{self.last_ping:.0f} ms")
        self.vars["avg"].set(f"{avg:.0f} ms")
        self.vars["jitter"].set(f"{jitter:.1f} ms")
        self.vars["loss"].set(f"{self.last_loss*100:.1f}%")
        self.vars["spikes"].set(str(len(self.spikes)))
        self.vars["worst"].set("--" if not vals else f"{max(vals):.0f} ms")

    def draw_graph(self):
        c=self.canvas
        c.delete("all")
        w=max(c.winfo_width(),300); h=max(c.winfo_height(),180)
        vals=[v for _,v in self.samples]
        if not vals:
            c.create_text(w//2,h//2,text="Waiting for measurements...",fill="white")
            return
        maxv=max(max(vals),100)
        step=w/max(1,len(vals)-1)
        points=[]
        for i,v in enumerate(vals):
            points += [i*step,h-20-min(v,maxv)/maxv*(h-40)]
        if len(points)>=4:
            c.create_line(*points,fill="#58a6ff",width=2,smooth=True)
        c.create_text(8,8,anchor="nw",text=f"{len(vals)} samples • max scale {maxv:.0f} ms",fill="#b8c0cc")

    def refresh_system(self):
        if psutil:
            try:
                self.vars["cpu"].set(f"{psutil.cpu_percent(interval=None):.0f}%")
                self.vars["ram"].set(f"{psutil.virtual_memory().percent:.0f}%")
            except Exception:
                pass
        else:
            self.vars["cpu"].set("Install psutil")
            self.vars["ram"].set("Install psutil")
        self.vars["gpu"].set("N/A")
        if self.running:
            self.root.after(1500,self.refresh_system)

    def launch_roblox(self):
        self.log_msg("Opening Roblox...")
        try:
            os.startfile("roblox-player:")
        except Exception:
            try:
                subprocess.Popen(["explorer.exe","roblox-player:"])
            except Exception as e:
                messagebox.showerror("Roblox",str(e))

    def optimize(self):
        self.log_msg("Starting safe gaming optimization...")
        try:
            subprocess.run(["powercfg","/setactive","SCHEME_MIN"],capture_output=True)
            self.log_msg("High-performance power plan requested.")
        except Exception as e:
            self.log_msg(f"Power-plan change skipped: {e}")
        self.log_msg("Optimization finished. No registry/security-disabling tweaks were applied.")

    def reset_optimizer(self):
        try:
            subprocess.run(["powercfg","/setactive","SCHEME_BALANCED"],capture_output=True)
            self.log_msg("Restored Balanced power plan.")
        except Exception as e:
            self.log_msg(f"Reset skipped: {e}")

    def run_test(self):
        self.log_msg("Running 20-second test...")
        def worker():
            vals=[]
            for _ in range(20):
                v=self.ping("1.1.1.1")
                if v is not None: vals.append(v)
                time.sleep(1)
            if vals:
                self.log_msg(f"Test result: avg {statistics.mean(vals):.0f} ms, min {min(vals):.0f}, max {max(vals):.0f}, replies {len(vals)}/20")
            else:
                self.log_msg("Test result: no replies.")
        threading.Thread(target=worker,daemon=True).start()

    def close(self):
        self.running=False
        self.root.destroy()

if __name__=="__main__":
    root=tk.Tk()
    RobloxGamingLauncher(root)
    root.mainloop()
