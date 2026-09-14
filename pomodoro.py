import tkinter as tk
from tkinter import font as tkfont
import time
import threading


class PomodoroTimer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pomodoro")
        self.root.overrideredirect(True)  # Remove decorations (frameless)
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", 0.7)  # 70% opacity (semi-transparent)
        self.root.configure(bg="#2d2d2d")  # Soft dark background

        # Window size and position (center-top of screen)
        w, h = 140, 50
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = 40
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Enable dragging
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)

        # Mouse hover events for opacity and color change
        self.root.bind("<Enter>", self.on_enter)
        self.root.bind("<Leave>", self.on_leave)

        # Timer label
        self.remaining = 25 * 60  # 25 minutes in seconds
        self.running = False

        self.label = tk.Label(
            self.root,
            text=self.format_time(self.remaining),
            bg="#2d2d2d",
            fg="#aaaaaa",
            font=tkfont.Font(family="Consolas", size=18, weight="bold"),
        )
        self.label.pack(expand=True, fill="both")

        # Click to start/pause, right-click to reset
        self.label.bind("<Button-1>", self.toggle_timer)
        self.label.bind("<Button-3>", self.reset_timer)

        # Idle (original) colors
        self.idle_bg = "#2d2d2d"
        self.idle_fg = "#aaaaaa"
        # Hover (active) colors
        self.hover_bg = "#00c853"
        self.hover_fg = "#ffffff"

        self.start_move_data = None
        self.alert_active = False

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def toggle_timer(self, event=None):
        if self.running:
            self.running = False
        else:
            self.running = True
            self.countdown()

    def reset_timer(self, event=None):
        self.running = False
        self.stop_alert()  # Stop animation if active
        self.remaining = 25 * 60
        self.label.config(text=self.format_time(self.remaining),
                          bg=self.idle_bg, fg=self.idle_fg)

    def countdown(self):
        if self.running and self.remaining > 0:
            self.label.config(text=self.format_time(self.remaining))
            self.remaining -= 1
            self.root.after(1000, self.countdown)
        elif self.remaining == 0:
            self.label.config(text="00:00")
            self.running = False
            self.start_alert()  # Trigger alert animation

    # --- Alert animation when timer ends ---
    def start_alert(self):
        self.alert_active = True
        self.flash_step = 0
        self.flash()      # Start flashing colors
        self.shake()      # Start window shake

    def flash(self):
        """Alternates label between red and dark, creating a blinking effect."""
        if not self.alert_active:
            return
        colors = [("#ff1744", "#ffffff"), ("#2d2d2d", "#aaaaaa")]
        bg, fg = colors[self.flash_step % 2]
        self.label.config(text="TIME'S UP!", bg=bg, fg=fg)
        self.flash_step += 1
        self.root.after(500, self.flash)  # Blink every 500ms

    def shake(self):
        """Moves the window left-right rapidly for a shake effect."""
        if not self.alert_active:
            return
        base_x = self.root.winfo_x()
        base_y = self.root.winfo_y()
        offsets = [6, -6, 4, -4, 2, -2, 0]
        self.shake_offsets = offsets
        self.shake_index = 0
        self._do_shake_step(base_x, base_y)

    def _do_shake_step(self, base_x, base_y):
        if not self.alert_active or self.shake_index >= len(self.shake_offsets):
            self.root.geometry(f"+{base_x}+{base_y}")
            return
        dx = self.shake_offsets[self.shake_index]
        self.root.geometry(f"+{base_x + dx}+{base_y}")
        self.shake_index += 1
        self.root.after(50, self._do_shake_step, base_x, base_y)

    def stop_alert(self):
        """Stops the alert animation and resets colors."""
        self.alert_active = False
        self.label.config(text=self.format_time(self.remaining),
                          bg=self.idle_bg, fg=self.idle_fg)

    # --- Dragging ---
    def start_move(self, event):
        self.start_move_data = (event.x, event.y)

    def do_move(self, event):
        if self.start_move_data:
            dx = event.x - self.start_move_data[0]
            dy = event.y - self.start_move_data[1]
            x = self.root.winfo_x() + dx
            y = self.root.winfo_y() + dy
            self.root.geometry(f"+{x}+{y}")

    def stop_move(self, event):
        self.start_move_data = None

    # --- Hover effects ---
    def on_enter(self, event):
        self.root.attributes("-alpha", 1.0)  # 100% opacity on hover
        if not self.alert_active:
            self.label.config(bg=self.hover_bg, fg=self.hover_fg)

    def on_leave(self, event):
        self.root.attributes("-alpha", 0.7)  # Back to 70% opacity
        if not self.alert_active:
            self.label.config(bg=self.idle_bg, fg=self.idle_fg)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PomodoroTimer()
    app.run()
