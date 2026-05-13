# yt-subtranslate

YouTube 视频下载 + 字幕翻译工具。自动下载视频、提取/识别英文字幕、AI 翻译为中文、合成双语字幕视频。

## 技术栈

![](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![](https://img.shields.io/badge/yt--dlp-download-red)
![](https://img.shields.io/badge/Whisper-STT-orange)
![](https://img.shields.io/badge/DeepSeek-translate-green)
![](https://img.shields.io/badge/FFmpeg-composite-purple)
![](https://img.shields.io/badge/uv-package--manager-lightgrey?logo=astral)

## 工作流程

```
YouTube URL → yt-dlp 下载视频
                ↓
         有英文字幕? ──是→ 手动字幕 > 自动字幕
                │
                否 → 提取音频 → Whisper 语音识别
                                        ↓
                           [可选] AI 英文字幕纠错
                                        ↓
                           [可选] YouTube 原生中文字幕
                                        ↓
                              AI 翻译 (DeepSeek) → 中文字幕
                                                        ↓
                                         FFmpeg 合成 → 字幕视频
```

## 快速开始

### 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- FFmpeg（需在 PATH 中可用）

### 安装

```bash
git clone https://github.com/ezhpry/yt-subtranslate.git && cd yt-subtranslate
uv sync
```

### 设置 API Key

翻译依赖 DeepSeek API（兼容 OpenAI 格式）：

```bash
set DEEPSEEK_API_KEY=sk-your-key-here
```

### 使用

```bash
# 一键全流程（默认双语字幕）
uv run python main.py https://www.youtube.com/watch?v=xxxxx

# 纯中文字幕
uv run python main.py https://www.youtube.com/watch?v=xxxxx --subtitle-mode chinese

# 使用 YouTube 原生中文字幕（跳过 AI 翻译）
uv run python main.py https://www.youtube.com/watch?v=xxxxx --native-zh

# AI 纠错英文字幕（修复自动字幕中的识别错误）
uv run python main.py https://www.youtube.com/watch?v=xxxxx --correct-en

# 禁用翻译缓存（强制重新翻译）
uv run python main.py https://www.youtube.com/watch?v=xxxxx --no-cache

# 指定分辨率 / Whisper 模型 / 翻译批次大小
uv run python main.py https://www.youtube.com/watch?v=xxxxx --resolution 720p
uv run python main.py https://www.youtube.com/watch?v=xxxxx --whisper-model medium
uv run python main.py https://www.youtube.com/watch?v=xxxxx --chunk-size 20

# 查看所有选项
uv run python main.py --help
```

### 输出

```
output/<video_id>/
├── <video_id>.mp4          # 原始下载视频
├── en.srt                   # 英文字幕
├── zh.srt                   # 中文字幕
├── output_burned.mp4        # 硬编码双语字幕视频
└── output_zh.srt            # 软字幕文件
```

### 断点续跑

Pipeline 自动检测中间产物，已存在的文件会跳过，支持中断后继续：

```bash
# 删除某阶段产物即可重跑该阶段
rm output/<video_id>/en.srt   # 重新获取字幕
rm output/<video_id>/zh.srt   # 重新翻译
```

## 开发

```bash
# 运行测试
uv run python -m pytest tests/ -v

# 运行各阶段 Demo
uv run python demo/01-yt_dlp_download_demo.py
uv run python demo/02-subtitle_extraction_demo.py
uv run python demo/03-translation_demo.py
uv run python demo/04-video_composition_demo.py
uv run python demo/05-cli_integration_demo.py
```

## 项目结构

```
yt-subtranslate/
├── main.py                   # CLI 入口
├── pipeline/pipeline.py      # 管道编排器
├── downloader/               # yt-dlp 视频下载
├── subtitler/                # 字幕提取 + Whisper 识别
├── translator/               # DeepSeek AI 翻译
├── compositor/               # FFmpeg 视频合成
├── models/types.py           # 共享数据类型
├── config/settings.py        # 配置默认值
└── utils/                    # cache, retry, logger, ...
```
