import sys
import os
import glob
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import csv

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QDial,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QToolButton,
    QMenu,
    QFileDialog,
)
from PyQt6.QtGui import QPixmap, QIcon, QAction
from PyQt6.QtCore import Qt, QSize, QTimer


class DrumMachineGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BeatBunker")
        self.setFixedSize(1000, 500)

        # State variables
        self.num_rows = 8
        self.num_cols = 16
        self.current_step = -1
        self.is_playing = False
        self.closing = False  # Prevent playback during close

        # Determine available kits: subfolders under "samples/"
        self.kit_names = sorted(
            [
                name
                for name in os.listdir("samples")
                if os.path.isdir(os.path.join("samples", name))
            ]
        )
        if not self.kit_names:
            raise RuntimeError("No kit subfolders found under samples/")

        # Default kit
        self.current_kit = self.kit_names[0]

        # Prepare containers (empty for now)
        self.samples = []          # Will hold (name, data, sr)
        self.sample_labels = []
        self.step_buttons = []
        self.vol_dials = []
        self.pitch_dials = []

        # Central widget and layout
        central = QWidget()
        central.setStyleSheet("background-color: #1e1e1e;")
        central_v = QVBoxLayout()
        central_v.setContentsMargins(10, 10, 10, 10)
        central_v.setSpacing(0)
        central.setLayout(central_v)
        self.setCentralWidget(central)

        # Config values
        button_size = 40
        dial_size = 40
        label_width = 100
        spacing_between_buttons = 6
        spacing_after_header = 2

        # Container for header + grid
        main_container = QWidget()
        main_container.setMinimumSize(1000, 450)
        main_container.setStyleSheet("background-color: transparent;")
        main_v = QVBoxLayout()
        main_v.setContentsMargins(0, 0, 20, 0)  # 20 px right margin
        main_v.setSpacing(0)
        main_container.setLayout(main_v)

        # 1) Top header
        header_h = QHBoxLayout()
        header_h.setContentsMargins(0, 0, 0, 0)
        header_h.setSpacing(spacing_between_buttons)
        header_h.addSpacing(label_width + 5)

        label_positions = {1: "1", 5: "2", 9: "3", 13: "4"}
        for col in range(1, self.num_cols + 1):
            text = label_positions.get(col, "")
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(QSize(button_size, button_size // 2))
            lbl.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    font-weight: bold;
                    margin: 0px;
                    padding: 0px;
                }
            """)
            header_h.addWidget(lbl)

        header_h.addSpacing(spacing_between_buttons)

        vol_lbl = QLabel("Vol")
        vol_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vol_lbl.setFixedSize(QSize(dial_size, button_size // 2))
        vol_lbl.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
                margin: 0px;
                padding: 0px;
            }
        """)
        header_h.addWidget(vol_lbl)
        header_h.addSpacing(spacing_between_buttons)

        pitch_lbl = QLabel("Pitch")
        pitch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pitch_lbl.setFixedSize(QSize(dial_size, button_size // 2))
        pitch_lbl.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
                margin: 0px;
                padding: 0px;
            }
        """)
        header_h.addWidget(pitch_lbl)

        main_v.addLayout(header_h)
        main_v.addSpacing(spacing_after_header)

        # Shared stylesheet for step buttons
        step_button_stylesheet = """
            QPushButton {
                background-color: #333333;
                border: 1px solid #444444;
                border-radius: 8px;
            }
            QPushButton:checked {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.8,
                    fx:0.5, fy:0.5,
                    stop:0 #4da6ff, stop:0.8 #007aff, stop:1 #005bb5
                );
                border: 1px solid #004080;
            }
            QPushButton[highlighted="true"] {
                background-color: #555555;
                border: 2px solid #00FFFF;
            }
        """

        # 2) Grid rows (labels, buttons, dials)
        for row in range(self.num_rows):
            row_h = QHBoxLayout()
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(spacing_between_buttons)

            # Sample label placeholder
            sample_label = QLabel(f"Sample {row+1}")
            sample_label.setFixedWidth(label_width)
            sample_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            sample_label.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    font-size: 14px;
                    margin-left: 4px;
                }
            """)
            row_h.addWidget(sample_label)
            self.sample_labels.append(sample_label)

            # 16 step buttons
            btn_row = []
            for _ in range(self.num_cols):
                btn = QPushButton()
                btn.setCheckable(True)
                btn.setFixedSize(QSize(button_size, button_size))
                btn.setProperty("highlighted", False)
                btn.setStyleSheet(step_button_stylesheet)
                row_h.addWidget(btn)
                btn_row.append(btn)
            self.step_buttons.append(btn_row)

            # Spacer before dials
            row_h.addSpacing(spacing_between_buttons)

            # Volume dial
            vol_dial = QDial()
            vol_dial.setMinimum(0)
            vol_dial.setMaximum(100)
            vol_dial.setValue(100)
            vol_dial.setFixedSize(QSize(dial_size, dial_size))
            vol_dial.setStyleSheet("""
                QDial::groove {
                    background: #444444;
                }
                QDial::handle {
                    background: #007aff;
                    border: 1px solid #555555;
                    width: 12px;
                    height: 12px;
                    border-radius: 6px;
                }
            """)
            row_h.addWidget(vol_dial)
            self.vol_dials.append(vol_dial)

            # Pitch dial (-8 to +8)
            pitch_dial = QDial()
            pitch_dial.setFixedSize(QSize(dial_size, dial_size))
            pitch_dial.setMinimum(-8)
            pitch_dial.setMaximum(8)
            pitch_dial.setValue(0)
            pitch_dial.setStyleSheet("""
                QDial::groove {
                    background: #444444;
                }
                QDial::handle {
                    background: #007aff;
                    border: 1px solid #555555;
                    width: 12px;
                    height: 12px;
                    border-radius: 6px;
                }
            """)
            row_h.addWidget(pitch_dial)
            self.pitch_dials.append(pitch_dial)

            main_v.addLayout(row_h)

        # Add vertical space, then insert main_container
        main_v.addSpacing(10)
        central_v.addWidget(main_container)

        # 3) Bottom controls: playback, tempo, kits, save/load
        bottom_h = QHBoxLayout()
        bottom_h.setContentsMargins(0, 0, 0, 0)
        bottom_h.setSpacing(0)

        # Helper for icon buttons
        def make_icon_button(filename: str):
            btn = QPushButton()
            btn.setFixedSize(QSize(22, 22))
            btn.setFlat(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 60);
                    border-radius: 4px;
                }
            """)
            icon_path = os.path.join("img", filename)
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    100, 100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                btn.setIcon(QIcon(scaled))
                btn.setIconSize(QSize(22, 22))
            return btn

        # Playback controls
        self.clear_btn = make_icon_button("restart.png")
        self.pause_btn = make_icon_button("pause.png")
        self.play_btn = make_icon_button("play.png")
        self.clear_btn.clicked.connect(self.clear_sequence)
        self.play_btn.clicked.connect(self.start_playback)
        self.pause_btn.clicked.connect(self.stop_playback)

        playback_container = QWidget()
        playback_layout = QHBoxLayout()
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setSpacing(8)
        playback_layout.addWidget(self.clear_btn)
        playback_layout.addWidget(self.pause_btn)
        playback_layout.addWidget(self.play_btn)
        playback_container.setLayout(playback_layout)

        # Tempo controls
        tempo_container = QWidget()
        tempo_layout = QHBoxLayout()
        tempo_layout.setContentsMargins(0, 0, 0, 0)
        tempo_layout.setSpacing(2)

        tempo_label = QLabel("Tempo:")
        tempo_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
            }
        """)

        self.tempo_edit = QLineEdit("120")
        self.tempo_edit.setFixedWidth(50)
        self.tempo_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tempo_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 2px;
            }
        """)

        up_btn = make_icon_button("up.png")
        down_btn = make_icon_button("down.png")
        up_btn.clicked.connect(self.increase_tempo)
        down_btn.clicked.connect(self.decrease_tempo)

        tempo_layout.addWidget(down_btn)
        tempo_layout.addWidget(self.tempo_edit)
        tempo_layout.addWidget(up_btn)
        tempo_container.setLayout(tempo_layout)

        # Kit dropdown (populate from subfolders)
        kit_container = QWidget()
        kit_layout = QHBoxLayout()
        kit_layout.setContentsMargins(0, 0, 0, 0)
        kit_layout.setSpacing(4)

        kit_label = QLabel("Kit:")
        kit_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
            }
        """)
        self.kit_button = QToolButton()
        self.kit_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.kit_button.setFixedWidth(100)
        self.kit_button.setStyleSheet("""
            QToolButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 2px 4px;
                text-align: left;
            }
            QToolButton::menu-indicator {
                image: none;
            }
        """)
        self.kit_button.setText(self.current_kit)

        self.kit_menu = QMenu()
        self.kit_menu.setStyleSheet("""
            QMenu {
                background-color: #2e2e2e;
                color: #FFFFFF;
                border: 1px solid #444444;
            }
            QMenu::item {
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #007AFF;
            }
        """)
        for name in self.kit_names:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, nm=name: self.set_kit(nm))
            self.kit_menu.addAction(action)
        self.kit_button.setMenu(self.kit_menu)

        kit_layout.addWidget(kit_label)
        kit_layout.addWidget(self.kit_button)
        kit_container.setLayout(kit_layout)

        # File controls: load & save
        file_container = QWidget()
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)

        self.load_btn = make_icon_button("folder.png")
        self.save_btn = make_icon_button("save.png")
        file_layout.addWidget(self.load_btn)
        file_layout.addWidget(self.save_btn)
        file_container.setLayout(file_layout)

        self.save_btn.clicked.connect(self.save_sequence)
        self.load_btn.clicked.connect(self.load_sequence)

        # Arrange bottom row
        bottom_h.addStretch()
        bottom_h.addWidget(playback_container)
        bottom_h.addStretch()
        bottom_h.addWidget(tempo_label)
        bottom_h.addWidget(tempo_container)
        bottom_h.addStretch()
        bottom_h.addWidget(kit_container)
        bottom_h.addStretch()
        bottom_h.addWidget(file_container)
        bottom_h.addStretch()

        central_v.addLayout(bottom_h)
        central_v.addSpacing(10)

        # Sequencer timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.advance_step)

        # Finally, load the default kit now that sample_labels exist
        self.load_kit(self.current_kit)
        # Warm up the audio device
        try:
            # Open a tiny OutputStream and close it immediately to force PortAudio to initialize
            warmup = sd.OutputStream(samplerate=44100, channels=1)
            warmup.start()
            warmup.stop()
            warmup.close()
        except Exception:
            pass
        try:
            dummy = np.zeros(256, dtype="float32")
            sd.play(dummy, samplerate=44100, blocking=True)
        except Exception:
            pass


    def load_kit(self, kit_name: str):
        """Load exactly 8 .wav samples from 'samples/kit_name'."""
        self.samples.clear()
        kit_path = os.path.join("samples", kit_name)
        wav_files = sorted(glob.glob(os.path.join(kit_path, "*.wav")))

        for path in wav_files[:8]:
            data, sr = sf.read(path, dtype="float32")
            name = os.path.splitext(os.path.basename(path))[0]
            if data.ndim == 2:
                data = data.mean(axis=1)
            self.samples.append((name, data, sr))

        # Pad with silent if fewer than 8
        while len(self.samples) < 8:
            self.samples.append((f"Empty {len(self.samples)+1}", np.zeros(1, dtype="float32"), 44100))

        # Update labels
        for r in range(self.num_rows):
            self.sample_labels[r].setText(self.samples[r][0])

    def set_kit(self, kit_name: str):
        """Switch to a different kit: stop playback, reload samples/labels."""
        if kit_name == self.current_kit:
            return
        self.current_kit = kit_name
        self.kit_button.setText(kit_name)
        self.stop_playback()
        self.load_kit(kit_name)

    def increase_tempo(self):
        try:
            val = int(self.tempo_edit.text())
        except ValueError:
            val = 120
        val = min(val + 1, 999)
        self.tempo_edit.setText(str(val))

    def decrease_tempo(self):
        try:
            val = int(self.tempo_edit.text())
        except ValueError:
            val = 120
        val = max(val - 1, 0)
        self.tempo_edit.setText(str(val))

    def clear_sequence(self):
        """Uncheck all step buttons and reset highlighting."""
        for row in range(self.num_rows):
            for col in range(self.num_cols):
                btn = self.step_buttons[row][col]
                btn.setChecked(False)
                btn.setProperty("highlighted", False)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        self.current_step = -1

    def save_sequence(self):
        """Prompt user to save current grid, volume, and pitch state (CSV)."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sequence", "", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, mode="w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                header = [f"Step{c}" for c in range(self.num_cols)] + ["Volume", "Pitch"]
                writer.writerow(["Sample"] + header)

                for r in range(self.num_rows):
                    row_data = [self.sample_labels[r].text()]
                    for c in range(self.num_cols):
                        row_data.append("1" if self.step_buttons[r][c].isChecked() else "0")
                    row_data.append(str(self.vol_dials[r].value()))
                    row_data.append(str(self.pitch_dials[r].value()))
                    writer.writerow(row_data)
        except Exception:
            pass

    def load_sequence(self):
        """Prompt user to load CSV and restore grid, volume, and pitch."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Sequence", "", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, mode="r", newline="") as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)

                for r, line in enumerate(rows[1 : self.num_rows + 1]):
                    # Steps
                    for c in range(self.num_cols):
                        checked = (line[1 + c] == "1")
                        btn = self.step_buttons[r][c]
                        btn.setChecked(checked)
                        btn.setProperty("highlighted", False)
                        btn.style().unpolish(btn)
                        btn.style().polish(btn)
                    # Volume
                    vol_val = int(line[1 + self.num_cols])
                    self.vol_dials[r].setValue(vol_val)
                    # Pitch
                    pitch_val = int(line[2 + self.num_cols])
                    self.pitch_dials[r].setValue(pitch_val)
        except Exception:
            pass

    def start_playback(self):
        """Begin stepping at the given tempo."""
        if self.closing:
            return
        if not self.is_playing:
            try:
                tempo = int(self.tempo_edit.text())
                if tempo <= 0:
                    raise ValueError
            except ValueError:
                tempo = 120
                self.tempo_edit.setText("120")
            interval_ms = int((60000 / tempo) / 4)
            self.timer.start(interval_ms)
            self.is_playing = True

    def stop_playback(self):
        """Stop stepping and reset to beginning."""
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
        if 0 <= self.current_step < self.num_cols:
            self._clear_column_highlight(self.current_step)
        self.current_step = -1

    def advance_step(self):
        """Advance to next column, play sounds, highlight."""
        if self.closing:
            return
        prev = self.current_step
        if 0 <= prev < self.num_cols:
            self._clear_column_highlight(prev)

        self.current_step = (self.current_step + 1) % self.num_cols
        step_idx = self.current_step
        self._highlight_column(step_idx)

        for row in range(self.num_rows):
            btn = self.step_buttons[row][step_idx]
            if btn.isChecked() and row < len(self.samples):
                name, data, sr = self.samples[row]
                vol = self.vol_dials[row].value() / 100.0
                semitone = self.pitch_dials[row].value()
                rate = 2 ** (semitone / 12.0)
                original_length = len(data)
                new_length = int(np.round(original_length / rate))
                if new_length < 1:
                    new_length = 1
                indices = np.linspace(0, original_length - 1, new_length)
                resampled = np.interp(indices, np.arange(original_length), data).astype("float32")
                data_to_play = (resampled * vol).astype("float32")
                threading.Thread(
                    target=self.play_sample, args=(data_to_play, sr), daemon=True
                ).start()

    def play_sample(self, data, sr):
        """Play a sample via OutputStream at original samplerate."""
        if self.closing:
            return
        arr = np.array(data, dtype="float32")
        try:
            with sd.OutputStream(samplerate=sr, channels=1) as stream:
                stream.write(arr)
        except Exception:
            sd.play(arr, sr, blocking=False)

    def _highlight_column(self, col_idx: int):
        """Set property 'highlighted' True on all buttons in column."""
        for row in range(self.num_rows):
            btn = self.step_buttons[row][col_idx]
            btn.setProperty("highlighted", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _clear_column_highlight(self, col_idx: int):
        """Clear 'highlighted' property on column, restoring checked/unchecked style."""
        for row in range(self.num_rows):
            btn = self.step_buttons[row][col_idx]
            btn.setProperty("highlighted", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def closeEvent(self, event):
        self.closing = True
        self.stop_playback()
        sd.stop()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QToolTip {
            background-color: #222222;
            color: #FFFFFF;
            border: none;
        }
    """)
    window = DrumMachineGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
