# ============================================================================
# DSP processor: DDC + LPF + 4-RRC-FSK demod
# ============================================================================
import numpy as np
import scipy.signal as signal
import logging


class DSPProcessor:
    def __init__(self, config: dict):
        self.logger = logging.getLogger("radar.dsp")
        self.sample_rate = config["sdr_settings"]["sample_rate_sps"]
        self.symbol_rate = config["demodulation"]["symbol_rate_bps"]
        self.fsk_dev = config["demodulation"]["fsk_deviation_hz"]
        self.filter_bw = config["demodulation"]["filter_bandwidth_hz"]
        self.rrc_alpha = config["demodulation"].get("rrc_alpha", 0.25)
        self.rrc_num_taps = config["demodulation"].get("rrc_num_taps", 88)

        self.samples_per_symbol = int(round(self.sample_rate / self.symbol_rate))

        # pre-design filters
        self.taps = self._design_lpf()
        self.rrc_taps = self._design_rrc()

    def _design_lpf(self):
        cutoff = self.filter_bw / 2.0
        nyquist = self.sample_rate / 2.0
        num_taps = 101
        return signal.firwin(num_taps, cutoff / nyquist, window="hamming")

    def _design_rrc(self):
        alpha = self.rrc_alpha
        sps = self.samples_per_symbol
        num_taps = int(self.rrc_num_taps)

        # Use exact num_taps length, symmetric around 0.
        if num_taps % 2 == 0:
            t = (np.arange(-num_taps / 2 + 0.5, num_taps / 2 + 0.5, dtype=np.float64) / sps)
        else:
            t = (np.arange(-(num_taps // 2), num_taps // 2 + 1, dtype=np.float64) / sps)
        taps = np.zeros_like(t)
        for i, ti in enumerate(t):
            if ti == 0.0:
                taps[i] = 1.0 - alpha + (4 * alpha / np.pi)
            elif alpha != 0 and abs(ti) == 1.0 / (4 * alpha):
                taps[i] = (alpha / np.sqrt(2)) * (
                    (1 + 2 / np.pi) * np.sin(np.pi / (4 * alpha))
                    + (1 - 2 / np.pi) * np.cos(np.pi / (4 * alpha))
                )
            else:
                numerator = np.sin(np.pi * ti * (1 - alpha)) + 4 * alpha * ti * np.cos(
                    np.pi * ti * (1 + alpha)
                )
                denominator = np.pi * ti * (1 - (4 * alpha * ti) ** 2)
                taps[i] = numerator / denominator

        taps = taps / np.sum(taps)
        return taps.astype(np.float64)

    def process_channel(self, wideband_samples: np.ndarray, freq_shift_hz: float) -> np.ndarray:
        if len(wideband_samples) == 0:
            return np.array([])

        # 1) DDC to baseband
        t = np.arange(len(wideband_samples))
        lo = np.exp(-1j * 2 * np.pi * (freq_shift_hz / self.sample_rate) * t)
        baseband = wideband_samples * lo

        # 2) LPF
        filtered = signal.lfilter(self.taps, 1.0, baseband)

        # 3) FM discriminator -> instantaneous frequency (Hz)
        phase = np.angle(filtered)
        dphi = np.angle(np.exp(1j * np.diff(phase)))
        freq_inst = dphi * self.sample_rate / (2 * np.pi)

        # 4) RRC matched filter
        freq_filt = signal.lfilter(self.rrc_taps, 1.0, freq_inst)

        # 5) symbol sampling
        total_delay = (len(self.taps) - 1) // 2 + (len(self.rrc_taps) - 1) // 2
        if total_delay >= len(freq_filt):
            return np.array([])

        idxs = np.arange(total_delay, len(freq_filt), self.samples_per_symbol)
        sym_samples = freq_filt[idxs]
        if len(sym_samples) == 0:
            return np.array([])

        # 6) 4-FSK decision (00->-3, 01->-1, 10->1, 11->3)
        abs_vals = np.abs(sym_samples)
        scale = np.percentile(abs_vals, 90) / 3.0 if len(abs_vals) > 10 else self.fsk_dev
        if scale <= 0:
            scale = self.fsk_dev
        levels = np.array([-3, -1, 1, 3]) * scale

        idx = np.argmin(np.abs(sym_samples.reshape(-1, 1) - levels.reshape(1, -1)), axis=1)
        bit_map = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.uint8)
        bits = bit_map[idx].reshape(-1)
        return bits
