



# import tkinter as tk
# from threading import Thread
# from PIL import Image, ImageTk, ImageDraw
# import os

# class JaguarOverlay:
#     def __init__(self):
#         self.root = None
#         self.status_label = None
#         self.canvas = None
#         self.logo_img = None

#         # Animation
#         self.ring = None
#         self.ring_radius = 40
#         self.pulse_direction = 1
#         self.is_listening = False

#         # Drag
#         self.offset_x = 0
#         self.offset_y = 0

#         self.status = "Idle"

#         self.status_colors = {
#             "Idle": "#2c3e50",
#             "Listening...": "#27ae60",
#             "Processing...": "#e67e22",
#             "Awaiting confirmation...": "#f1c40f",
#             "Offline": "#c0392b",
#         }

#     # -------------------------------
#     # 🟢 Circle Image Creator
#     # -------------------------------
#     def create_circle_image(self, path, size=(70, 70)):
#         img = Image.open(path).resize(size).convert("RGBA")

#         mask = Image.new("L", size, 0)
#         draw = ImageDraw.Draw(mask)
#         draw.ellipse((0, 0, size[0], size[1]), fill=255)

#         img.putalpha(mask)
#         return ImageTk.PhotoImage(img)

#     # -------------------------------
#     # 🟢 UI Setup
#     # -------------------------------
#     def create_overlay(self):
#         self.root = tk.Tk()
#         self.root.overrideredirect(True)
#         self.root.attributes("-topmost", True)
#         self.root.attributes("-alpha", 0.95)

#         width, height = 200, 220

#         screen_width = self.root.winfo_screenwidth()
#         x = screen_width - width - 30
#         y = 80

#         self.root.geometry(f"{width}x{height}+{x}+{y}")
#         self.root.configure(bg="#121212")

#         frame = tk.Frame(self.root, bg="#121212")
#         frame.pack(expand=True, fill="both")

#         # -------------------------------
#         # 🎨 CANVAS (Logo + Animation)
#         # -------------------------------
#         self.canvas = tk.Canvas(
#             frame,
#             width=120,
#             height=120,
#             bg="#121212",
#             highlightthickness=0
#         )
#         self.canvas.pack(pady=(10, 5))

#         logo_path = "static/icon.png"

#         if os.path.exists(logo_path):
#             self.logo_img = self.create_circle_image(logo_path, (70, 70))
#             self.canvas.create_image(60, 60, image=self.logo_img)
#         else:
#             self.canvas.create_text(
#                 60, 60,
#                 text="🐆",
#                 font=("Segoe UI", 28),
#                 fill="#20e6d7"
#             )

#         # Glow ring
#         self.ring = self.canvas.create_oval(
#             20, 20, 100, 100,
#             outline="#20e6d7",
#             width=2,
#             state="hidden"
#         )

#         # -------------------------------
#         # 🏷️ TITLE
#         # -------------------------------
#         tk.Label(
#             frame,
#             text="Jaguar AI",
#             font=("Orbitron", 12, "bold"),
#             fg="#20e6d7",
#             bg="#121212"
#         ).pack(pady=(0, 10))

#         # -------------------------------
#         # 📊 STATUS
#         # -------------------------------
#         self.status_label = tk.Label(
#             frame,
#             text="● Idle",
#             font=("Segoe UI", 10, "bold"),
#             fg="white",
#             bg=self.status_colors["Idle"],
#             padx=10,
#             pady=5
#         )
#         self.status_label.pack(pady=(5, 15))

#         # -------------------------------
#         # 🖱️ DRAG SUPPORT
#         # -------------------------------
#         self.root.bind("<Button-1>", self.start_drag)
#         self.root.bind("<B1-Motion>", self.do_drag)

#         # -------------------------------
#         # 🖱️ CLICK ACTIONS
#         # -------------------------------
#         self.root.bind("<Button-3>", self.close_app)  # Right click
#         self.root.bind("<Double-Button-1>", self.toggle_status)  # Double click

#     # -------------------------------
#     # 🟢 Animation
#     # -------------------------------
#     def animate_ring(self):
#         if not self.is_listening:
#             return

#         self.ring_radius += self.pulse_direction * 2

#         if self.ring_radius > 50 or self.ring_radius < 35:
#             self.pulse_direction *= -1

#         x0 = 60 - self.ring_radius
#         y0 = 60 - self.ring_radius
#         x1 = 60 + self.ring_radius
#         y1 = 60 + self.ring_radius

#         self.canvas.coords(self.ring, x0, y0, x1, y1)

#         # Glow color variation
#         intensity = int(150 + (self.ring_radius - 35) * 5)
#         intensity = max(0, min(255, intensity))
#         color = f"#20e6{intensity:02x}"

#         self.canvas.itemconfig(self.ring, outline=color)

#         self.root.after(50, self.animate_ring)

#     # -------------------------------
#     # 🟢 Update Status
#     # -------------------------------
#     def update_status(self, status):
#         self.status = status

#         if not self.status_label:
#             return

#         color = self.status_colors.get(status, "#2c3e50")
#         self.status_label.config(text=f"● {status}", bg=color)

#         if status == "Listening...":
#             self.is_listening = True
#             self.canvas.itemconfig(self.ring, state="normal")
#             self.animate_ring()
#         else:
#             self.is_listening = False
#             self.canvas.itemconfig(self.ring, state="hidden")

#     # -------------------------------
#     # 🟢 Drag Functions
#     # -------------------------------
#     def start_drag(self, event):
#         self.offset_x = event.x
#         self.offset_y = event.y

#     def do_drag(self, event):
#         x = self.root.winfo_x() + event.x - self.offset_x
#         y = self.root.winfo_y() + event.y - self.offset_y
#         self.root.geometry(f"+{x}+{y}")

#     # -------------------------------
#     # 🟢 Click Actions
#     # -------------------------------
#     def toggle_status(self, event=None):
#         if self.status == "Idle":
#             self.update_status("Listening...")
#         else:
#             self.update_status("Idle")

#     def close_app(self, event=None):
#         self.root.destroy()

#     # -------------------------------
#     def run(self):
#         self.create_overlay()
#         self.root.mainloop()


# # -------------------------------
# # 🔁 Singleton + Thread
# # -------------------------------
# overlay_instance = JaguarOverlay()

# def start_overlay():
#     t = Thread(target=overlay_instance.run, daemon=True)
#     t.start()

# def update_overlay(status):
#     overlay_instance.update_status(status)


# # -------------------------------
# # 🚀 RUN (for testing)
# # -------------------------------
# if __name__ == "__main__":
#     start_overlay()

#     import time
#     time.sleep(2)
#     update_overlay("Listening...")


























import tkinter as tk
from threading import Thread
from PIL import Image, ImageTk, ImageDraw
import os
import queue
import queue


class JaguarOverlay:

    def __init__(self, start_callback=None, stop_callback=None):
        self.root = None

        # UI
        self.frame = None
        self.canvas = None
        self.status_label = None
        self.logo_img = None

        # Animation
        self.ring = None
        self.ring_radius = 40
        self.pulse_direction = 1
        self.is_listening = False

        # State
        self.status = "Idle"
        self.expanded = False
        self.running = False

        # Drag
        self.offset_x = 0
        self.offset_y = 0

        # Thread-safe UI updates
        self.update_queue = queue.Queue()

        # Callbacks
        self.start_callback = start_callback
        self.stop_callback = stop_callback

        # Status colors
        self.status_colors = {
            "Idle": "#263238",
            "Listening...": "#087f5b",
            "Processing...": "#b85c00",
            "Awaiting confirmation...": "#a47f00",
            "Offline": "#9b2c2c",
        }

    # ==========================================================
    # CREATE CIRCULAR IMAGE
    # ==========================================================

    def create_circle_image(self, path, size=(76, 76)):

        img = Image.open(path).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)

        mask = Image.new("L", size, 0)

        draw = ImageDraw.Draw(mask)
        draw.ellipse(
            (0, 0, size[0] - 1, size[1] - 1),
            fill=255
        )

        img.putalpha(mask)

        return ImageTk.PhotoImage(img)

    # ==========================================================
    # CREATE OVERLAY
    # ==========================================================

    def create_overlay(self):

        self.root = tk.Tk()

        # Remove title bar
        self.root.overrideredirect(True)

        # Always on top
        self.root.attributes("-topmost", True)

        # Transparency
        self.root.attributes("-alpha", 0.96)

        # Initial size
        self.set_window_size()

        # Background
        self.root.configure(bg="#101820")

        # Main frame
        self.frame = tk.Frame(
            self.root,
            bg="#101820"
        )

        self.frame.pack(
            fill="both",
            expand=True
        )

        # Build square UI
        self.build_square_ui()

        # Mouse controls
        self.root.bind(
            "<Button-1>",
            self.start_drag
        )

        self.root.bind(
            "<B1-Motion>",
            self.do_drag
        )

        self.root.bind(
            "<ButtonRelease-1>",
            self.on_click
        )

        # Right click = close
        self.root.bind(
            "<Button-3>",
            self.close_app
        )

        # Process external status updates
        self.process_queue()

    # ==========================================================
    # WINDOW SIZE
    # ==========================================================

    def set_window_size(self):

        if self.expanded:

            width = 500
            height = 100

        else:

            width = 210
            height = 225

        screen_width = self.root.winfo_screenwidth()

        # Keep current position if possible
        try:
            x = self.root.winfo_x()
            y = self.root.winfo_y()

            if x <= 0:
                x = screen_width - width - 30

        except Exception:

            x = screen_width - width - 30
            y = 80

        self.root.geometry(
            f"{width}x{height}+{x}+{y}"
        )

    # ==========================================================
    # SQUARE UI
    # ==========================================================

    def build_square_ui(self):

        self.clear_frame()

        self.canvas = tk.Canvas(
            self.frame,
            width=130,
            height=130,
            bg="#101820",
            highlightthickness=0
        )

        self.canvas.pack(
            pady=(8, 0)
        )

        # ------------------------------------------------------
        # LOGO
        # ------------------------------------------------------

        logo_path = "jaguar_logo.png"

        if os.path.exists(logo_path):

            self.logo_img = self.create_circle_image(
                logo_path,
                (76, 76)
            )

            self.canvas.create_image(
                65,
                65,
                image=self.logo_img
            )

        else:

            self.canvas.create_text(
                65,
                65,
                text="🐆",
                font=("Segoe UI", 32),
                fill="#20e6d7"
            )

        # ------------------------------------------------------
        # GLOW RING
        # ------------------------------------------------------

        self.ring = self.canvas.create_oval(
            25,
            25,
            105,
            105,
            outline="#20e6d7",
            width=2,
            state="hidden"
        )

        # ------------------------------------------------------
        # TITLE
        # ------------------------------------------------------

        title = tk.Label(
            self.frame,
            text="JAGUAR AI",
            font=("Segoe UI", 11, "bold"),
            fg="#20e6d7",
            bg="#101820"
        )

        title.pack(
            pady=(0, 7)
        )

        # ------------------------------------------------------
        # STATUS
        # ------------------------------------------------------

        self.status_label = tk.Label(
            self.frame,
            text=f"● {self.status}",
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg=self.status_colors.get(
                self.status,
                "#263238"
            ),
            padx=15,
            pady=5
        )

        self.status_label.pack()

        # ------------------------------------------------------
        # HINT
        # ------------------------------------------------------

        hint = tk.Label(
            self.frame,
            text="Click to control",
            font=("Segoe UI", 7),
            fg="#78909c",
            bg="#101820"
        )

        hint.pack(
            pady=(6, 0)
        )

        # Restore listening animation
        if self.is_listening:

            self.canvas.itemconfig(
                self.ring,
                state="normal"
            )

            self.animate_ring()

    # ==========================================================
    # EXPANDED CONTROL BAR
    # ==========================================================

    def build_control_bar(self):

        self.clear_frame()

        self.root.configure(
            bg="#101820"
        )

        # ------------------------------------------------------
        # LEFT LOGO
        # ------------------------------------------------------

        logo_frame = tk.Frame(
            self.frame,
            bg="#101820"
        )

        logo_frame.pack(
            side="left",
            padx=(12, 8)
        )

        logo_path = "static/icon.png"

        if os.path.exists(logo_path):

            self.logo_img = self.create_circle_image(
                logo_path,
                (60, 60)
            )

            logo = tk.Label(
                logo_frame,
                image=self.logo_img,
                bg="#101820"
            )

        else:

            logo = tk.Label(
                logo_frame,
                text="🐆",
                font=("Segoe UI", 28),
                fg="#20e6d7",
                bg="#101820"
            )

        logo.pack()

        # ------------------------------------------------------
        # JAGUAR INFO
        # ------------------------------------------------------

        info = tk.Frame(
            self.frame,
            bg="#101820"
        )

        info.pack(
            side="left",
            padx=5
        )

        tk.Label(
            info,
            text="JAGUAR AI",
            font=("Segoe UI", 11, "bold"),
            fg="#20e6d7",
            bg="#101820"
        ).pack(
            anchor="w"
        )

        self.status_label = tk.Label(
            info,
            text=f"● {self.status}",
            font=("Segoe UI", 8, "bold"),
            fg="white",
            bg=self.status_colors.get(
                self.status,
                "#263238"
            ),
            padx=10,
            pady=4
        )

        self.status_label.pack(
            anchor="w",
            pady=(5, 0)
        )

        # ------------------------------------------------------
        # CONTROL BUTTONS
        # ------------------------------------------------------

        controls = tk.Frame(
            self.frame,
            bg="#101820"
        )

        controls.pack(
            side="left",
            padx=15
        )

        # START
        self.start_button = tk.Button(
            controls,
            text="▶  START",
            command=self.start_jaguar,
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg="#087f5b",
            activebackground="#099268",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2"
        )

        self.start_button.grid(
            row=0,
            column=0,
            padx=4
        )

        # STOP
        self.stop_button = tk.Button(
            controls,
            text="■  STOP",
            command=self.stop_jaguar,
            font=("Segoe UI", 9, "bold"),
            fg="white",
            bg="#9b2c2c",
            activebackground="#c0392b",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            cursor="hand2"
        )

        self.stop_button.grid(
            row=0,
            column=1,
            padx=4
        )

        # COLLAPSE
        self.collapse_button = tk.Button(
            controls,
            text="−",
            command=self.collapse,
            font=("Segoe UI", 13, "bold"),
            fg="#20e6d7",
            bg="#18242c",
            activebackground="#22333d",
            activeforeground="#20e6d7",
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2"
        )

        self.collapse_button.grid(
            row=0,
            column=2,
            padx=(8, 0)
        )

    # ==========================================================
    # CLEAR FRAME
    # ==========================================================

    def clear_frame(self):

        for widget in self.frame.winfo_children():
            widget.destroy()

        self.canvas = None
        self.status_label = None
        self.ring = None

    # ==========================================================
    # EXPAND
    # ==========================================================

    def expand(self):

        if self.expanded:
            return

        self.expanded = True

        self.set_window_size()

        self.build_control_bar()

    # ==========================================================
    # COLLAPSE
    # ==========================================================

    def collapse(self):

        if not self.expanded:
            return

        self.expanded = False

        self.set_window_size()

        self.build_square_ui()

    # ==========================================================
    # START JAGUAR
    # ==========================================================

    def start_jaguar(self):

        if self.running:
            return

        self.running = True

        self.update_status_internal(
            "Listening..."
        )

        print("Jaguar AI STARTED")

        # Call your real Jaguar start function
        if self.start_callback:

            try:
                self.start_callback()

            except Exception as e:

                print(
                    "Start callback error:",
                    e
                )

    # ==========================================================
    # STOP JAGUAR
    # ==========================================================

    def stop_jaguar(self):

        if not self.running:
            return

        self.running = False

        self.update_status_internal(
            "Idle"
        )

        print("Jaguar AI STOPPED")

        # Call your real Jaguar stop function
        if self.stop_callback:

            try:
                self.stop_callback()

            except Exception as e:

                print(
                    "Stop callback error:",
                    e
                )

    # ==========================================================
    # STATUS UPDATE
    # ==========================================================

    def update_status_internal(self, status):

        self.status = status

        if not self.status_label:
            return

        color = self.status_colors.get(
            status,
            "#263238"
        )

        self.status_label.config(
            text=f"● {status}",
            bg=color
        )

        # Listening animation
        if status == "Listening...":

            self.is_listening = True

            if self.canvas and self.ring:

                self.canvas.itemconfig(
                    self.ring,
                    state="normal"
                )

                self.animate_ring()

        else:

            self.is_listening = False

            if self.canvas and self.ring:

                self.canvas.itemconfig(
                    self.ring,
                    state="hidden"
                )

    # ==========================================================
    # PUBLIC STATUS UPDATE
    # ==========================================================

    def update_status(self, status):

        # Put update into queue
        self.update_queue.put(
            ("status", status)
        )

    # ==========================================================
    # QUEUE PROCESSOR
    # ==========================================================

    def process_queue(self):

        try:

            while True:

                action, value = (
                    self.update_queue.get_nowait()
                )

                if action == "status":

                    self.update_status_internal(
                        value
                    )

        except queue.Empty:
            pass

        if self.root:

            self.root.after(
                50,
                self.process_queue
            )

    # ==========================================================
    # GLOWING RING
    # ==========================================================

    def animate_ring(self):

        if not self.is_listening:
            return

        if not self.canvas or not self.ring:
            return

        self.ring_radius += (
            self.pulse_direction * 1.5
        )

        if self.ring_radius >= 50:

            self.ring_radius = 50
            self.pulse_direction = -1

        elif self.ring_radius <= 36:

            self.ring_radius = 36
            self.pulse_direction = 1

        center = 65

        x0 = center - self.ring_radius
        y0 = center - self.ring_radius
        x1 = center + self.ring_radius
        y1 = center + self.ring_radius

        self.canvas.coords(
            self.ring,
            x0,
            y0,
            x1,
            y1
        )

        self.canvas.itemconfig(
            self.ring,
            outline="#20e6d7"
        )

        self.root.after(
            45,
            self.animate_ring
        )

    # ==========================================================
    # DRAG
    # ==========================================================

    def start_drag(self, event):

        self.offset_x = event.x
        self.offset_y = event.y

        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root

    def do_drag(self, event):

        x = (
            self.root.winfo_x()
            + event.x_root
            - self.drag_start_x
        )

        y = (
            self.root.winfo_y()
            + event.y_root
            - self.drag_start_y
        )

        self.root.geometry(
            f"+{x}+{y}"
        )

        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root

    # ==========================================================
    # CLICK
    # ==========================================================

    def on_click(self, event):

        # Don't expand when clicking buttons
        widget = event.widget

        if isinstance(widget, tk.Button):
            return

        if not self.expanded:

            self.expand()

    # ==========================================================
    # CLOSE
    # ==========================================================

    def close_app(self, event=None):

        if self.running:

            self.stop_jaguar()

        if self.root:

            self.root.destroy()

    # ==========================================================
    # RUN
    # ==========================================================

    def run(self):

        self.create_overlay()

        self.root.mainloop()


# ==============================================================
# YOUR JAGUAR FUNCTIONS
# ==============================================================

def start_jaguar_voice():
    import state
    listener = state.get_listener()
    if listener:
        print(">>> Overlay: Requesting Voice system start...")
        listener.start_listening()
    else:
        print(">>> Overlay Error: Listener not found in state")

def stop_jaguar_voice():
    import state
    listener = state.get_listener()
    if listener:
        print(">>> Overlay: Requesting Voice system stop...")
        listener.stop_listening()
    else:
        print(">>> Overlay Error: Listener not found in state")


# ==============================================================
# CREATE OVERLAY
# ==============================================================

overlay_instance = JaguarOverlay(
    start_callback=start_jaguar_voice,
    stop_callback=stop_jaguar_voice
)


# ==============================================================
# START OVERLAY
# ==============================================================

def start_overlay():

    thread = Thread(
        target=overlay_instance.run,
        daemon=True
    )

    thread.start()


# ==============================================================
# UPDATE OVERLAY FROM JAGUAR
# ==============================================================

def update_overlay(status):

    overlay_instance.update_status(
        status
    )


# ==============================================================
# TEST
# ==============================================================

if __name__ == "__main__":

    start_overlay()

    import time

    time.sleep(2)

    update_overlay(
        "Idle"
    )
