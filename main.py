from pyrogram import Client, filters, enums
import asyncio
import os
import json
from datetime import datetime
from flask import Flask
import threading

# === CONFIG ===
API_ID = 27117940
API_HASH = "0b2ecae57fafbca7da3042a735b2774a"
SESSION_NAME = os.environ.get("SESSION_NAME", "userbot_session")

BROADCAST_DELAY = 4000  # detik
BROADCAST_FILE = "broadcasts.json"
STATE_FILE = "state.json"
GROUPS_FILE = "groups.json"

# === Inisialisasi Pyrogram ===
app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

# === Flask server untuk uptime ===
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "✅ Userbot aktif dan berjalan dengan baik di Koyeb!"

def run_web():
    port = int(os.environ.get("PORT", 3000))
    web_app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# === Helpers ===
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

broadcasts = load_json(BROADCAST_FILE, [])
state = load_json(STATE_FILE, {"running": False})
groups = load_json(GROUPS_FILE, [])

# === Ambil daftar grup ===
async def refresh_groups():
    found = []
    async for dialog in app.get_dialogs():
        if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            found.append(dialog.chat.id)
    save_json(GROUPS_FILE, found)
    return found

async def send_report(text):
    try:
        await app.send_message("me", text)
    except Exception as e:
        print("⚠️ Gagal kirim laporan:", e)

# === Simpan pesan ===
@app.on_message(filters.command("savepesan") & filters.me)
async def save_message(client, message):
    if not message.reply_to_message:
        await message.reply("⚠️ Balas ke pesan yang ingin disimpan dulu.")
        return
    data = {"chat_id": message.reply_to_message.chat.id, "message_id": message.reply_to_message.id}
    broadcasts.append(data)
    save_json(BROADCAST_FILE, broadcasts)
    await message.reply(f"✅ Pesan disimpan. Total: {len(broadcasts)}")

# === Lihat daftar pesan ===
@app.on_message(filters.command("listpesan") & filters.me)
async def list_message(client, message):
    if not broadcasts:
        await message.reply("📭 Belum ada pesan tersimpan.")
        return
    text = "📋 Pesan tersimpan:\n"
    for i, b in enumerate(broadcasts):
        text += f"{i}. chat_id={b['chat_id']} msg_id={b['message_id']}\n"
    await message.reply(text)

# === Hapus pesan ===
@app.on_message(filters.command("delpesan") & filters.me)
async def delete_message(client, message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Gunakan format: /delpesan <index>")
        return
    idx = int(parts[1])
    if idx < 0 or idx >= len(broadcasts):
        await message.reply("Index tidak valid.")
        return
    broadcasts.pop(idx)
    save_json(BROADCAST_FILE, broadcasts)
    await message.reply(f"✅ Pesan index {idx} dihapus.")

# === Cek grup ===
@app.on_message(filters.command("cekgrup") & filters.me)
async def check_groups(client, message):
    global groups
    groups = await refresh_groups()
    if not groups:
        await message.reply("❌ Tidak ada grup ditemukan.")
        return
    text = f"✅ Ditemukan {len(groups)} grup:\n"
    for g in groups[:10]:
        chat = await app.get_chat(g)
        text += f"- {chat.title} ({g})\n"
    await message.reply(text)

# === Broadcast utama ===
async def do_broadcast():
    global groups
    if not groups:
        groups = await refresh_groups()
    if not groups:
        await send_report("⚠️ Tidak ada grup ditemukan.")
        return

    total_success = total_fail = 0
    for b in broadcasts:
        for g in groups:
            try:
                await app.forward_messages(chat_id=g, from_chat_id=b["chat_id"], message_ids=b["message_id"])
                total_success += 1
            except Exception:
                total_fail += 1
                continue

    waktu = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    await send_report(f"📣 Broadcast selesai ({waktu})\n✅ Sukses: {total_success}\n❌ Gagal: {total_fail}\n👥 Total grup: {len(groups)}")

# === Auto broadcast loop ===
async def auto_broadcast():
    while state.get("running", False):
        await do_broadcast()
        await asyncio.sleep(BROADCAST_DELAY)

# === Start broadcast ===
@app.on_message(filters.command("startbroadcast") & filters.me)
async def start_broadcast(client, message):
    if state.get("running", False):
        await message.reply("ℹ️ Broadcast sudah berjalan.")
        return
    state["running"] = True
    save_json(STATE_FILE, state)
    await message.reply(f"▶️ Broadcast dimulai. Mengulang tiap {BROADCAST_DELAY//60} menit.")
    asyncio.create_task(auto_broadcast())

# === Stop broadcast ===
@app.on_message(filters.command("stopbroadcast") & filters.me)
async def stop_broadcast(client, message):
    if not state.get("running", False):
        await message.reply("ℹ️ Broadcast sudah berhenti.")
        return
    state["running"] = False
    save_json(STATE_FILE, state)
    await message.reply("⏹ Broadcast dihentikan.")

# === Status ===
@app.on_message(filters.command("status") & filters.me)
async def status(client, message):
    await message.reply(f"🔎 Status: {'ON' if state['running'] else 'OFF'}\n🗂 Pesan tersimpan: {len(broadcasts)}\n👥 Grup terdeteksi: {len(groups)}\n⏱ Delay antar siklus: {BROADCAST_DELAY//60} menit")

# === Jalankan ===
print("🚀 Jalankan userbot & Flask uptime server...")
keep_alive()
app.run()
