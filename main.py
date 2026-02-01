# ============================================================================
# RoboMaster Radar SDR Receiver - main
# ============================================================================
import json
import argparse
import signal
import time
from pathlib import Path

import numpy as np

from utils import setup_logger
from sdr_driver import SDRDriver
from dsp_processor import DSPProcessor
from packet_decoder import PacketDecoder

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

running = True


def signal_handler(sig, frame):
    global running
    print("\nExit signal received.")
    running = False


def load_config(config_path="config.json"):
    path = Path(__file__).parent / config_path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_frequency_plan(config):
    game = config.get("game_settings", {})
    receive_team = game.get("receive_team")

    if receive_team == "red":
        freqs = config["frequencies"]["blue_team_receiving_red"]
        mode_str = "Receive RED broadcast"
    elif receive_team == "blue":
        freqs = config["frequencies"]["red_team_receiving_blue"]
        mode_str = "Receive BLUE broadcast"
    else:
        # fallback: original logic (my_team listens to opponent)
        team = game.get("my_team", "red")
        if team == "red":
            freqs = config["frequencies"]["red_team_receiving_blue"]
            mode_str = "Red team listening to BLUE"
        else:
            freqs = config["frequencies"]["blue_team_receiving_red"]
            mode_str = "Blue team listening to RED"

    level = game.get("target_jammer_level", 1)
    enable_jammer = config.get("processing", {}).get("enable_jammer", False)

    freq_broadcast = freqs["broadcast_freq"]
    if not enable_jammer:
        freq_jammer = freq_broadcast
    elif level == 0:
        freq_jammer = freq_broadcast
    elif level == 1:
        freq_jammer = freqs["jammer_1_freq"]
    elif level == 2:
        freq_jammer = freqs["jammer_2_freq"]
    elif level == 3:
        freq_jammer = freqs["jammer_3_freq"]
    else:
        freq_jammer = freq_broadcast

    center_freq = (freq_broadcast + freq_jammer) / 2.0
    offset_bc = freq_broadcast - center_freq
    offset_jam = freq_jammer - center_freq

    return mode_str, center_freq, offset_bc, offset_jam


class SpectrumPlot:
    def __init__(self, sample_rate, update_hz=5):
        self.sample_rate = sample_rate
        self.update_interval = 1.0 / max(update_hz, 1)
        self.last_update = 0.0
        self.enabled = MATPLOTLIB_AVAILABLE
        if not self.enabled:
            return
        plt.ion()
        self.fig, self.ax = plt.subplots()
        self.line, = self.ax.plot([], [])
        self.ax.set_title("Spectrum")
        self.ax.set_xlabel("Frequency (kHz)")
        self.ax.set_ylabel("Power (dB)")
        self.ax.grid(True)

    def update(self, samples):
        if not self.enabled:
            return
        now = time.time()
        if now - self.last_update < self.update_interval:
            return
        self.last_update = now

        n = 4096
        if len(samples) < n:
            return
        x = samples[:n]
        window = np.hanning(n)
        spec = np.fft.fftshift(np.fft.fft(x * window))
        power = 20 * np.log10(np.abs(spec) + 1e-12)
        freqs = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / self.sample_rate)) / 1e3

        self.line.set_data(freqs, power)
        self.ax.set_xlim(freqs[0], freqs[-1])
        self.ax.set_ylim(np.max(power) - 80, np.max(power) + 5)
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


def main():
    global running
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    logger = setup_logger()

    try:
        raw_config = load_config(args.config)
        mode_str, center_freq, offset_bc, offset_jam = calculate_frequency_plan(raw_config)

        raw_config["center_frequency_hz"] = center_freq

        logger.info(mode_str)
        logger.info(f"Center frequency: {center_freq/1e6:.4f} MHz")
        logger.info(f"Broadcast offset: {offset_bc/1e3:.1f} kHz | Jammer offset: {offset_jam/1e3:.1f} kHz")

        driver = SDRDriver(raw_config)
        dsp = DSPProcessor(raw_config)
        decoder = PacketDecoder()

        show_spec = raw_config.get("logging", {}).get("show_spectrum", False)
        update_hz = raw_config.get("logging", {}).get("spectrum_update_hz", 5)
        spectrum = SpectrumPlot(raw_config["sdr_settings"]["sample_rate_sps"], update_hz) if show_spec else None

        enable_jammer = raw_config.get("processing", {}).get("enable_jammer", False)

        driver.open()
        time.sleep(1)
        logger.info("Receiver started.")

        last_stat = time.time()
        pkt_count = 0

        while running:
            samples = driver.read_samples()
            if len(samples) == 0:
                continue

            if spectrum:
                spectrum.update(samples)

            bits_bc = dsp.process_channel(samples, offset_bc)
            if len(bits_bc) > 0:
                packets = decoder.decode(bits_bc, "broadcast")
                if packets:
                    pkt_count += len(packets)
                    decoder.print_packets(packets)

            if enable_jammer and abs(offset_bc - offset_jam) > 1000:
                bits_jam = dsp.process_channel(samples, offset_jam)
                if len(bits_jam) > 0:
                    packets = decoder.decode(bits_jam, "jammer")
                    if packets:
                        pkt_count += len(packets)
                        decoder.print_packets(packets)

            now = time.time()
            if now - last_stat >= 1.0:
                logger.info(f"Packets/s: {pkt_count}")
                pkt_count = 0
                last_stat = now

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if "driver" in locals():
            driver.close()


if __name__ == "__main__":
    main()
