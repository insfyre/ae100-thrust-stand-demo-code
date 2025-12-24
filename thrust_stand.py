#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# thrust_stand_demo.py

import os, csv, time, datetime, threading, queue, sys
import tkinter as tk
from tkinter import ttk, messagebox, font
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import nidaqmx
from nidaqmx.constants import TerminalConfiguration, AcquisitionType

class DAQApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NI USB-6009 Force Logger (Python)")

        # ---- make UI bigger ----
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=20)   # Larger Font
        root.option_add("*TButton.Padding", 8)
        root.option_add("*TButton.Font", default_font)
        root.option_add("*TLabel.Font", default_font)
        root.option_add("*TEntry.Font", default_font)

        # ---- state variables ----
        self.running = False
        self.recording = False
        self.reader_stop = False
        self.task = None
        self.csv_writer = None
        self.csv_file = None
        self.t0 = None

        self.tare_v = 0.0
        self.cal = 20.31 #Calibrated 11/2 from 100.0
        self.q = queue.Queue(maxsize=64)
        self.t_data, self.f_data = [], []

        # ---- Controls ----
        frm = ttk.Frame(root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(frm, text="Device/Chan").grid(row=0, column=0, sticky="w")
        self.e_chan = ttk.Entry(frm, width=12)
        self.e_chan.insert(0, "Dev1/ai0")
        self.e_chan.grid(row=0, column=1, padx=4)

        ttk.Label(frm, text="Terminal").grid(row=0, column=2, sticky="e")
        self.cmb_term = ttk.Combobox(frm, width=8, values=["DIFF","RSE"], state="readonly")
        self.cmb_term.set("DIFF")
        self.cmb_term.grid(row=0, column=3, padx=4)

        ttk.Label(frm, text="V Range").grid(row=0, column=4, sticky="e")
        self.e_vmin = ttk.Entry(frm, width=6); self.e_vmin.insert(0, "-10")
        self.e_vmax = ttk.Entry(frm, width=6); self.e_vmax.insert(0, "10")
        self.e_vmin.grid(row=0, column=5); self.e_vmax.grid(row=0, column=6, padx=(0,8))

        ttk.Label(frm, text="Fs [S/s]").grid(row=1, column=0, sticky="w")
        self.e_fs = ttk.Entry(frm, width=10); self.e_fs.insert(0, "1000")
        self.e_fs.grid(row=1, column=1, padx=4)

        ttk.Label(frm, text="Samples/read").grid(row=1, column=2, sticky="e")
        self.e_nper = ttk.Entry(frm, width=10); self.e_nper.insert(0, "100")
        self.e_nper.grid(row=1, column=3, padx=4)

        ttk.Label(frm, text="Calibration (N/V)").grid(row=1, column=4, sticky="e")
        self.e_cal = ttk.Entry(frm, width=10); self.e_cal.insert(0, str(self.cal))
        self.e_cal.grid(row=1, column=5)

        self.btn_apply = ttk.Button(frm, text="Apply", command=self.apply_params)
        self.btn_apply.grid(row=1, column=6, padx=(6,0))

        # --- X/Y Range ---
        ttk.Label(frm, text="X Min [s]").grid(row=2, column=0, sticky="e")
        self.e_xmin = ttk.Entry(frm, width=8); self.e_xmin.insert(0, "0")
        self.e_xmin.grid(row=2, column=1)
        
        ttk.Label(frm, text="X Max [s]").grid(row=2, column=2, sticky="e")
        self.e_xmax = ttk.Entry(frm, width=8); self.e_xmax.insert(0, "100")
        self.e_xmax.grid(row=2, column=3)

        self.btn_applyx = ttk.Button(frm, text="Apply X Range", command=self.apply_xrange)
        self.btn_applyx.grid(row=2, column=4, padx=(6,0))

        ttk.Label(frm, text="Y Min").grid(row=2, column=5, sticky="e")
        self.e_ymin = ttk.Entry(frm, width=8); self.e_ymin.insert(0, "-1")
        self.e_ymin.grid(row=2, column=6)

        ttk.Label(frm, text="Y Max").grid(row=2, column=7, sticky="e")
        self.e_ymax = ttk.Entry(frm, width=8); self.e_ymax.insert(0, "40")
        self.e_ymax.grid(row=2, column=8)

        self.btn_applyy = ttk.Button(frm, text="Apply Y Range", command=self.apply_yrange)
        self.btn_applyy.grid(row=2, column=9, padx=(6,0))

        # --- Start/Stop/Tare/Record ---
        self.btn_start = ttk.Button(frm, text="Start", command=self.start)
        self.btn_start.grid(row=3, column=0, pady=6, sticky="ew")
        self.btn_stop  = ttk.Button(frm, text="Stop", command=self.stop, state="disabled")
        self.btn_stop.grid(row=3, column=1, sticky="ew")
        self.btn_tare  = ttk.Button(frm, text="Tare (Zero)", command=self.do_tare, state="disabled")
        self.btn_tare.grid(row=3, column=2, sticky="ew")
        self.btn_rec   = ttk.Button(frm, text="Record: OFF", command=self.toggle_record, state="disabled")
        self.btn_rec.grid(row=3, column=3, sticky="ew")

        ttk.Label(frm, text="CSV:").grid(row=3, column=4, sticky="e")
        self.lbl_csv = ttk.Label(frm, text="(not recording)")
        self.lbl_csv.grid(row=3, column=5, columnspan=4, sticky="w")

        # ---- Plot ----
        self.fig, self.ax = plt.subplots(figsize=(10,5))
        self.fig.tight_layout()
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("Force [N]")
        self.line, = self.ax.plot([], [], lw=1)
        plt.grid(which='minor',linestyle=':',linewidth='0.5',color='gray')
        plt.grid(which='major',linestyle='-',linewidth='0.8',color='gray')
        plt.minorticks_on()

        canvas = FigureCanvasTkAgg(self.fig, master=root)
        canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        canvas.draw()
        toolbarFrame = ttk.Frame(master=root)
        toolbarFrame.grid(row=4, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(canvas,toolbarFrame)
        toolbar.update()
        self.canvas = canvas

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(80, self.update_plot)

    # ---- Handlers ----
    def apply_params(self):
        try:
            self.cal = float(self.e_cal.get())
            float(self.e_fs.get()); int(self.e_nper.get())
            float(self.e_vmin.get()); float(self.e_vmax.get())
            if self.running:
                messagebox.showinfo("Info", "Stop before applying new parameters.")
        except Exception as e:
            messagebox.showerror("Param error", str(e))

    def apply_xrange(self):
        try:
            xmin = float(self.e_xmin.get())
            xmax = float(self.e_xmax.get())
            if xmin >= xmax: raise ValueError("X Min must be < X Max")
            self.ax.set_xlim(xmin, xmax)
            self.canvas.draw_idle()
        except Exception as e:
            messagebox.showerror("X Range error", str(e))

    def apply_yrange(self):
        try:
            ymin = float(self.e_ymin.get())
            ymax = float(self.e_ymax.get())
            if ymin >= ymax: raise ValueError("Y Min must be < Y Max")
            self.ax.set_ylim(ymin, ymax)
            self.canvas.draw_idle()
        except Exception as e:
            messagebox.showerror("Y Range error", str(e))

    def start(self):
        # Starts reading data from DAQ. Button action
        if self.running: return
        try:
            chan = self.e_chan.get().strip()
            fs   = float(self.e_fs.get())
            nper = int(self.e_nper.get())
            vmin = float(self.e_vmin.get())
            vmax = float(self.e_vmax.get())
            term = TerminalConfiguration.DIFF if self.cmb_term.get()=="DIFF" else TerminalConfiguration.RSE
        except Exception as e:
            messagebox.showerror("Param error", str(e)); return

        self.running = True
        self.recording = False
        self.reader_stop = False
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_tare.config(state="normal")
        self.btn_rec.config(state="normal", text="Record: OFF")
        self.lbl_csv.config(text="(not recording)")

        self.t_data.clear(); self.f_data.clear()
        self.t0 = time.time()
        self.tare_v = 0.0

        self.task = nidaqmx.Task()
        self.task.ai_channels.add_ai_voltage_chan(
            chan, min_val=vmin, max_val=vmax, terminal_config=term
        )
        self.task.timing.cfg_samp_clk_timing(rate=fs, sample_mode=AcquisitionType.CONTINUOUS)

        self.reader = threading.Thread(target=self._reader_loop, args=(nper, fs), daemon=True)
        self.reader.start()

    def stop(self):
        # Stops reading data from DAQ. Button action
        self.recording = False
        self.btn_rec.config(text="Record: OFF")
        if self.csv_file:
            try: self.csv_file.close()
            except: pass
            self.csv_writer = None; self.csv_file = None
        self.lbl_csv.config(text="(not recording)")

        self.reader_stop = True
        if self.task:
            try: self.task.close()
            except: pass
            self.task = None

        self.running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_tare.config(state="disabled")
        self.btn_rec.config(state="disabled")

    def do_tare(self):
        if not self.f_data:
            self.tare_v = 0.0
            return
        window = self.f_data[-50:] if len(self.f_data)>=50 else self.f_data
        mean_force = sum(window)/len(window)
        self.tare_v += (mean_force/self.cal)

    def toggle_record(self):
        if not self.running: return
        self.recording = not self.recording
        if self.recording:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"daq_{ts}.csv"
            self.csv_file = open(fname, "w", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["t_sec","voltage_V","force_N"])
            self.lbl_csv.config(text=os.path.abspath(fname))
            self.btn_rec.config(text="Record: ON")
        else:
            if self.csv_file:
                try: self.csv_file.close()
                except: pass
            self.csv_writer = None; self.csv_file = None
            self.lbl_csv.config(text="(not recording)")
            self.btn_rec.config(text="Record: OFF")

    # ---- Reader ----
    def _reader_loop(self, nper, fs):
        try:
            while not self.reader_stop:
                vals = self.task.read(number_of_samples_per_channel=nper)
                t_now = time.time()-self.t0
                v_mean = sum(vals)/len(vals) if vals else 0.0
                try: self.q.put_nowait((t_now, v_mean))
                except queue.Full: pass
                time.sleep(max(0.0, nper/fs*0.05))
        except Exception as e:
            try: self.q.put(("__error__", str(e)))
            except: pass

    # ---- Updater ----
    def update_plot(self):
        while True:
            try: item = self.q.get_nowait()
            except queue.Empty: break

            if item[0]=="__error__":
                messagebox.showerror("DAQ error", item[1])
                self.stop()
                break
            t,v = item
            force = (v - self.tare_v)*self.cal
            self.t_data.append(t); self.f_data.append(force)
            if self.recording and self.csv_writer:
                self.csv_writer.writerow([f"{t:.6f}", f"{v:.6f}", f"{force:.6f}"])

        if self.t_data:
            self.line.set_data(self.t_data, self.f_data)
            self.ax.relim(); self.ax.autoscale_view(scalex=True, scaley=False)
            self.canvas.draw_idle()

        self.root.after(80, self.update_plot)

    def on_close(self):
        # kills program on window close
        try: self.stop()
        except: pass
        self.root.destroy()
        sys.exit()

if __name__=="__main__":
    root = tk.Tk()
    app = DAQApp(root)
    root.mainloop()

