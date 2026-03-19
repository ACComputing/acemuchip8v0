import tkinter as tk
from tkinter import filedialog, messagebox
import random
import os
import time

class Chip8CPU:
    def __init__(self):
        self.reset()

    def reset(self):
        # 4KB memory
        self.memory = [0] * 4096
        # 16 8-bit registers V0 to VF
        self.V = [0] * 16
        # Index register and Program Counter
        self.I = 0
        self.PC = 0x200
        # Stack for subroutines
        self.stack = [0] * 16
        self.SP = 0
        # Timers
        self.delay_timer = 0
        self.sound_timer = 0
        # Display 64x32
        self.display = [0] * (64 * 32)
        self.draw_flag = False
        # Input keys
        self.keys = [0] * 16
        # Internal state
        self.halted = False
        self.waiting_for_key = False
        self.key_register = 0

        # Load Fontset into memory (0x000-0x050)
        fontset = [
            0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
            0x20, 0x60, 0x20, 0x20, 0x70, # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
            0x90, 0x90, 0xF0, 0x10, 0x10, # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
            0xF0, 0x10, 0x20, 0x40, 0x40, # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90, # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
            0xF0, 0x80, 0x80, 0x80, 0xF0, # C
            0xE0, 0x90, 0x90, 0x90, 0xE0, # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
            0xF0, 0x80, 0xF0, 0x80, 0x80  # F
        ]
        for i in range(len(fontset)):
            self.memory[i] = fontset[i]

    def load_rom(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                rom_data = f.read()
            # Load ROM into memory starting at 0x200
            for i in range(len(rom_data)):
                if 0x200 + i < 4096:
                    self.memory[0x200 + i] = rom_data[i]
            self.halted = False
            self.PC = 0x200
            return True
        except Exception as e:
            print(f"Error loading ROM: {e}")
            return False

    def cycle(self):
        if self.halted:
            return

        # Handle waiting for key press (FX0A)
        if self.waiting_for_key:
            for i in range(16):
                if self.keys[i] == 1:
                    self.V[self.key_register] = i
                    self.waiting_for_key = False
                    return 
            return

        # Fetch Opcode (2 bytes)
        if self.PC + 1 >= 4096:
            self.halted = True
            return

        opcode = (self.memory[self.PC] << 8) | self.memory[self.PC + 1]
        self.decode_execute(opcode)

    def decode_execute(self, opcode):
        # Increment PC
        self.PC += 2

        # Extract common nibbles
        nnn = opcode & 0x0FFF
        nn = opcode & 0x00FF
        n = opcode & 0x000F
        x = (opcode >> 8) & 0x0F
        y = (opcode >> 4) & 0x0F

        first = (opcode >> 12) & 0x0F

        if first == 0x0:
            if opcode == 0x00E0: # Clear screen
                self.display = [0] * (64 * 32)
                self.draw_flag = True
            elif opcode == 0x00EE: # Return from subroutine
                if self.SP > 0:
                    self.SP -= 1
                    self.PC = self.stack[self.SP]
        
        elif first == 0x1: # Jump
            self.PC = nnn
        
        elif first == 0x2: # Call subroutine
            if self.SP < 16:
                self.stack[self.SP] = self.PC
                self.SP += 1
                self.PC = nnn
        
        elif first == 0x3: # Skip if Vx == NN
            if self.V[x] == nn:
                self.PC += 2
        
        elif first == 0x4: # Skip if Vx != NN
            if self.V[x] != nn:
                self.PC += 2
        
        elif first == 0x5: # Skip if Vx == Vy
            if self.V[x] == self.V[y]:
                self.PC += 2
        
        elif first == 0x6: # Set Vx = NN
            self.V[x] = nn
        
        elif first == 0x7: # Add NN to Vx
            self.V[x] = (self.V[x] + nn) & 0xFF
        
        elif first == 0x8:
            if n == 0x0:   self.V[x] = self.V[y]
            elif n == 0x1: self.V[x] |= self.V[y]
            elif n == 0x2: self.V[x] &= self.V[y]
            elif n == 0x3: self.V[x] ^= self.V[y]
            elif n == 0x4: # Add with carry
                total = self.V[x] + self.V[y]
                self.V[x] = total & 0xFF
                self.V[0xF] = 1 if total > 255 else 0
            elif n == 0x5: # Sub with borrow
                self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
                self.V[x] = (self.V[x] - self.V[y]) & 0xFF
            elif n == 0x6: # Shift Right
                self.V[0xF] = self.V[y] & 0x1
                self.V[x] = self.V[y] >> 1
            elif n == 0x7: # Sub Vy - Vx
                self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
                self.V[x] = (self.V[y] - self.V[x]) & 0xFF
            elif n == 0xE: # Shift Left
                self.V[0xF] = (self.V[y] >> 7) & 0x1
                self.V[x] = (self.V[y] << 1) & 0xFF
        
        elif first == 0x9: # Skip if Vx != Vy
            if self.V[x] != self.V[y]:
                self.PC += 2
        
        elif first == 0xA: # Set I
            self.I = nnn
        
        elif first == 0xB: # Jump V0 + NNN
            self.PC = nnn + self.V[0]
        
        elif first == 0xC: # Random
            self.V[x] = random.randint(0, 255) & nn
        
        elif first == 0xD: # Draw
            x_coord = self.V[x] % 64
            y_coord = self.V[y] % 32
            self.V[0xF] = 0
            
            for row in range(n):
                if self.I + row >= 4096: break
                sprite_byte = self.memory[self.I + row]
                
                for col in range(8):
                    if x_coord + col >= 64: break
                    if y_coord + row >= 32: break
                    
                    px = (y_coord + row) * 64 + x_coord + col
                    
                    if (sprite_byte & (0x80 >> col)) != 0:
                        if self.display[px] == 1:
                            self.V[0xF] = 1
                        self.display[px] ^= 1
            
            self.draw_flag = True

        elif first == 0xE:
            if nn == 0x9E: # Skip if Key Vx pressed
                if self.keys[self.V[x]] == 1:
                    self.PC += 2
            elif nn == 0xA1: # Skip if Key Vx not pressed
                if self.keys[self.V[x]] == 0:
                    self.PC += 2
        
        elif first == 0xF:
            if nn == 0x07: # Set Vx = Delay Timer
                self.V[x] = self.delay_timer
            elif nn == 0x0A: # Wait for key
                self.waiting_for_key = True
                self.key_register = x
            elif nn == 0x15: # Set Delay Timer = Vx
                self.delay_timer = self.V[x]
            elif nn == 0x18: # Set Sound Timer = Vx
                self.sound_timer = self.V[x]
            elif nn == 0x1E: # I += Vx
                self.I = (self.I + self.V[x]) & 0xFFF
            elif nn == 0x29: # Set I = Font char Vx
                self.I = (self.V[x] & 0xF) * 5
            elif nn == 0x33: # BCD
                val = self.V[x]
                self.memory[self.I] = val // 100
                self.memory[self.I + 1] = (val // 10) % 10
                self.memory[self.I + 2] = val % 10
            elif nn == 0x55: # Store V0-Vx
                for i in range(x + 1):
                    self.memory[self.I + i] = self.V[i]
                self.I += x + 1 
            elif nn == 0x65: # Load V0-Vx
                for i in range(x + 1):
                    self.V[i] = self.memory[self.I + i]
                self.I += x + 1

class CatsChip8:
    def __init__(self, root):
        self.root = root
        self.root.title("Cat's Chip 8 emulator")
        self.root.configure(bg="#202020")
        
        self.cpu = Chip8CPU()
        self.current_rom_path = None
        
        self.scale = 10
        self.fg_color = "#33FF33"
        self.bg_color = "black"
        
        self.create_menu()
        self.create_main_view()
        self.create_status_bar()
        
        self.last_cycle_time = time.time()
        self.running = False
        self.rom_loaded = False
        
        self.key_map = {
            '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
            'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
            'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
            'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
        }

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        
        # Initial sizing
        self.set_scale(10)
        self.loop()

    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        # Snes9x Style: File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load Game...", command=self.load_rom_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Snes9x Style: Emulation
        emu_menu = tk.Menu(menubar, tearoff=0)
        emu_menu.add_command(label="Pause", command=self.toggle_pause)
        emu_menu.add_command(label="Reset", command=self.reset_rom)
        menubar.add_cascade(label="Emulation", menu=emu_menu)
        
        # Snes9x Style: Input
        input_menu = tk.Menu(menubar, tearoff=0)
        input_menu.add_command(label="Input Configuration...", command=self.stub_dialog)
        menubar.add_cascade(label="Input", menu=input_menu)

        # Snes9x Style: Video
        video_menu = tk.Menu(menubar, tearoff=0)
        
        size_menu = tk.Menu(video_menu, tearoff=0)
        size_menu.add_command(label="1x Window Size", command=lambda: self.set_scale(1))
        size_menu.add_command(label="2x Window Size", command=lambda: self.set_scale(2))
        size_menu.add_command(label="5x Window Size", command=lambda: self.set_scale(5))
        size_menu.add_command(label="10x Window Size", command=lambda: self.set_scale(10))
        size_menu.add_command(label="15x Window Size", command=lambda: self.set_scale(15))
        video_menu.add_cascade(label="Window Size", menu=size_menu)
        
        color_menu = tk.Menu(video_menu, tearoff=0)
        color_menu.add_command(label="Phosphor Green", command=lambda: self.set_color("#33FF33"))
        color_menu.add_command(label="Amber", command=lambda: self.set_color("#FFB000"))
        color_menu.add_command(label="White", command=lambda: self.set_color("#FFFFFF"))
        video_menu.add_cascade(label="Display Color", menu=color_menu)
        
        menubar.add_cascade(label="Video", menu=video_menu)

        # Snes9x Style: Sound
        sound_menu = tk.Menu(menubar, tearoff=0)
        sound_menu.add_command(label="Sound Configuration...", command=self.stub_dialog)
        menubar.add_cascade(label="Sound", menu=sound_menu)

        # Snes9x Style: Help
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def create_main_view(self):
        self.main_frame = tk.Frame(self.root, bg="#202020")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.main_frame, bg="black", highlightthickness=0)
        self.canvas.pack(pady=10)
        
        self.pixels = []
        for y in range(32):
            row = []
            for x in range(64):
                rect = self.canvas.create_rectangle(0, 0, 0, 0, fill="black", outline="")
                row.append(rect)
            self.pixels.append(row)

    def create_status_bar(self):
        self.status_bar = tk.Label(self.root, text="Ready. Load a ROM.", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#f0f0f0")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_scale(self, new_scale):
        self.scale = new_scale
        w = 64 * self.scale
        h = 32 * self.scale
        self.canvas.config(width=w, height=h)
        self.root.geometry("") # Let window auto-resize around the canvas
        
        for y in range(32):
            for x in range(64):
                self.canvas.coords(
                    self.pixels[y][x],
                    x * self.scale,
                    y * self.scale,
                    (x + 1) * self.scale,
                    (y + 1) * self.scale
                )

    def set_color(self, hex_color):
        self.fg_color = hex_color
        self.cpu.draw_flag = True # Force a redraw
        
    def stub_dialog(self):
        messagebox.showinfo("Not Implemented", "This configuration dialog is a placeholder to match the Snes9x GUI layout.")

    def about_dialog(self):
        messagebox.showinfo("About", "[C] Chip 8 team [C] AC Team")

    def load_rom_dialog(self):
        file_path = filedialog.askopenfilename(filetypes=[("Chip 8 ROMs", "*.ch8"), ("All Files", "*.*")])
        if file_path:
            if self.cpu.load_rom(file_path):
                self.rom_loaded = True
                self.running = True
                self.current_rom_path = file_path
                rom_name = os.path.basename(file_path)
                self.status_bar.config(text=f"Running: {rom_name}")
                self.root.title(f"Cat's Chip 8 emulator - {rom_name}")
            else:
                messagebox.showerror("Error", "Failed to load ROM.")

    def toggle_pause(self):
        if self.rom_loaded:
            self.running = not self.running
            status = "Running" if self.running else "Paused"
            rom_name = os.path.basename(self.current_rom_path) if self.current_rom_path else ""
            self.status_bar.config(text=f"{status}: {rom_name}")

    def reset_rom(self):
        if self.rom_loaded and self.current_rom_path:
            self.cpu.reset()
            self.cpu.load_rom(self.current_rom_path)
            self.running = True
            rom_name = os.path.basename(self.current_rom_path)
            self.status_bar.config(text=f"Running: {rom_name}")
    
    def on_key_press(self, event):
        k = event.char.lower()
        if k in self.key_map:
            self.cpu.keys[self.key_map[k]] = 1

    def on_key_release(self, event):
        k = event.char.lower()
        if k in self.key_map:
            self.cpu.keys[self.key_map[k]] = 0

    def render(self):
        if self.cpu.draw_flag:
            self.cpu.draw_flag = False
            for y in range(32):
                for x in range(64):
                    idx = y * 64 + x
                    color = self.fg_color if self.cpu.display[idx] == 1 else self.bg_color
                    self.canvas.itemconfig(self.pixels[y][x], fill=color)

    def loop(self):
        if self.running:
            # Run several cycles per frame to approximate ~600Hz CPU speed
            for _ in range(10):
                self.cpu.cycle()
            
            # Update Timers at 60Hz
            self.cpu.delay_timer = max(0, self.cpu.delay_timer - 1)
            self.cpu.sound_timer = max(0, self.cpu.sound_timer - 1)
            
            self.render()
            
        self.root.after(16, self.loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = CatsChip8(root)
    root.mainloop()
