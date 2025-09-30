import discord
import asyncio
import websockets
import json
import struct
from datetime import datetime
import io
from PIL import Image
# --- 設 定 し て く だ さ い  ---
DISCORD_BOT_TOKEN = ""  # こ こ に Discord Botの ト ー ク ン を 入 力
TARGET_CHANNEL_ID =   # こ こ に 通 知 を 送 り た い チ ャ ン ネ ル の IDを 入力
# --------------------
# --- グ ロ ー バ ル 変 数  (Botの 状 態 管 理 ) ---
latest_live_image = None
latest_diff_image = None
latest_diff_percentage = 0.0
latest_timestamp = None
last_notified_percentage_tier = -1 # 通 知 済 み の 10%区 切 り
# --- WebSocketか ら 画 像 と メ タ デ ー タ を 受 信 し て 処 理 す る  ---
async def receive_wplace_data():
    global latest_live_image, latest_diff_image, latest_diff_percentage, latest_timestamp, last_notified_percentage_tier
    uri = "" # ここにWebSocketのURLなどを設定
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("wplaceサ ー バ ー に 接 続 し ま し た 。 ")
                while True:
                    message = await websocket.recv()
                    if isinstance(message, str):
                        data = json.loads(message)
                        if data.get("type") == "metadata":
                            latest_diff_percentage = data.get("diff_percentage", 0.0)
                            latest_timestamp = datetime.now()
                            print(f"メ タ デ ー タ 受 信 : 差 分 率 ={latest_diff_percentage}%")
                            # 差 分 率 が 10%の 区 切 り を 越 え た か チ ェ ッ ク
                            current_tier = int(latest_diff_percentage // 10)
                            if current_tier != last_notified_percentage_tier:
                                # 0%に 戻 っ た 場 合 や 、 10,20,30...と 変 化 し た 場 合 に 通知
                                if latest_diff_percentage < last_notified_percentage_tier * 10:
                                     # 差 分 が 減 っ て 閾 値 を ま た い だ 時
                                     last_notified_percentage_tier = current_tier
                                     await send_update_notification(f"🪽 差 分 が **{current_tier * 10}%台 **ま で 減 少 し ま し た 。 ")
                                elif latest_diff_percentage >= (last_notified_percentage_tier + 1) * 10:
                                     # 差 分 が 増 え て 閾 値 を ま た い だ 時
                                     last_notified_percentage_tier = current_tier
                                     await send_update_notification(f"🚨 差 分 が **{current_tier * 10}%台 **に 増 加 し ま し た ！ ")
                    elif isinstance(message, bytes):
                        header_format = '<BI'  # (type_id: 1 byte, length: 4 bytes)
                        header_size = struct.calcsize(header_format)
                        if len(message) > header_size:
                            type_id, length = struct.unpack(header_format, message[:header_size])
                            image_bytes = message[header_size:]
                            if type_id == 2: # IMAGE_TYPE_LIVE
                                latest_live_image = io.BytesIO(image_bytes)
                                print("ラ イ ブ 画 像 を 受 信 し ま し た 。 ")
                            elif type_id == 3: # IMAGE_TYPE_DIFF
                                latest_diff_image = io.BytesIO(image_bytes)
                                print("差 分 画 像 を 受 信 し ま し た 。 ")
        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError)
as e:
            print(f"wplaceサ ー バ ー へ の 接 続 に 失 敗 し ま し た : {e}。 5秒 後 に 再 接 続 し ま
す 。 ")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"予 期 せ ぬ エ ラ ー が 発 生 し ま し た : {e}")
            await asyncio.sleep(5)
# --- Discord Botの ロ ジ ッ ク  ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
@client.event
async def on_ready():
    print(f'{client.user} と し て Discordに ロ グ イ ン し ま し た 。 ')
    # WebSocket受 信 タ ス ク を 開 始
    asyncio.create_task(receive_wplace_data())
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content == '!now':
        await send_status_update(message.channel)
async def send_status_update(channel):
    """現 在 の 状 況 を 送 信 す る """
    if latest_live_image and latest_diff_image and latest_timestamp:
        # 画 像 を 先 頭 に 戻 す
        latest_live_image.seek(0)
        latest_diff_image.seek(0)
        # --- 画 像 結 合 処 理  ---
        try:
            img1 = Image.open(latest_live_image)
            img2 = Image.open(latest_diff_image)
            dst_width = img1.width + img2.width
            dst_height = max(img1.height, img2.height)
            combined_img = Image.new('RGBA', (dst_width, dst_height))
            combined_img.paste(img1, (0, 0))
            combined_img.paste(img2, (img1.width, 0))
            combined_io = io.BytesIO()
            combined_img.save(combined_io, format='PNG')
            combined_io.seek(0)
            files = [discord.File(combined_io, filename="wplace_combined.png")]
            image_url = "attachment://wplace_combined.png"
        except Exception as e:
            print(f"画 像 結 合 中 に エ ラ ー が 発 生 し ま し た : {e}")
            # 結 合 に 失 敗 し た 場 合 は 、 以 前 の 方 法 で 送 信
            latest_live_image.seek(0)
            latest_diff_image.seek(0)
            files = [
                discord.File(latest_live_image, filename="live_image.png"),
                discord.File(latest_diff_image, filename="diff_image.png")
            ]
            image_url = None
        # --- 結 合 処 理 こ こ ま で  ---
        embed = discord.Embed(
            title="Wplace 監 視 情 報 ",
            description=f"差 分 率 : **{latest_diff_percentage:.2f}%**",
            color=discord.Color.blue(),
            timestamp=latest_timestamp
        )
        embed.set_footer(text="取 得 時 刻 ")
        if image_url:
            embed.set_image(url=image_url)
        await channel.send(embed=embed, files=files)
    else:
        await channel.send("ま だ 監 視 デ ー タ を 取 得 で き て い ま せ ん 。 し ば ら く 待 っ て か
ら も う 一 度 お 試 し く だ さ い 。 ")
async def send_update_notification(change_message):
    """差 分 率 が 変 化 し た と き に 特 定 の チ ャ ン ネ ル に 通 知 す る """
    channel = client.get_channel(TARGET_CHANNEL_ID)
    if channel:
        print(f"#{channel.name} に 差 分 率 の 変 化 を 通 知 し ま す 。 ")
        await channel.send(f"【 差 分 率 変 動 】  {change_message}")
        await send_status_update(channel)
    else:
        print(f"エ ラ ー : チ ャ ン ネ ル ID {TARGET_CHANNEL_ID} が 見 つ か り ま せ ん 。 ")
# --- Botの 実 行  ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN" or TARGET_CHANNEL_ID == 123456789012345678:
        print("エ ラ ー : Discord Botの ト ー ク ン ま た は チ ャ ン ネ ル IDが 設 定 さ れ て い ま せ
ん 。 ")
        print("`discord_bot.py`フ ァ イ ル を 編 集 し て 、 DISCORD_BOT_TOKENと TARGET_CHANNEL_IDを 設 定 し て く だ さ い 。 ")
    else:
        client.run(DISCORD_BOT_TOKEN)
