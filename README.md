# Wplace-s-Kokyo-Monitor-for-Discord
Wplaceの皇居をモニタリングするDiscordのBotです。
- Python 3.11 以上
- Windows / macOS / Linux
- 必要ライブラリ: discord.py, websockets, Pillow
## 使い方
コードを確認して、`TOKEN,Channel ID,uri`を設定してください。

!nowで、リアルタイムのWplace内の皇居の画像や見本との差分、パーセンテージ、取得時刻を取得•送信します。

また、指定されたIDのchannelで、10%ごとの区切りをまたぐ変化があった際に!nowの情報を送信します。
