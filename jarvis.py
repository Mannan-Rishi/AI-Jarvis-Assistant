import sys, os, threading, time, math, random
import numpy as np
import psutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame, QSizePolicy,
    QScrollArea, QGraphicsDropShadowEffect, QSpacerItem)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal, QThread
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, QBrush,
    QRadialGradient, QLinearGradient, QPainterPath, QImage, QPixmap)

from voice import voice
from commands import process_command
import config
from vision import vision
from automation_controller import automation

# ── Design Tokens ─────────────────────────────────────────────────────────────
C_BG      = "#08080f"
C_PANEL   = "rgba(12,16,36,0.88)"
C_BORDER  = "rgba(74,158,255,0.18)"
C_TEXT    = "#c8d6f0"
C_DIM     = "#4a5880"

STATE_COLORS = {
    "IDLE":        QColor(74,  158, 255),
    "LISTENING":   QColor(16,  185, 129),
    "THINKING":    QColor(245, 158, 11),
    "SPEAKING":    QColor(139, 92,  246),
    "EXECUTING":   QColor(0,   212, 255),
    "INTERRUPTED": QColor(251, 191, 36),
    "ERROR":       QColor(239, 68,  68),
    "PROCESSING":  QColor(245, 158, 11),
    "INITIALIZING":QColor(74,  158, 255),
    "VISION":      QColor(236, 72,  153),
    "CONTROLLING": QColor(255, 69,  0),   # Orange Red
    "AUTOMATING":  QColor(0,   255, 255), # Cyan
}

# ── Neural Background ─────────────────────────────────────────────────────────
class NeuralBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._nodes, self._tick = [], 0
        t = QTimer(self); t.timeout.connect(self._step); t.start(50)

    def _init_nodes(self):
        w, h = self.width(), self.height()
        self._nodes = [{'x': random.uniform(0,w), 'y': random.uniform(0,h),
            'vx': random.uniform(-0.25,0.25), 'vy': random.uniform(-0.25,0.25)}
            for _ in range(45)]

    def resizeEvent(self, e): self._init_nodes()

    def _step(self):
        if not self._nodes: self._init_nodes()
        w, h = self.width(), self.height()
        for n in self._nodes:
            n['x'] += n['vx']; n['y'] += n['vy']
            if not (0 < n['x'] < w): n['vx'] *= -1
            if not (0 < n['y'] < h): n['vy'] *= -1
        self._tick += 1; self.update()

    def paintEvent(self, e):
        if not self._nodes: return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        MAX = 160
        for i, n1 in enumerate(self._nodes):
            for n2 in self._nodes[i+1:]:
                d = math.hypot(n1['x']-n2['x'], n1['y']-n2['y'])
                if d < MAX:
                    a = int(22*(1-d/MAX))
                    p.setPen(QPen(QColor(74,158,255,a), 0.6))
                    p.drawLine(QPointF(n1['x'],n1['y']), QPointF(n2['x'],n2['y']))
        p.setPen(Qt.NoPen)
        for n in self._nodes:
            p.setBrush(QBrush(QColor(74,158,255,35)))
            p.drawEllipse(QRectF(n['x']-1.5, n['y']-1.5, 3, 3))
        p.end()

# ── AI Orb ────────────────────────────────────────────────────────────────────
class AIOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 340)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.state = "IDLE"
        self.color = STATE_COLORS["IDLE"]
        self.is_active = False          # compat alias
        self._breathe = 0.0
        self._ring_a  = [0.0, 0.0, 0.0]
        self._boot    = 0.0
        self._particles = [{'a': random.uniform(0,6.28),
            'r': random.uniform(55,130), 'spd': random.uniform(0.004,0.013),
            'sz': random.uniform(1.5,3.2), 'al': random.randint(100,200)}
            for _ in range(22)]
        t = QTimer(self); t.timeout.connect(self._step); t.start(16)

    def set_state(self, state):
        self.state = state
        self.color = STATE_COLORS.get(state, STATE_COLORS["IDLE"])
        self.is_active = state in ("LISTENING","PROCESSING","THINKING","EXECUTING","VISION","CONTROLLING","AUTOMATING")

    def _step(self):
        self._breathe = (self._breathe + 0.022) % 6.283
        spd = {"THINKING":3.2,"SPEAKING":2.6,"LISTENING":2.0,"EXECUTING":3.0}.get(self.state, 1.0)
        self._ring_a[0] = (self._ring_a[0] + 0.009*spd) % 6.283
        self._ring_a[1] = (self._ring_a[1] - 0.006*spd) % 6.283
        self._ring_a[2] = (self._ring_a[2] + 0.013*spd) % 6.283
        for pt in self._particles:
            pt['a'] = (pt['a'] + pt['spd']*(1+spd*0.4)) % 6.283
        self._boot = min(1.0, self._boot + 0.009)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect(); cx, cy = r.width()/2, r.height()/2
        bp = self._boot
        br = 1.0 + 0.06*math.sin(self._breathe)
        base = min(cx,cy)*0.36*bp
        c = self.color

        # outer halos
        for rad, al in [(base*2.9,12),(base*2.2,22),(base*1.75,38)]:
            rad *= br
            g = QRadialGradient(cx, cy, rad)
            gc = QColor(c); gc.setAlpha(al); g.setColorAt(0, gc)
            g.setColorAt(1, QColor(0,0,0,0))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx-rad, cy-rad, rad*2, rad*2))

        # orbit rings
        for i,(rad,span,lw) in enumerate([(base*1.55,55,2.0),(base*1.22,110,1.4),(base*0.92,80,1.0)]):
            rad *= bp; a = int(math.degrees(self._ring_a[i])*16)
            pc = QColor(c); pc.setAlpha(75+int(45*math.sin(self._breathe+i)))
            pen = QPen(pc, lw); pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cx-rad,cy-rad,rad*2,rad*2), a, span*16)
            p.drawArc(QRectF(cx-rad,cy-rad,rad*2,rad*2), a+180*16, span*16)

        # particles
        p.setPen(Qt.NoPen)
        for pt in self._particles:
            px = cx + pt['r']*math.cos(pt['a'])*bp
            py = cy + pt['r']*math.sin(pt['a'])*bp
            pc = QColor(c); pc.setAlpha(int(pt['al']*bp))
            p.setBrush(QBrush(pc)); s=pt['sz']
            p.drawEllipse(QRectF(px-s/2, py-s/2, s, s))

        # core
        cr = base*br
        g = QRadialGradient(cx, cy, cr)
        cc = QColor(255,255,255,210); g.setColorAt(0, cc)
        mid = QColor(c); mid.setAlpha(195); g.setColorAt(0.38, mid)
        out = QColor(c.darker(170)); out.setAlpha(70); g.setColorAt(0.85, out)
        g.setColorAt(1.0, QColor(0,0,0,0))
        p.setBrush(QBrush(g))
        p.drawEllipse(QRectF(cx-cr, cy-cr, cr*2, cr*2))

        # speaking ripple
        if self.state == "SPEAKING":
            rr = base*(1.0+0.45*abs(math.sin(self._breathe*3)))
            rpen = QPen(QColor(c.red(),c.green(),c.blue(),55), 1.5)
            p.setPen(rpen); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx-rr, cy-rr, rr*2, rr*2))
        
        # automation pulse
        if self.state in ("CONTROLLING", "AUTOMATING"):
            for rad, al in [(base*3.5, 30), (base*4.5, 15)]:
                rad *= (1.0 + 0.1 * math.sin(self._breathe * 4))
                pc = QColor(self.color); pc.setAlpha(al)
                p.setPen(QPen(pc, 1.0)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(cx-rad, cy-rad, rad*2, rad*2))
        
        p.end()

# ── Premium Waveform ──────────────────────────────────────────────────────────
class PremiumWaveform(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.is_speaking = False
        self._bars = [0.0]*44
        t = QTimer(self); t.timeout.connect(self._step); t.start(45)

    def _step(self):
        if self.is_speaking:
            tgt = [random.uniform(0.28,1.0) for _ in range(44)]
        else:
            tgt = [random.uniform(0.01,0.06) for _ in range(44)]
        self._bars = [b*0.55+t*0.45 for b,t in zip(self._bars,tgt)]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._bars); bw = w/(n*1.6); gap = bw*0.6; tot = bw+gap
        xs = (w - tot*n)/2; mid = h/2
        for i,v in enumerate(self._bars):
            bh = v*(h*0.44)
            cr = abs(i-n/2)/(n/2)
            r=int(74+65*cr); g=int(158-80*cr); b=255
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(r,g,b,int(160+90*v))))
            x = xs+i*tot
            p.drawRoundedRect(QRectF(x,mid-bh,bw,bh*2), bw/2, bw/2)
        p.setPen(QPen(QColor(255,215,0,50),1))
        p.drawLine(0,int(mid),w,int(mid))
        p.end()

# ── Stats Widget ──────────────────────────────────────────────────────────────
class StatsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(90)
        self.cpu = 0; self.ram = 0
        t = QTimer(self); t.timeout.connect(self._update); t.start(2000)

    def _update(self):
        self.cpu = psutil.cpu_percent()
        self.ram = psutil.virtual_memory().percent
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(12,16,36,200)))
        path = QPainterPath(); path.addRoundedRect(QRectF(0,0,w,h), 12, 12)
        p.drawPath(path)
        p.setPen(QPen(QColor(74,158,255,40),1))
        p.drawRoundedRect(QRectF(0.5,0.5,w-1,h-1), 12, 12)

        font = QFont("Segoe UI", 8); p.setFont(font)

        for row,label,val in [(0,"CPU CORE",self.cpu),(1,"MEMORY",self.ram)]:
            y0 = 14+row*36
            p.setPen(QColor(100,130,180))
            p.drawText(QRectF(14,y0,100,14), Qt.AlignLeft, label)
            p.setPen(QColor(200,220,255))
            p.drawText(QRectF(w-60,y0,46,14), Qt.AlignRight, f"{val:.0f}%")
            # track bg
            p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(30,40,80,160)))
            p.drawRoundedRect(QRectF(14,y0+17,w-28,5), 2.5, 2.5)
            # fill
            c = QColor(74,158,255) if row==0 else QColor(139,92,246)
            p.setBrush(QBrush(c))
            p.drawRoundedRect(QRectF(14,y0+17,(w-28)*(val/100),5), 2.5, 2.5)
        p.end()

# ── Vision Feed Widget ────────────────────────────────────────────────────────
class VisionFeed(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(140)
        self.image = None
        self.active_title = "Desktop"
        self._glow = 0.0
        t = QTimer(self); t.timeout.connect(self._step); t.start(100)

    def _step(self):
        self._glow = (self._glow + 0.1) % 6.28
        self.update()

    def set_data(self, img_bytes, title):
        if img_bytes:
            qimg = QImage.fromData(img_bytes)
            self.image = QPixmap.fromImage(qimg)
        self.active_title = title if title else "Desktop"

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        # Background
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(12,16,36,200)))
        p.drawRoundedRect(QRectF(0,0,w,h), 12, 12)
        
        # Screenshot Preview
        if self.image:
            # Draw blurred/dimmed screenshot
            target_rect = QRectF(10, 30, w-20, h-40)
            p.setOpacity(0.6)
            p.drawPixmap(target_rect.toRect(), self.image.scaled(int(w-20), int(h-40), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            p.setOpacity(1.0)
        
        # Overlay border glow
        g_val = abs(math.sin(self._glow)) * 40
        p.setPen(QPen(QColor(236, 72, 153, int(50 + g_val)), 1.5))
        p.drawRoundedRect(QRectF(0.5,0.5,w-1,h-1), 12, 12)
        
        # Labels
        font = QFont("Segoe UI", 8, QFont.Bold)
        p.setFont(font)
        p.setPen(QColor(236, 72, 153))
        p.drawText(QRectF(14, 10, w-28, 15), Qt.AlignLeft, "LIVE OPTIC FEED")
        
        font.setBold(False); font.setPointSize(7)
        p.setFont(font)
        p.setPen(QColor(200, 220, 255, 180))
        title_text = self.active_title if len(self.active_title) < 30 else self.active_title[:27]+"..."
        p.drawText(QRectF(14, h-18, w-28, 15), Qt.AlignLeft, f"CONTEXT: {title_text}")
        p.end()

# ── Glass Panel helper ────────────────────────────────────────────────────────
def glass_frame(radius=16):
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background-color: rgba(12,16,36,0.82);
            border: 1px solid rgba(74,158,255,0.18);
            border-radius: {radius}px;
        }}
    """)
    return f

# ── Main Window ───────────────────────────────────────────────────────────────
class JarvisGUI(QMainWindow):
    status_signal = pyqtSignal(str)
    chat_signal   = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.is_listening = False
        self.init_ui()
        self.status_signal.connect(self.update_status)
        self.chat_signal.connect(self.add_chat_message)
        voice.on_interrupt = self._handle_interrupt
        QTimer.singleShot(120, self.start_boot_sequence)

    # ── UI Construction ───────────────────────────────────────────────────────
    def init_ui(self):
        self.setWindowTitle(config.WINDOW_TITLE)
        self.resize(1280, 820)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(f"background-color: {C_BG}; color: {C_TEXT};")

        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0,0,0,0)
        root_layout.setSpacing(0)

        # ── Neural background (absolute, under everything) ─────────────────
        self._bg = NeuralBackground(root)
        self._bg.setGeometry(0,0,1280,820)
        self._bg.lower()

        # ── Left Nav Sidebar ───────────────────────────────────────────────
        nav = QWidget(); nav.setFixedWidth(72)
        nav.setStyleSheet("background-color: rgba(8,10,22,0.95); border-right: 1px solid rgba(74,158,255,0.12);")
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(10,20,10,20)
        nav_layout.setSpacing(8)

        logo = QLabel("✦")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("color: #4a9eff; font-size: 22px; padding-bottom: 12px;")
        nav_layout.addWidget(logo)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(74,158,255,0.2);")
        nav_layout.addWidget(sep)
        nav_layout.addSpacing(8)

        for icon, tip in [("⊙","Assistant"),("⚡","Automation"),
                          ("📁","Files"),("⌚","Schedule"),("⚙","Settings")]:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setFixedSize(48,48)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { background:rgba(74,158,255,0.07); border:1px solid rgba(74,158,255,0.2);
                    border-radius:12px; font-size:18px; color:rgba(160,175,210,0.7); }
                QPushButton:hover { background:rgba(74,158,255,0.22); border:1px solid rgba(74,158,255,0.55);
                    color:#4a9eff; }
            """)
            nav_layout.addWidget(btn, alignment=Qt.AlignHCenter)

        nav_layout.addStretch()
        root_layout.addWidget(nav)

        # ── Center Panel ───────────────────────────────────────────────────
        center = QWidget()
        center.setStyleSheet("background:transparent;")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(24,20,24,20)
        center_layout.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(48)
        title_bar.setStyleSheet("background:transparent;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(0,0,0,0)
        title_lbl = QLabel("RISHI INDUSTRIES  ·  J·A·R·V·I·S")
        title_lbl.setStyleSheet("color:#4a9eff; font-family:'Segoe UI'; font-size:13px; font-weight:600; letter-spacing:4px;")
        tb_layout.addStretch()
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()
        center_layout.addWidget(title_bar)

        # Orb
        self.arc_ring = AIOrb()    # kept as arc_ring for compat
        center_layout.addWidget(self.arc_ring, alignment=Qt.AlignCenter)

        center_layout.addSpacing(12)

        # Waveform
        self.waveform = PremiumWaveform()
        center_layout.addWidget(self.waveform)

        center_layout.addSpacing(14)

        # Status label
        self.status_label = QLabel("IDLE")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "color:#4a9eff; font-family:'Segoe UI'; font-size:11px; "
            "letter-spacing:5px; font-weight:600;")
        center_layout.addWidget(self.status_label)

        center_layout.addSpacing(18)

        # Mic button
        self.mic_btn = QPushButton("⬤")
        self.mic_btn.setFixedSize(72, 72)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(74,158,255,0.12);
                border: 2px solid rgba(74,158,255,0.5);
                border-radius: 36px; font-size: 26px; color: #4a9eff;
            }
            QPushButton:hover {
                background-color: rgba(74,158,255,0.28);
                border: 2px solid #4a9eff;
            }
            QPushButton:pressed {
                background-color: #4a9eff; color: #08080f;
            }
        """)
        self.mic_btn.clicked.connect(self.toggle_mic)

        mic_hint = QLabel("PRESS TO SPEAK")
        mic_hint.setAlignment(Qt.AlignCenter)
        mic_hint.setStyleSheet("color:rgba(74,158,255,0.45); font-family:'Segoe UI'; font-size:9px; letter-spacing:3px;")

        center_layout.addWidget(self.mic_btn, alignment=Qt.AlignCenter)
        center_layout.addSpacing(6)
        center_layout.addWidget(mic_hint)
        center_layout.addStretch()

        root_layout.addWidget(center, stretch=3)

        # ── Right Panel ────────────────────────────────────────────────────
        right = QWidget(); right.setFixedWidth(310)
        right.setStyleSheet("background:transparent;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0,20,20,20)
        right_layout.setSpacing(14)

        # Stats card
        stats_card = glass_frame()
        sc_layout = QVBoxLayout(stats_card)
        sc_layout.setContentsMargins(0,8,0,8)
        hdr = QLabel("  SYSTEM TELEMETRY")
        hdr.setStyleSheet("color:rgba(74,158,255,0.6); font-family:'Segoe UI'; font-size:9px; letter-spacing:3px;")
        sc_layout.addWidget(hdr)
        self.stats = StatsWidget()
        sc_layout.addWidget(self.stats)
        right_layout.addWidget(stats_card)

        # Vision Feed card
        self.vision_feed = VisionFeed()
        right_layout.addWidget(self.vision_feed)

        # Chat feed card
        chat_card = glass_frame()
        cc_layout = QVBoxLayout(chat_card)
        cc_layout.setContentsMargins(14,12,14,12)
        cc_layout.setSpacing(8)

        chat_hdr = QLabel("SECURE UPLINK")
        chat_hdr.setStyleSheet("color:rgba(74,158,255,0.5); font-family:'Segoe UI'; font-size:9px; letter-spacing:3px;")
        cc_layout.addWidget(chat_hdr)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: rgba(74,158,255,0.15);")
        cc_layout.addWidget(sep2)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background:transparent; border:none;
                color: #c8d6f0; font-family:'Segoe UI'; font-size:10pt;
                line-height:1.6;
            }
            QScrollBar:vertical { background:transparent; width:4px; }
            QScrollBar::handle:vertical { background:rgba(74,158,255,0.3); border-radius:2px; }
        """)
        cc_layout.addWidget(self.chat_display)
        right_layout.addWidget(chat_card, stretch=1)

        root_layout.addWidget(right)

    # ── Resize background ──────────────────────────────────────────────────────
    def resizeEvent(self, e):
        if hasattr(self, '_bg'):
            self._bg.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(e)

    # ── Boot sequence ─────────────────────────────────────────────────────────
    def start_boot_sequence(self):
        self.status_label.setText("INITIALIZING")
        self.arc_ring.set_state("IDLE")
        self.speak("Systems calibrating. Just a moment, sir.")
        QTimer.singleShot(2200, self.greet_boss)

    def greet_boss(self):
        self.speak("JARVIS online, sir.")
        # Start passive wake word listening in the background
        voice.start_passive_listening(self._on_wake_word)
        # Start passive vision tracking
        vision.start_passive_mode()
        # Start UI update timer for vision
        self.vision_timer = QTimer(self)
        self.vision_timer.timeout.connect(self._update_vision_ui)
        self.vision_timer.start(2000)

    def _update_vision_ui(self):
        img_bytes = vision.get_ui_preview()
        title = vision.get_active_window()
        self.vision_feed.set_data(img_bytes, title)

    # ── State management ──────────────────────────────────────────────────────
    def update_status(self, text):
        clean = text.replace("STATUS:", "").replace("...", "").strip()
        
        # Check if automation is overriding state
        if automation.is_active:
            clean = "AUTOMATING"
        
        self.status_label.setText(clean)
        state = clean.upper().split()[0] if clean else "IDLE"
        self.arc_ring.set_state(state)
        # Update status color
        c = STATE_COLORS.get(state, STATE_COLORS["IDLE"])
        hex_c = f"#{c.red():02x}{c.green():02x}{c.blue():02x}"
        self.status_label.setStyleSheet(
            f"color:{hex_c}; font-family:'Segoe UI'; font-size:11px; "
            f"letter-spacing:5px; font-weight:600;")

    def add_chat_message(self, role, message):
        ts = time.strftime("%H:%M")
        if role == "USER":
            color, prefix = "#64b5f6", "YOU"
        else:
            color, prefix = "#b39ddb", "J·A·R·V·I·S"
        self.chat_display.append(
            f"<span style='color:rgba(100,116,139,0.7);font-size:8pt;'>[{ts}]</span> "
            f"<span style='color:{color};font-weight:600;'>{prefix}</span><br>"
            f"<span style='color:#c8d6f0;'>{message}</span><br>"
        )
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum())

    # ── Voice actions ─────────────────────────────────────────────────────────
    def toggle_mic(self):
        if not self.is_listening:
            threading.Thread(target=self.run_voice_command, daemon=True).start()

    def _handle_interrupt(self):
        if self.is_listening: return
        self.waveform.is_speaking = False
        self.status_signal.emit("INTERRUPTED")
        self.run_voice_command()

    def _on_wake_word(self):
        if self.is_listening: return
        self.status_signal.emit("LISTENING")
        self.toggle_mic()

    def speak(self, text):
        self.chat_signal.emit("JARVIS", text)
        self.waveform.is_speaking = True
        voice.speak(text)
        QTimer.singleShot(max(len(text)*80, 800),
            lambda: setattr(self.waveform, 'is_speaking', False))

    def run_voice_command(self):
        voice.stop_speech()
        self.is_listening = True
        self.status_signal.emit("LISTENING")
        query = voice.listen()
        if query and query != "..." and len(query.strip()) > 0:
            text_clean = query.lower().strip()
            vision_triggers = [
                "what's on my screen", "what am i doing", "what am i working on", 
                "summarize this page", "summarize this", "explain this",
                "screen pe kya chal raha", "is page ko explain karo", "see my screen",
                "look at my screen", "what is this", "what is on my screen",
                "isey dekho", "dekho screen par", "what's this", "identify this",
                "click on", "type in", "type this", "scroll down", "scroll up",
                "click karo", "type karo", "upar scroll karo", "neeche scroll karo"
            ]
            if any(trigger in text_clean for trigger in vision_triggers):
                self.status_signal.emit("VISION")
            else:
                self.status_signal.emit("THINKING")

            self.chat_signal.emit("USER", query)
            response, cmd_type = process_command(query)
            self.status_signal.emit("SPEAKING")
            self.speak(response)
        else:
            self.status_signal.emit("IDLE")
        self.is_listening = False
        self.status_signal.emit("IDLE")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = JarvisGUI()
    window.show()
    sys.exit(app.exec_())
