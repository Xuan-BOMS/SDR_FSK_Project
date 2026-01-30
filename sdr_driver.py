# ============================================================================
# 硬件封装层 (修正版：支持从内存传入配置)
# ============================================================================
import numpy as np
from typing import Optional, Union
import logging

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32
    SOAPY_AVAILABLE = True
except ImportError:
    SOAPY_AVAILABLE = False
    print("警告: SoapySDR 未安装")

class SDRDriver:
    def __init__(self, config: dict):
        """
        初始化 SDR 驱动
        Args:
            config: 已经在 main.py 中计算好频率的配置字典
        """
        self.cfg = config
        self.logger = logging.getLogger("sdr_fsk.driver")
        
        self.sdr = None
        self.rx_stream = None
        self._opened = False
        
        # 直接从传入的 config 中读取参数 (这些参数在 main.py 已经被修改过)
        self.center_freq = self.cfg["center_frequency_hz"]
        self.sample_rate = self.cfg["sdr_settings"]["sample_rate_sps"]
        self.gain = self.cfg["sdr_settings"]["gain_db"]
        
        # 这里的带宽设置跟采样率一致，确保不滤除干扰信号
        self.bandwidth = self.sample_rate 
        self.buffer_size = self.cfg["processing"]["buffer_size"]
        
        self.logger.info(f"SDR 驱动初始化目标: 频率={self.center_freq/1e6:.4f}MHz, 采样率={self.sample_rate/1e6}Msps")

    def open(self):
        if not SOAPY_AVAILABLE:
            raise RuntimeError("SoapySDR 未安装")
        
        try:
            # 1. 连接设备
            driver_name = self.cfg["device"]["driver"]
            # 如果是 sdrplay，通常参数是 driver=sdrplay
            args = f"driver={driver_name}" 
            if self.cfg["device"]["args"]:
                args += "," + self.cfg["device"]["args"]

            self.logger.info(f"正在连接设备: {args}")
            self.sdr = SoapySDR.Device(args)
            
            channel = 0
            
            # 2. 设置参数
            self.sdr.setSampleRate(SOAPY_SDR_RX, channel, self.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_RX, channel, self.center_freq)
            self.sdr.setGain(SOAPY_SDR_RX, channel, self.gain)
            
            # 尝试设置带宽
            try:
                self.sdr.setBandwidth(SOAPY_SDR_RX, channel, self.bandwidth)
            except:
                self.logger.warning("设备不支持手动设置带宽，使用默认值")

            # 3. 创建流
            self.rx_stream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32, [channel])
            self.sdr.activateStream(self.rx_stream)
            
            self._opened = True
            self.logger.info("SDR 设备启动成功")
            
        except Exception as e:
            self.logger.error(f"打开设备失败: {e}")
            raise RuntimeError(f"无法打开 SDR: {e}")

    def read_samples(self, num_samples: Optional[int] = None) -> np.ndarray:
        if not self._opened:
            raise RuntimeError("设备未打开")
        
        if num_samples is None:
            num_samples = self.buffer_size
        
        buff = np.zeros(num_samples, dtype=np.complex64)
        sr = self.sdr.readStream(self.rx_stream, [buff], num_samples)
        
        if sr.ret < 0:
            # 这里的 log 太多会刷屏，可以注释掉
            # self.logger.warning(f"读取错误: {sr.ret}")
            return np.array([], dtype=np.complex64)
        
        return buff[:sr.ret]

    def close(self):
        if self._opened and self.sdr:
            try:
                self.sdr.deactivateStream(self.rx_stream)
                self.sdr.closeStream(self.rx_stream)
                self.sdr = None
                self._opened = False
                self.logger.info("SDR 设备已关闭")
            except:
                pass
