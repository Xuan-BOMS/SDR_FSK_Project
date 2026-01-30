# RoboMaster 雷达信息波解调系统 (SDR_FSK_Project)

本项目旨在通过软件定义无线电 (SDR) 接收并解调 RoboMaster 比赛中的雷达信息波信号。系统能够自动计算接收频率，同时监听广播源和干扰源，并解析出比赛相关的关键数据包。

## 1. 系统架构

系统主要由以下三个模块组成：

1.  **SDR Driver (`sdr_driver.py`)**: 
    *   负责与 SDR 硬件 (如 SDRPlay, HackRF, RTL-SDR) 进行交互。
    *   根据配置设置采样率、增益和中心频率。
    *   提供原始 IQ 采样数据流。

2.  **DSP Processor (`dsp_processor.py`)**: 
    *   接收原始 IQ 数据。
    *   执行数字信号处理，包括频移、滤波、解调 (FSK)。
    *   支持多通道处理，可同时解调广播源和干扰源信号。

3.  **Packet Decoder (`packet_decoder.py`)**: 
    *   接收解调后的比特流。
    *   寻找帧头 (SOF)，校验 CRC8 和 CRC16。
    *   根据 Cmd ID 解析具体的数据包内容。

## 2. 频率接收切换逻辑

为了同时接收“广播源”和“干扰源”的信号，系统采用了**中心频率偏移法**：

1.  **读取配置**: 从 `config.json` 中读取己方颜色 (红/蓝) 和目标干扰等级 (0-3)。
2.  **确定频率**:
    *   根据队伍颜色确定监听的频率表 (红方听蓝方，蓝方听红方)。
    *   获取广播源频率 (`broadcast_freq`)。
    *   根据干扰等级获取对应的干扰源频率 (`jammer_freq`)。
3.  **计算中心频率**:
    *   `Center Freq = (Broadcast Freq + Jammer Freq) / 2`
    *   这样可以确保两个信号都落在 SDR 的接收带宽内。
4.  **数字下变频 (DDC)**:
    *   在 DSP 处理阶段，分别将广播源和干扰源的信号搬移到基带进行解调。
    *   `Offset_Broadcast = Broadcast Freq - Center Freq`
    *   `Offset_Jammer = Jammer Freq - Center Freq`

## 3. 数据包解析 (Packet Decoder)

系统支持解析 RoboMaster 2026 协议 V1.1.0 中的多种数据包，特别是新增的 **雷达无线链路 (SDR)** 数据。

### 3.1 常规链路 (串口转发)
*   **0x0001 比赛状态**: 比赛阶段、剩余时间等。
*   **0x0003 机器人血量**: 己方各单位血量。
*   **0x020B 地面机器人位置**: (旧版/通用) 地面单位坐标。
*   **0x020E 雷达自主决策**: 双倍易伤状态、密钥修改权限等。

### 3.2 雷达无线链路 (SDR 专属) - **核心更新**
这些数据由场上信号源直接广播，包含对方队伍的关键信息：

*   **0x0A01 对方机器人位置**: 
    *   包含对方英雄、工程、步兵、空中、哨兵的 (X, Y) 坐标。
*   **0x0A02 对方机器人血量**: 
    *   包含对方所有主要单位的当前血量。
*   **0x0A03 对方机器人剩余发弹量**: 
    *   包含对方各单位的剩余允许发弹量。
*   **0x0A04 对方队伍宏观状态**: 
    *   金币数量。
    *   各增益点 (补给区、高地、飞坡等) 的占领状态。
*   **0x0A05 对方各机器人当前增益**: 
    *   详细列出对方每个单位的 回血、冷却、防御、易伤、攻击 增益。
    *   包含哨兵的当前姿态。
*   **0x0A06 对方干扰波密钥**: 
    *   获取对方的 6 字节 ASCII 密钥，用于反干扰策略。

## 4. 使用说明

### 4.1 环境依赖
*   Python 3.8+
*   SoapySDR (及对应硬件驱动)
*   Python 库: `numpy`, `scipy` (见 `requirements.txt`)

### 4.2 配置文件 (`config.json`)
在运行前，请确保 `config.json` 中的以下设置正确：
*   `game_settings`: 设置己方队伍 (`my_team`) 和目标干扰等级 (`target_jammer_level`)。
*   `device`: 设置 SDR 驱动名称 (如 `sdrplay`, `rtlsdr`)。

### 4.3 运行
```bash
python main.py --config config.json
```

程序启动后将自动计算频率，连接 SDR 设备，并在控制台输出解析到的数据包信息。

## 5. 文件列表
*   `main.py`: 程序入口，负责调度各模块。
*   `sdr_driver.py`: SDR 硬件驱动封装。
*   `dsp_processor.py`: 信号处理核心算法。
*   `packet_decoder.py`: 协议解析与数据包解包。
*   `utils.py`: 日志等通用工具。
*   `config.json`: 系统配置文件。
