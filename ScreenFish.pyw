"""Screen Fish: a small, click-through Windows desktop aquarium."""
import ctypes
from ctypes import wintypes
import math
import random
import time
import tkinter as tk
import winsound
from pathlib import Path
import wave


class WaveFormat(ctypes.Structure):
    _fields_ = [('tag', wintypes.WORD), ('channels', wintypes.WORD),
                ('rate', wintypes.DWORD), ('bytes_per_sec', wintypes.DWORD),
                ('alignment', wintypes.WORD), ('bits', wintypes.WORD),
                ('extra', wintypes.WORD)]


class WaveHeader(ctypes.Structure):
    _fields_ = [('data', ctypes.c_void_p), ('length', wintypes.DWORD),
                ('recorded', wintypes.DWORD), ('user', ctypes.c_size_t),
                ('flags', wintypes.DWORD), ('loops', wintypes.DWORD),
                ('next', ctypes.c_void_p), ('reserved', ctypes.c_size_t)]


class ReadySounds:
    """Keep the device open and PCM buffers ready before a click arrives."""
    def __init__(self, directory):
        self.api = ctypes.WinDLL('winmm')
        self.items = {}
        self.api.waveOutOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wintypes.UINT,
                                        ctypes.POINTER(WaveFormat), ctypes.c_size_t,
                                        ctypes.c_size_t, wintypes.DWORD]
        for name in ('drop', 'bite', 'reel'):
            with wave.open(str(directory / (name+'.wav'))) as wav:
                channels, rate, bits = wav.getnchannels(), wav.getframerate(), wav.getsampwidth()*8
                pcm = ctypes.create_string_buffer(wav.readframes(wav.getnframes()))
            alignment = channels*bits//8
            fmt = WaveFormat(1, channels, rate, rate*alignment, alignment, bits, 0)
            handle = ctypes.c_void_p()
            if self.api.waveOutOpen(ctypes.byref(handle), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0):
                continue
            header = WaveHeader(ctypes.addressof(pcm), len(pcm)-1, 0, 0, 0, 0, None, 0)
            if self.api.waveOutPrepareHeader(handle, ctypes.byref(header), ctypes.sizeof(header)):
                self.api.waveOutClose(handle)
                continue
            self.items[name] = (handle, header, pcm)

    def stop(self):
        for handle, _, _ in self.items.values():
            self.api.waveOutReset(handle)

    def play(self, name):
        if name not in self.items:
            return False
        self.stop()
        handle, header, _ = self.items[name]
        return self.api.waveOutWrite(handle, ctypes.byref(header), ctypes.sizeof(header)) == 0

    def close(self):
        self.stop()
        for handle, header, _ in self.items.values():
            self.api.waveOutUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(header))
            self.api.waveOutClose(handle)
        self.items.clear()


class Aquarium:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        try:
            self.user32.SetProcessDPIAware()
        except Exception:
            pass
        self.root = tk.Tk()
        self.root.title('Screen Fish')
        self.root.geometry('310x400+50+50')
        self.root.configure(bg='#102534')
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.paused = False
        self.fish = []
        self.cast = None
        self.caught = 0
        self.click_was_down = False
        self.right_was_down = False
        self.chum = []
        self.last_chum = -10
        self.fishing = tk.BooleanVar(value=True)
        self.sound_enabled = tk.BooleanVar(value=True)
        self.tint_enabled = tk.BooleanVar(value=True)
        self.last_water_frame = -1
        self.sound_dir = Path(__file__).resolve().parent / 'sounds'
        self.ready_sounds = ReadySounds(self.sound_dir)
        self.user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user32.GetAsyncKeyState.restype = ctypes.c_short
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self.density = tk.IntVar(value=5)
        self.water = tk.Toplevel(self.root)
        self.water.overrideredirect(True)
        self.water.configure(bg='#287e91')
        self.water.attributes('-alpha', .055)
        self.water.attributes('-topmost', True)
        self.water_canvas = tk.Canvas(self.water, bg='#287e91', highlightthickness=0)
        self.water_canvas.pack(fill='both', expand=True)
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg='#010101')
        self.overlay.attributes('-transparentcolor', '#010101')
        self.overlay.attributes('-topmost', True)
        self.canvas = tk.Canvas(self.overlay, bg='#010101', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.root.update_idletasks()
        self.configure_overlay()
        tk.Label(self.root, text='SCREEN FISH', font=('Segoe UI', 19, 'bold'),
                 fg='#74e2d3', bg='#102534').pack(pady=(18, 4))
        tk.Label(self.root, text='A little ocean, wherever you work.',
                 font=('Segoe UI', 10), fg='#c4d9e4', bg='#102534').pack()
        tk.Scale(self.root, from_=1, to=12, orient='horizontal', variable=self.density,
                 label='Fish activity', bg='#102534', fg='#e4f5fa',
                 troughcolor='#234455', highlightthickness=0, length=250).pack(pady=10)
        row = tk.Frame(self.root, bg='#102534')
        row.pack()
        self.pause_button = tk.Button(row, text='Pause', command=self.toggle, width=10)
        self.pause_button.pack(side='left', padx=4)
        tk.Button(row, text='Quit', command=self.quit, width=10).pack(side='left', padx=4)
        tk.Checkbutton(self.root, text='Click to drop / click to reel', variable=self.fishing,
                       bg='#102534', fg='#c4d9e4', selectcolor='#234455',
                       activebackground='#102534', activeforeground='#c4d9e4').pack(pady=(12, 0))
        self.status = tk.Label(self.root, text='Take your time. The fish will come.',
                               font=('Segoe UI', 9), fg='#74e2d3', bg='#102534')
        self.status.pack(pady=(7, 0))
        tk.Label(self.root, text='Right-click to sprinkle a little fish food.',
                 font=('Segoe UI', 9), fg='#9db9c9', bg='#102534').pack(pady=4)
        tk.Checkbutton(self.root, text='Soft fishing sounds', variable=self.sound_enabled,
                       command=self.stop_sound, bg='#102534', fg='#c4d9e4',
                       selectcolor='#234455', activebackground='#102534',
                       activeforeground='#c4d9e4').pack()
        tk.Label(self.root, text='Minimize this window to keep fish swimming.',
                 font=('Segoe UI', 9), fg='#9db9c9', bg='#102534').pack(pady=12)
        tk.Checkbutton(self.root, text='Gentle water tint', variable=self.tint_enabled,
                       command=self.update_tint, bg='#102534', fg='#c4d9e4',
                       selectcolor='#234455', activebackground='#102534',
                       activeforeground='#c4d9e4').pack()
        self.next_spawn = time.monotonic() + 1
        self.last_frame = time.monotonic()
        self.last_screen_check = 0
        self.poll_input()
        self.tick()

    def configure_overlay(self):
        u = self.user32
        self.left, self.top = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        self.width, self.height = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetParent.restype = wintypes.HWND
        get_style = u.GetWindowLongPtrW
        set_style = u.SetWindowLongPtrW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        for window in (self.water, self.overlay):
            window.geometry(f'{self.width}x{self.height}+0+0')
            window.update_idletasks()
            hwnd = u.GetParent(window.winfo_id()) or window.winfo_id()
            # Click-through, hidden from Alt-Tab, and never steals focus.
            set_style(hwnd, -20, get_style(hwnd, -20) | 0x80000 | 0x20 | 0x80 | 0x08000000)
            u.SetWindowPos(hwnd, -1, self.left, self.top, self.width, self.height, 0x10)

    def update_tint(self):
        self.water.attributes('-alpha', .055 if self.tint_enabled.get() and not self.paused else 0)

    def animate_water(self, now):
        if not self.tint_enabled.get() or now-self.last_water_frame < .15:
            return
        self.last_water_frame = now
        self.water_canvas.delete('rays')
        for i in range(6):
            x = self.width*(i-.5)/5 + math.sin(now*.12+i)*50
            self.water_canvas.create_polygon(x, 0, x+70, 0, x+300, self.height,
                                              x+130, self.height, fill='#64b9c2',
                                              outline='', tags='rays')

    def spawn(self):
        direction = random.choice((-1, 1))
        size = random.uniform(20, 39)
        palette = random.choice([
            ('#ffb44c', '#ff784f', '#ffe6a2'),
            ('#55cde7', '#2989cf', '#b3f6fa'),
            ('#c79aff', '#8861d2', '#efd9ff'),
            ('#ff8fae', '#e65989', '#ffd5e2'),
            ('#70deac', '#32a88c', '#c4ffe1')])
        tag = 'fish_' + str(time.monotonic_ns())
        self.fish.append(dict(x=-size*3 if direction == 1 else self.width+size*3,
                              y=random.uniform(60, max(61, self.height-80)),
                              size=size, direction=direction, speed=random.uniform(25, 48),
                              phase=random.uniform(0, math.tau), palette=palette, tag=tag))

    def draw(self, fish, now):
        c = self.canvas
        tag = fish['tag']
        c.delete(tag)
        s, d = fish['size'], fish['direction']
        x = fish['x']
        y = fish['y'] + math.sin(now*1.6 + fish['phase'])*14
        body, fin, shine = fish['palette']
        def poly(points, color):
            c.create_polygon(*[v for px, py in points for v in (x+px*s*d, y+py*s)],
                             fill=color, outline='', smooth=True, tags=tag)
        wag = math.sin(now*9 + fish['phase'])*.13
        poly([(-.9, 0), (-1.8, -.7+wag), (-1.65, .65+wag)], fin)
        poly([(-.35, -.3), (-.15, -.95), (.55, -.36)], fin)
        poly([(-.3, .3), (-.05, .8), (.55, .32)], fin)
        c.create_oval(x-s, y-s*.55, x+s, y+s*.55, fill=body, outline='', tags=tag)
        poly([(-.4, -.3), (.05, -.4), (.6, -.25), (.05, -.18)], shine)
        poly([(-.1, -.1), (-.42, .3), (.3, .16)], fin)
        ex, ey = x+s*.58*d, y-s*.1
        r = s*.135
        c.create_oval(ex-r, ey-r, ex+r, ey+r, fill='#fff7e8', outline='', tags=tag)
        r *= .52
        c.create_oval(ex-r+s*.025*d, ey-r, ex+r+s*.025*d, ey+r,
                      fill='#172b39', outline='', tags=tag)

    def tick(self):
        now = time.monotonic()
        dt = min(now-self.last_frame, .08)
        self.last_frame = now
        if now-self.last_screen_check > 4:
            self.last_screen_check = now
            if (self.user32.GetSystemMetrics(78), self.user32.GetSystemMetrics(79),
                self.user32.GetSystemMetrics(76), self.user32.GetSystemMetrics(77)) != (
                    self.width, self.height, self.left, self.top):
                self.configure_overlay()
        if not self.paused:
            self.animate_water(now)
            self.animate_chum(now)
            if now >= self.next_spawn and len(self.fish) < self.density.get():
                self.spawn()
                self.next_spawn = now + random.uniform(2, 7) / (self.density.get()/5)
            for fish in self.fish[:]:
                if self.cast and self.cast.get('fish') is fish:
                    continue
                target = self.cast
                interested = (target and target['state'] == 'waiting' and
                              target.get('visitor') is fish)
                food = self.food_target(fish, now) if not interested else None
                if interested or food:
                    destination = target if interested else food
                    dx, dy = destination['x']-fish['x'], destination['y']-fish['y']
                    distance = math.hypot(dx, dy)
                    step = min(distance, fish['speed']*(1.4 if interested else .85)*dt)
                    fish['direction'] = 1 if dx >= 0 else -1
                    fish['x'] += dx/max(1, distance)*step
                    fish['y'] += dy/max(1, distance)*step
                else:
                    fish['x'] += fish['direction']*fish['speed']*dt
                if fish['x'] < -160 or fish['x'] > self.width+160:
                    self.canvas.delete(fish['tag'])
                    self.fish.remove(fish)
                else:
                    self.draw(fish, now)
            self.animate_cast(now)
        self.root.after(33, self.tick)

    def poll_input(self):
        self.check_click(time.monotonic())
        self.root.after(8, self.poll_input)

    def check_click(self, now):
        down = bool(self.user32.GetAsyncKeyState(1) & 0x8000)
        right = bool(self.user32.GetAsyncKeyState(2) & 0x8000)
        left_edge = down and not self.click_was_down
        right_edge = right and not self.right_was_down
        if (left_edge or right_edge) and self.fishing.get() and not self.paused:
            point = wintypes.POINT()
            if self.user32.GetCursorPos(ctypes.byref(point)):
                # Leave the control panel's own buttons free of casts.
                panel_hit = (self.root.state() != 'iconic' and
                             self.root.winfo_rootx() <= point.x <= self.root.winfo_rootx()+self.root.winfo_width() and
                             self.root.winfo_rooty() <= point.y <= self.root.winfo_rooty()+self.root.winfo_height())
                if not panel_hit:
                    if right_edge:
                        self.drop_chum(point.x-self.left, point.y-self.top, now)
                    elif left_edge:
                        self.click_cast(point.x-self.left, point.y-self.top, now)
        self.click_was_down = down
        self.right_was_down = right

    def drop_chum(self, x, y, now):
        if now-self.last_chum < .8:
            return
        self.last_chum = now
        self.chum.append(dict(x=x, y=-12, landing_y=max(70, min(y, self.height-50)), start=now,
                              grains=[(random.uniform(-32, 32), random.uniform(-18, 18),
                                       random.uniform(1.5, 3)) for _ in range(16)]))
        self.chum = self.chum[-3:]

    def food_target(self, fish, now):
        nearby = [food for food in self.chum if now-food['start'] < 18 and
                  math.hypot(food['x']-fish['x'], food['y']-fish['y']) < 650]
        return min(nearby, key=lambda f: math.hypot(f['x']-fish['x'],
                   f['y']-fish['y'])) if nearby else None

    def chum_y(self, food, now):
        age = max(0, now-food['start'])
        # Water drag eases the initial fall into a slow, steady sinking speed.
        depth = food['landing_y']+12
        drag_time = max(1.5, depth/150)
        return min(self.height+35, -12+depth*(1-math.exp(-age/drag_time))+age*5)

    def animate_chum(self, now):
        self.canvas.delete('chum')
        self.chum = [food for food in self.chum if now-food['start'] < 18]
        for food in self.chum:
            age = now-food['start']
            food['y'] = self.chum_y(food, now)
            for i, (dx, dy, r) in enumerate(food['grains']):
                # The last grains disappear gradually as the food disperses.
                if age > 11+i*.44:
                    continue
                spread = 1+.9*(1-math.exp(-age/6))
                drift = (1-math.exp(-age/3))
                x = food['x']+dx*spread+math.sin(age*.4+i)*5*drift
                y = food['y']+dy*spread+math.sin(age*.3+i)*3*drift
                self.canvas.create_oval(x-r, y-r, x+r, y+r, fill='#c5b48a',
                                         outline='', tags='chum')

    def click_cast(self, x, y, now):
        if self.cast is None:
            self.cast = dict(start=now, x=x, y=max(70, y), fish=None,
                             state='dropping', visitor=None,
                             next_visit=now+random.uniform(3, 8))
            cast = self.cast
            self.root.after(150, lambda: self.play_sound('drop')
                            if self.cast is cast and not self.paused
                            and cast['state'] != 'reeling' else None)
            self.status.configure(text='Worm deployed. Looking extremely silly.')
        elif self.cast['state'] != 'reeling':
            self.cast['reel_y'] = self.bait_y(now)
            self.cast['start'] = now
            self.cast['state'] = 'reeling'
            self.play_sound('reel')

    def play_sound(self, name):
        if self.sound_enabled.get():
            if self.ready_sounds.play(name):
                return
            try:
                winsound.PlaySound(str(self.sound_dir / (name + '.wav')),
                                   winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except RuntimeError:
                pass

    def stop_sound(self):
        self.ready_sounds.stop()
        winsound.PlaySound(None, 0)

    def bait_y(self, now):
        cast = self.cast
        elapsed = max(0, now-cast['start'])
        if cast['state'] == 'dropping':
            return 30+(cast['y']-30)*(1-(1-min(1, elapsed))**3)
        if cast['state'] == 'reeling':
            return 30+(cast['reel_y']-30)*max(0, 1-elapsed/1.5)
        return cast['y']+math.sin(now*1.5)*3

    def animate_cast(self, now):
        self.canvas.delete('tackle')
        if not self.cast:
            return
        cast = self.cast
        elapsed = now-cast['start']
        if cast['state'] == 'dropping' and elapsed >= 1:
            cast['state'] = 'waiting'
        x, y = cast['x'], self.bait_y(now)
        if cast['state'] == 'waiting' and not cast['fish']:
            if now >= cast['next_visit'] and cast['visitor'] is None:
                candidates = [f for f in self.fish if 0 < f['x'] < self.width]
                if candidates:
                    cast['visitor'] = random.choice(candidates)
                    cast['visit_until'] = now+random.uniform(10, 20)
                cast['next_visit'] = now+random.uniform(5, 12)
            visitor = cast['visitor']
            if visitor:
                if math.hypot(visitor['x']-x, visitor['y']-y) < 28:
                    cast['fish'] = visitor
                    self.play_sound('bite')
                    self.status.configure(text='Nibble! Click again to reel your friend up.')
                elif now > cast['visit_until'] or visitor not in self.fish:
                    cast['visitor'] = None
                    cast['next_visit'] = now+random.uniform(4, 10)
        c = self.canvas
        c.create_line(x-70, 0, x-25, 16, x, 30, fill='#bda67e', width=4,
                      smooth=True, tags='tackle')
        c.create_line(x, 30, x+math.sin(now*1.4)*5, y/2, x, y,
                      fill='#b8d6d8', width=1, smooth=True, tags='tackle')
        # A tiny curved hook and a very unserious pink worm.
        c.create_line(x, y-12, x, y+14, x+10, y+18, x+15, y+8,
                      fill='#dce8e9', width=2, smooth=True, tags='tackle')
        wiggle = math.sin(now*3)*4
        worm = [x-5, y-7, x-14+wiggle, y+3, x+6, y+12,
                x+16+wiggle, y+22, x+5, y+29]
        c.create_line(*worm, fill='#b95b83', width=12, smooth=True,
                      capstyle='round', tags='tackle')
        c.create_line(*worm, fill='#f49fbd', width=8, smooth=True,
                      capstyle='round', tags='tackle')
        for ex, ey in ((x-10, y-12), (x, y-14)):
            c.create_oval(ex-5, ey-6, ex+5, ey+6, fill='#fff9e9', outline='', tags='tackle')
            c.create_oval(ex-1+wiggle*.3, ey-1, ex+2+wiggle*.3, ey+3,
                          fill='#253449', outline='', tags='tackle')
        c.create_arc(x-8, y-6, x+2, y+2, start=190, extent=150,
                     style='arc', outline='#70354e', width=2, tags='tackle')
        if cast['fish']:
            fish = cast['fish']
            fish['x'] = x
            fish['y'] = y+fish['size']*.7-math.sin(now*1.6+fish['phase'])*14
            self.draw(fish, now)
        if cast['state'] == 'reeling' and elapsed >= 1.5:
            if cast['fish']:
                fish = cast['fish']
                self.canvas.delete(fish['tag'])
                self.fish.remove(fish)
                self.caught += 1
                self.status.configure(text=f'{self.caught} fish caught & released. No hurry.')
            else:
                self.status.configure(text='A peaceful cast. Try near a passing fish.')
            self.canvas.delete('tackle')
            self.cast = None

    def toggle(self):
        self.paused = not self.paused
        self.update_tint()
        self.pause_button.configure(text='Resume' if self.paused else 'Pause')
        if self.paused:
            self.stop_sound()
            self.chum.clear()
            self.canvas.delete('all')
            if self.cast and self.cast.get('fish'):
                fish = self.cast['fish']
                fish['y'] = random.uniform(80, max(81, self.height-80))
            self.cast = None
        else:
            self.next_spawn = time.monotonic()

    def quit(self):
        self.stop_sound()
        self.ready_sounds.close()
        self.root.destroy()


if __name__ == '__main__':
    Aquarium().root.mainloop()
