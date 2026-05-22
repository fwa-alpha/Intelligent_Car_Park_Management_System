Intelligent Car Park Management System
项目简介 (Project Overview)
本项目旨在设计并实现一个基于 Raspberry Pi 与边缘计算视觉的智能停车场管理系统。系统通过实时监控、车牌识别（OCR）及 PLC 式逻辑控制，实现了停车场入口/出口的自动化管理、车位实时统计及计费核算，有效解决了在预算受限环境下实现工业级自动化控制的工程问题。

核心功能 (Key Features)
自动化门禁控制：集成红外传感器，实现车辆入场的自动识别与道闸开闭。

边缘视觉识别：部署基于 OpenCV 与 Tesseract 的视觉处理管线，采用统计投票策略（Statistical Voting OCR）提高识别精度。

PLC 逻辑映射：采用非阻塞式架构（Non-blocking Execution），在 Raspberry Pi 上高效模拟 PLC 梯形逻辑（Ladder Logic），确保实时控制响应。

智能状态互锁：系统内置“满位互锁”功能，实时监控车位余量并联动警示系统。

技术栈 (Tech Stack)
硬件：Raspberry Pi 4B, 红外/超声波传感器, 伺服舵机, 报警 LED

软件：Python 3.13, OpenCV, Tesseract OCR

架构模式：状态机模型 (FSM), 梯形逻辑映射 (Ladder Logic Modeling)
