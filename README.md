# Local Music Metadata Fetcher

[![GitHub Issues](https://img.shields.io/github/issues/yourusername/reponame?color=critical)](https://github.com/yourusername/reponame/issues)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

> Fetches metadata for local music files from major Chinese music platforms

## ✨ Features
- **Multi-platform support**: Retrieves song covers and lyrics from:
  - NetEase Cloud Music (网易云音乐)
  - KuGou Music (酷狗音乐)
  - Kuwo Music (酷我音乐)
- **Interactive UI**:
  - Right-click on cover/lyrics areas to toggle displays
  - Automatic metadata matching by local file name

## 👨‍💻 Project Status
> **Maintainer Note**  
> As a full-time undergraduate student with limited maintenance capacity, this project benefits from community contributions. Current priorities:
> - 🐛 Bug fixes for metadata fetching
> - 🔄 Platform API updates
> - 🚀 Performance optimizations

## 🤝 How to Contribute
We welcome developers to help improve this project! Here's how you can contribute:

1. **Report Issues**  
   Found a bug? [Open an issue]([https://github.com/yourusername/reponame/issues](https://github.com/PythonBeginners0/Local-music-player/issues)) with:
   - Platform name (NetEase/KuGou/Kuwo)
   - Error logs
   - Sample file details

2. **Improve Crawlers**  
   Help maintain up-to-date platform parsers:
   ```bash
   git checkout -b feature/kuwo-api-update
   # Modify crawlers/kuwo_parser.py
