import asyncio, json, os, random, time, uuid, sys
import logging
import subprocess
import shutil
import struct
import threading
import queue
from datetime import datetime

try:
    import opuslib
    OPUSLIB_AVAILABLE = True
except ImportError:
    OPUSLIB_AVAILABLE = False
    print("[!] opuslib chưa cài: pip install opuslib")
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import httpx
import thunderFF_pb2
from aiohttp import web

try:
    from google_play_scraper import app as play_scraper
except Exception:
    play_scraper = None

from Chu_Giang import *

try:
    from GPackGEN import TAO_PACKET
except Exception:
    TAO_PACKET = None

logging.getLogger("asyncio").setLevel(logging.CRITICAL)

def _silence_asyncio_exc(loop, context):
    msg = context.get("message", "")
    if any(x in msg for x in ("socket.send()", "Broken pipe", "ConnectionResetError", "closed")):
        return
    loop.default_exception_handler(context)

try:
    asyncio.get_event_loop().set_exception_handler(_silence_asyncio_exc)
except Exception:
    pass

DEVICES_FILE = "devices.json"
ACCOUNTS_FILE = "pitien_mac_bikini.json"
STATS_FILE = "stats.json"
AES_KEY = b"Yg&tc%DEuh6%Zc^8"
AES_IV = b"6oyZDr22E3ychjM%"
BASE_HEADERS = {
    "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "Connection": "Keep-Alive", "Accept-Encoding": "gzip",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Unity-Version": "2018.4.12f1",
    "X-GA-SV": "1789535859", "X-GA": "v1 1", "ReleaseVersion": "OB55",
}
HEARTBEAT_INTERVAL = 3.0
HTTP_HOST  = "127.0.0.1"
HTTP_PORT  = 8080
APP_ID     = "FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97"
VOICE_UUID = "682761f7-3f39-4912-b019-ced851732362"

BOTS = {}
CURRENT_TEAMCODE = None

# ── Set lưu teamcode đã join thành công – tránh join lại ──────────────────────
JOINED_TEAMCODES: set = set()

STATS = {
    "team_created": 0, "squad_joined": 0, "ghost_sent": 0,
    "hunt_success": 0, "hunt_fail": 0,
    "last_update": None, "history": [],
}

# ── Phát nhạc khi thành công ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════
# GVOICE PIPELINE  (ported từ main-1.py)
# ═══════════════════════════════════════════════════════

def _pb_encode_sync(fields: dict) -> bytes:
    """Encode protobuf đơn giản (sync version)."""
    def _vi(n):
        out = bytearray()
        while True:
            b = n & 0x7F; n >>= 7
            if n: b |= 0x80
            out.append(b)
            if not n: break
        return bytes(out)
    parts = []
    for k, v in fields.items():
        k = int(k)
        if isinstance(v, bool):
            parts.append(_vi(k << 3 | 0) + _vi(1 if v else 0))
        elif isinstance(v, int):
            parts.append(_vi(k << 3 | 0) + _vi(v))
        elif isinstance(v, dict):
            nb = _pb_encode_sync(v)
            parts.append(_vi(k << 3 | 2) + _vi(len(nb)) + nb)
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(_vi(k << 3 | 2) + _vi(len(ev)) + ev)
    return b"".join(parts)


class VoiceDispatcherGRTC:
    def __init__(self, dispatcher_ip="148.222.82.60", dispatcher_port=6674):
        self.dispatcher_ip   = dispatcher_ip
        self.dispatcher_port = dispatcher_port

    def _decode_varint(self, data, idx):
        result = shift = 0
        while idx < len(data):
            b = data[idx]; result |= (b & 0x7F) << shift; idx += 1
            if not (b & 0x80): break
            shift += 7
        return result, idx

    async def get_voice_server(self, uid, room_id, uuid_str):
        req = _pb_encode_sync({
            1: str(uid), 2: room_id, 3: uuid_str, 5: "voice",
            6: "android", 7: "1.0.0", 8: 1, 9: "VN",
            10: APP_ID, 11: "voiceb", 12: "24094RAD4G", 13: 2, 14: "mt6855",
        })
        try:
            reader, writer = await asyncio.open_connection(self.dispatcher_ip, self.dispatcher_port)
            writer.write(struct.pack(">I", len(req)) + req)
            await writer.drain()
            resp = b""
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=2.0)
                    if chunk: resp += chunk
                    if len(resp) >= 8: break
                except asyncio.TimeoutError:
                    print("[GVOICE STEP2] ❌ Timeout"); return None, None
            writer.close()
            if len(resp) < 8: return None, None
            idx = 4
            voice_ip = voice_port = None
            if idx < len(resp) and resp[idx] == 0x0A:
                idx += 1; ip_len, idx = self._decode_varint(resp, idx)
                voice_ip = resp[idx:idx+ip_len].decode(); idx += ip_len
            if idx < len(resp) and resp[idx] == 0x10:
                idx += 1; voice_port, _ = self._decode_varint(resp, idx)
            if not voice_ip:
                print("[GVOICE STEP2] ❌ Không parse được IP"); return None, None
            print(f"[GVOICE STEP2] ✅ {voice_ip}:{voice_port}")
            return voice_ip, voice_port
        except Exception as e:
            print(f"[GVOICE STEP2] ❌ {e!r}"); return None, None


class VoiceTCPHandshakeGRTC:
    def __init__(self, voice_ip, voice_tcp_port):
        self.voice_ip       = voice_ip
        self.voice_tcp_port = voice_tcp_port

    def _decode_varint(self, data, idx):
        r = s = 0
        while idx < len(data):
            b = data[idx]; r |= (b & 0x7F) << s; idx += 1
            if not (b & 0x80): break
            s += 7
        return r, idx

    async def execute_handshake(self, uid, room_id, uuid_str):
        req = _pb_encode_sync({
            1: str(uid), 2: room_id, 3: uuid_str, 5: "voice",
            6: "android", 7: "1.0.0", 8: 1, 9: "VN",
            10: APP_ID, 11: "voiceb", 12: "24094RAD4G", 13: 2, 14: "mt6855",
        })
        print(f"[GVOICE STEP3] Voice TCP {self.voice_ip}:{self.voice_tcp_port} ...")
        try:
            reader, writer = await asyncio.open_connection(self.voice_ip, self.voice_tcp_port)
            writer.write(struct.pack(">I", len(req)) + req)
            await writer.drain()
            r1 = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            if len(r1) < 8: writer.close(); return None, None, None, None, None
            # Parse response
            fields = {}; idx = 4
            while idx < len(r1):
                if idx >= len(r1): break
                tag, idx = self._decode_varint(r1, idx)
                fn, wt = tag >> 3, tag & 0x07
                if wt == 0:
                    val, idx = self._decode_varint(r1, idx); fields[fn] = val
                elif wt == 2:
                    ln, idx = self._decode_varint(r1, idx)
                    fields[fn] = r1[idx:idx+ln]; idx += ln
                else: break
            f1_raw   = fields.get(1, b"")
            f3       = fields.get(3, 0)
            udp_port = fields.get(4, 0)
            f13_32   = fields.get(13, 0) & 0xFFFFFFFF
            fixed_2  = fields.get(2, 0x00002662)
            ssrc     = f13_32 if f13_32 > 0 else (f3 if f3 > 0 else random.randint(0x10000000, 0x7FFFFFFF))
            f3_val   = f3 & 0xFFFFFFFF
            # Echo response back
            echo_pb = (bytes([0x0A, len(f1_raw)]) + f1_raw) if f1_raw else r1
            writer.write(struct.pack(">I", len(echo_pb)) + echo_pb)
            await writer.drain()
            print(f"[GVOICE STEP3] ✅ UDP={udp_port} SSRC=0x{ssrc:08X}")
            return udp_port, ssrc, fixed_2, reader, writer
        except Exception as e:
            print(f"[GVOICE STEP3] ❌ {e!r}")
            return None, None, None, None, None


class OpusVoiceClientGRTC:
    def __init__(self, voice_ip, voice_udp_port, ssrc, fixed_2=0x00002662):
        self.voice_ip        = voice_ip
        self.voice_udp_port  = voice_udp_port
        self.ssrc            = ssrc & 0xFFFFFFFF
        self.fixed_2         = fixed_2 & 0xFFFFFFFF
        self.seq_num         = random.randint(1, 0xFFFF)
        self.timestamp       = random.randint(1, 0xFFFFFFFF)
        self.is_running      = False
        self.sock            = __import__("socket").socket(__import__("socket").AF_INET, __import__("socket").SOCK_DGRAM)
        if OPUSLIB_AVAILABLE:
            self.encoder = opuslib.Encoder(48000, 1, opuslib.APPLICATION_AUDIO)
        print(f"[OpusClient] {voice_ip}:{voice_udp_port} ssrc=0x{ssrc:08x}")

    def send_open_mic(self, ka_seq=None, ka_ts=None):
        seq = ka_seq if ka_seq is not None else (self.seq_num & 0xFFFFFF)
        ts  = ka_ts  if ka_ts  is not None else (self.timestamp & 0xFFFFFFFF)
        pkt = bytearray()
        pkt.append(0x71)
        pkt += (seq & 0xFFFFFF).to_bytes(3, "big")
        pkt += struct.pack(">I", ts & 0xFFFFFFFF)
        pkt += struct.pack(">I", self.ssrc & 0xFFFFFFFF)
        pkt += struct.pack(">I", 0x00000311)
        self.sock.sendto(bytes(pkt), (self.voice_ip, self.voice_udp_port))

    def build_opus_packet(self, opus_data: bytes) -> bytes:
        hdr = bytearray([0x80, 0x78])
        hdr.extend(struct.pack(">H", self.seq_num & 0xFFFF))
        hdr.extend(struct.pack(">I", self.timestamp & 0xFFFFFFFF))
        hdr.extend(struct.pack(">I", self.ssrc & 0xFFFFFFFF))
        hdr.extend(struct.pack(">I", self.fixed_2 & 0xFFFFFFFF))
        self.seq_num  += 1
        self.timestamp += 960
        return bytes(hdr) + opus_data

    def _producer_thread(self, mp3_file, q):
        cmd = ["ffmpeg", "-i", mp3_file,
               "-filter:a", "volume=4.8,alimiter=limit=0.95",
               "-ar", "48000", "-ac", "1", "-f", "s16le", "-"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frame = 960 * 2  # 960 samples × 2 bytes (s16le mono)
        while True:
            raw = proc.stdout.read(frame)
            if len(raw) < frame:
                q.put(None); break
            if OPUSLIB_AVAILABLE:
                q.put(self.encoder.encode(raw, 960))
            else:
                q.put(raw)

    def _audio_loop(self, mp3_file, on_finish=None):
        q = queue.Queue(maxsize=50)
        threading.Thread(target=self._producer_thread, args=(mp3_file, q), daemon=True).start()
        self.is_running = True
        sent = 0
        try:
            while True:
                try:   opus = q.get(timeout=0.5)
                except queue.Empty: continue
                if opus is None:
                    print(f"[Audio] Hết nhạc ({sent} frames)"); break
                try: self.sock.sendto(self.build_opus_packet(opus), (self.voice_ip, self.voice_udp_port))
                except OSError as e: print(f"[Audio] sock: {e}")
                sent += 1
                time.sleep(0.019)
        except Exception as e:
            print(f"[Audio] Fatal: {e}")
        finally:
            self.is_running = False
            if on_finish:
                try: on_finish()
                except Exception as e: print(f"[Audio] on_finish err: {e}")

    def start_music_stream(self, mp3_file="s1.mp3", on_finish=None):
        if not OPUSLIB_AVAILABLE:
            print("[OpusClient] opuslib không có, bỏ qua stream"); return
        if self.is_running:
            return
        mp3_files = [f for f in os.listdir(".") if f.lower().endswith(".mp3")]
        if not mp3_files:
            print("[Audio] Không có file .mp3")
            if on_finish:
                try: on_finish()
                except: pass
            return
        chosen = random.choice(mp3_files)
        print(f"[🎵] Stream nhạc: {chosen}")
        threading.Thread(target=self._audio_loop, args=(chosen, on_finish), daemon=True).start()


async def trigger_music_pipeline(uid: int, room_id: str, mp3_file: str = None):
    """Chạy full GVoice pipeline: Dispatcher → TCP Handshake → UDP stream nhạc."""
    _uuid = VOICE_UUID

    async def _tcp_cmd(writer, cmd_id):
        try:
            clean = str(room_id).replace("VN_", "")
            token = f"{APP_ID}VN_{clean}"
            f1b   = _pb_encode_sync({1: cmd_id, 2: 0, 3: 0})
            f3b   = _pb_encode_sync({1: str(uid), 2: 1})
            pl    = _pb_encode_sync({1: f1b, 2: token, 3: f3b})
            writer.write(struct.pack(">I", len(pl)) + pl)
            await writer.drain()
        except Exception as e:
            print(f"  [TCP TX] CMD={cmd_id} err: {e}")

    async def _agora_join(writer):
        try:
            pkt = bytes.fromhex("feffff7f")
            writer.write(struct.pack(">I", len(pkt)) + pkt)
            await writer.drain()
        except Exception: pass

    # STEP 2
    disp = VoiceDispatcherGRTC()
    v_ip, v_tcp_port = await disp.get_voice_server(uid, room_id, _uuid)
    if not v_ip or not v_tcp_port:
        print("[GVOICE] ❌ Không lấy được voice server"); return

    await asyncio.sleep(0.1)

    # STEP 3
    hs = VoiceTCPHandshakeGRTC(v_ip, v_tcp_port)
    udp_port, ssrc, fixed_2, vr, vw = await hs.execute_handshake(uid, room_id, _uuid)
    if not udp_port or not ssrc:
        print("[GVOICE] ❌ Handshake thất bại"); return

    # STEP 4
    await _tcp_cmd(vw, 9)
    await asyncio.sleep(0.05)
    await _agora_join(vw)

    opus = OpusVoiceClientGRTC(v_ip, udp_port, ssrc, fixed_2)
    opus.send_open_mic()
    await asyncio.sleep(0.1)

    await _tcp_cmd(vw, 24)
    await _tcp_cmd(vw, 35)

    last_ka  = time.time()
    music_ok = False

    while not vw.is_closing():
        now = time.time()
        if now - last_ka >= 18:
            await _tcp_cmd(vw, 9); last_ka = now
        try:
            hdr    = await asyncio.wait_for(vr.readexactly(4), timeout=1.0)
            pl_len = struct.unpack(">I", hdr)[0]
            if pl_len == 0: continue
            if pl_len > 500_000:
                print(f"[GVOICE] pl_len={pl_len} bất thường, ngắt"); break
            payload = await asyncio.wait_for(vr.readexactly(pl_len), timeout=10.0)

            if pl_len > 100 and not music_ok:
                print("[GVOICE] Member info → kích nhạc")
                await _agora_join(vw)
                await _tcp_cmd(vw, 33)
                music_ok = True
                done_event = asyncio.Event()
                def _done():
                    print("[GVOICE] Nhạc xong")
                    opus.is_running = False
                    try: vw.close()
                    except: pass
                    done_event.set()
                opus.start_music_stream(on_finish=_done)
            else:
                # Keepalive echo CMD 10/11
                cmd_id = None
                if len(payload) >= 3 and payload[0] == 0x0A:
                    il = payload[1]
                    if il >= 2 and payload[2] == 0x08:
                        cmd_id = payload[3] if len(payload) > 3 else None
                if cmd_id in (10, 11):
                    vw.write(struct.pack(">I", len(payload)) + payload)
                    await vw.drain()
                    if cmd_id == 11:
                        await asyncio.sleep(0.1)
                        opus.send_open_mic()
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"[GVOICE TCP] Ngắt: {e}"); break

    print("[GVOICE] Pipeline kết thúc")


# ═══════════════════════════════════════════════════════

def play_music(teamcode: str, owner: int):
    """Phát 1 file .mp3 ngẫu nhiên trong thư mục hiện tại (không thoát chương trình)."""
    mp3_files = [f for f in os.listdir(".") if f.lower().endswith(".mp3")]
    if mp3_files:
        chosen = random.choice(mp3_files)
        print(f"[🎵] Nhạc: {chosen}")
        try:
            for player in ["mpg123", "ffplay", "aplay"]:
                if shutil.which(player):
                    cmd = (["ffplay", "-nodisp", "-autoexit", chosen]
                           if player == "ffplay" else [player, chosen])
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    break
            else:
                print("[!] Không tìm thấy mpg123/ffplay/aplay để phát nhạc")
        except Exception as e:
            print(f"[!] Phát nhạc lỗi: {e}")
    else:
        print("[!] Không có file .mp3 nào")

    print(f"[✅] JOIN! code={teamcode} owner={owner}")

# ─────────────────────────────────────────────────────────────────────────────

def load_stats():
    global STATS
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            for k in STATS:
                if k in d:
                    STATS[k] = d[k]
        except:
            pass

def save_stats():
    STATS["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(STATS, f, indent=2, ensure_ascii=False)
    except:
        pass

def bump_stat(field, n=1):
    STATS[field] = STATS.get(field, 0) + n
    save_stats()

def add_history(entry):
    STATS["history"].append(entry)
    if len(STATS["history"]) > 500:
        STATS["history"] = STATS["history"][-500:]
    save_stats()

def _get_channel(account_id):
    """Kênh K của bot = account_id % 4"""
    return int(account_id) % 4

def _yy_valid_for_channel(k):
    """Danh sách 2 chữ số cuối hợp lệ cho kênh K"""
    return [str(yy).zfill(2) for yy in range(0, 100) if yy % 4 == k]

def _teamcode_matches_channel(teamcode, k):
    """Teamcode có thuộc kênh K không (dựa trên 2 chữ số cuối YY % 4 == k)"""
    if len(teamcode) < 2:
        return False
    suffix = teamcode[-2:]
    try:
        return int(suffix) % 4 == k
    except:
        return False

def _enc_varint(n):
    if n < 0:
        return b""
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)

def _build_proto(fields):
    parts = []
    for k, v in fields.items():
        if isinstance(v, bool):
            parts.append(_enc_varint(k << 3 | 0) + _enc_varint(1 if v else 0))
        elif isinstance(v, int):
            parts.append(_enc_varint(k << 3 | 0) + _enc_varint(v))
        elif isinstance(v, dict):
            nested = _build_proto(v)
            parts.append(_enc_varint(k << 3 | 2) + _enc_varint(len(nested)) + nested)
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(_enc_varint(k << 3 | 2) + _enc_varint(len(ev)) + ev)
    return b"".join(parts)

def _encrypt_bytes(b):
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(b, AES.block_size))

def get_device(uid):
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                devices = json.load(f)
        except:
            pass
    if uid in devices:
        return devices[uid]
    pool = [
        ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
        ("Xiaomi", "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
        ("Realme", "RMX3700", "Mali-G710", "Android OS 14 / API-34"),
    ]
    brand, model, gpu, os_ver = random.choice(pool)
    dev = {
        "unique_device_id": f"Google|{uuid.uuid4()}",
        "brand": brand, "model": model, "gpu_renderer": gpu,
        "system_software": os_ver,
        "screen_width": random.choice([1080, 1440, 720]),
        "screen_height": random.choice([2400, 3200, 1600]),
        "screen_dpi": str(random.randint(300, 420)),
        "memory": random.randint(2800, 6500),
        "processor_details": f"ARM64 FP ASIMD AES | {random.randint(2200, 3200)} | {random.randint(6, 12)}",
        "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}",
    }
    devices[uid] = dev
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=2)
    except:
        pass
    return dev

http_client = httpx.AsyncClient(verify=False, timeout=15.0,
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20))

async def _get_playstore_version():
    if play_scraper is None:
        return "1.132.11"
    loop = asyncio.get_event_loop()
    try:
        r = await loop.run_in_executor(None, lambda: play_scraper("com.dts.freefireth", lang="vi", country="vn"))
        return r.get("version", "1.132.11")
    except:
        return "1.132.11"

async def get_version_config():
    av = await _get_playstore_version()
    url = (f"https://version.ggwhitehawk.com/live/ver.php?version={av}"
           f"&lang=hi&device=android&channel=android&appstore=googleplay"
           f"&region=VN&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    try:
        r = await http_client.get(url)
        r.raise_for_status()
        d = r.json()
        return d.get("latest_release_version"), d.get("remote_version"), d.get("server_url")
    except:
        return None

async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    data = {
        "uid": uid, "password": password, "response_type": "token", "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067",
    }
    for _ in range(5):
        try:
            r = await http_client.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                d = r.json()
                oid, at, pf = d.get("open_id"), d.get("access_token"), d.get("platform", 4)
                if oid and at:
                    return oid, at, pf
        except:
            pass
        await asyncio.sleep(0.5)
    return None

async def build_majorlogin_payload(open_id, access_token, platform, client_version, dev):
    p = {
        3: str(datetime.now())[:-7], 4: "free fire", 5: 4, 7: str(client_version),
        8: str(dev.get("system_software")), 9: "Handheld", 10: "Viettel", 11: "WIFI",
        12: int(dev.get("screen_width")), 13: int(dev.get("screen_height")),
        14: str(dev.get("screen_dpi")), 15: dev.get("processor_details"),
        16: int(dev.get("memory")), 17: str(dev.get("gpu_renderer")),
        18: "OpenGL ES 3.2 build 25.1@6715691", 19: str(dev.get("unique_device_id")),
        20: str(dev.get("client_ip")), 21: "vn", 22: str(open_id), 23: "4",
        24: "Handheld", 25: str(dev.get("model")), 26: "VN", 29: str(access_token),
        30: 1, 41: "Viettel", 42: "WIFI", 57: "7428b253defc164018c604a1ebbfebdf",
        60: 233141, 61: 172590, 62: 902, 64: 173114, 65: 233141, 66: 173114,
        67: 233141, 73: 3,
        74: "/data/app/~~OOxSMPtiZSaEIgYJjPoHOg==/com.dts.freefireth-KkAAAdjU2FG5Ts4HwgDgCw==/lib/arm64",
        76: 1,
        77: "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~OOxSMPtiZSaEIgYJjPoHOg==/com.dts.freefireth-KkAAAdjU2FG5Ts4HwgDgCw==/base.apk",
        78: 3, 79: 2, 81: "64", 83: "2019121229", 85: 3, 86: "OpenGLES2", 87: 8191,
        88: 4, 90: "Quận Một", 91: "SG", 92: 10968, 93: "android",
        94: "KqsHT0Q7h333TG5PRgHHMPeY52YAbiB2/CUjX28YaEK6kGm0ieehpzRhEeZ1N/GP2hWAoRRtOvXk8DqwEQgsJ2n+ohtc18X5bJZ6IS8WNFZf7sZI",
        95: 111107, 96: '{"cur_rate":[60,90,120],"support_etc2":false}', 97: 1,
        99: "4", 100: "4", 102: "4a501646550a090965", 103: 1, 104: 1070, 105: 1,
        106: "https://dl.ak.freefiremobile.com/live/ABHotUpdates/|https://core-ak.freefiremobile.com/live/ABHotUpdates/|9a9a493d643462570dc50320b28533d0",
        107: "1.af7c82fd80a978e6",
    }
    return _encrypt_bytes(_build_proto(p))

async def send_majorlogin(data, release_version, server_url):
    url = f"{server_url}MajorLogin" if server_url.endswith("/") else f"{server_url}/MajorLogin"
    h = BASE_HEADERS.copy()
    h["ReleaseVersion"] = str(release_version)
    try:
        r = await http_client.post(url, headers=h, data=data)
    except Exception as e:
        print(f"[-] MajorLogin error: {e}")
        return None
    if r.status_code != 200:
        return None
    c = r.content
    for off in [0, 64] + list(range(128)):
        try:
            m = thunderFF_pb2.MajorLoginRes()
            m.ParseFromString(c[off:])
            if m.region and m.token:
                return m
        except:
            continue
    return None

async def send_getlogin(data, base_url, token, release_version):
    url = f"{base_url.rstrip('/')}/GetLoginData"
    h = BASE_HEADERS.copy()
    h["ReleaseVersion"] = release_version
    h["Authorization"] = f"Bearer {token}"
    h["Host"] = "clientbp.ppmainecoonghj.com"
    try:
        r = await http_client.post(url, headers=h, data=data)
    except Exception as e:
        print(f"[-] GetLoginData error: {e}")
        return None
    if r.status_code != 200:
        return None
    c = r.content
    rp = thunderFF_pb2.GetLoginDataRes()
    ok = False
    try:
        rp.ParseFromString(c)
        if rp.functional_addrs or rp.informational_addrs:
            ok = True
    except:
        pass
    if not ok:
        for off in range(min(128, len(c))):
            try:
                cand = thunderFF_pb2.GetLoginDataRes()
                cand.ParseFromString(c[off:])
                if cand.functional_addrs or cand.informational_addrs:
                    rp = cand
                    break
            except:
                continue
    return rp

def build_tcp_startup(account_id, token, server_time, key, iv, region="VN"):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(token.encode(), AES.block_size)).hex()
    enc_len = f"{len(enc)//2:08x}"
    reg = str(region).upper() if region else "VN"
    pfx = "7119" if reg == "ID" else ("7114" if reg == "IND" else "7115")
    return f"{pfx}{uid_hex}{ts_hex}00000000{enc_len}{enc}"

def build_keepalive(region="VN"):
    reg = str(region).upper() if region else "VN"
    if reg == "ID":
        return bytes.fromhex("0219")
    if reg == "IND":
        return bytes.fromhex("0214")
    return bytes.fromhex("0215")

def _make_chat_packet(packet_type_byte, type_str, fields, key, iv):
    payload = _build_proto(fields)
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(payload, 16))
    enc_hex = encrypted.hex()

    length_hex = hex(len(enc_hex) // 2)[2:]
    padding = "0" * max(0, 8 - len(length_hex))
    return bytes.fromhex("%02x%s%s%s%s" % (packet_type_byte, type_str, padding, length_hex, enc_hex))

def JoinSq_original(code, K, V):
    skinz = {
        1: 4,
        2: {
            4: "\u0001\u0007\t\n\u000b\u0012\u0019 '",
            5: str(code), 6: 6, 8: 1,
            9: {
                1: "08FFF3BE903F27DF0203110111110000006B0003006800169194106F13CF106E4676251411010404dfe9e8b5ca3ca4f96a3119c00000004f03060301cacfa16d",
                2: 130,
                3: "tY_S\u0013\b\u0001M\u0002\u0000T\u0000\u0005\u000e\b\t\u0002\u0000\u0003U\u0003\u0001V\u000fR\u000e\tRQ\u0002\u0004\u0005US\u0003XS\u0005\u0001\u0002\u0011\u0001\u0002JuTAEN\u001e\u0002\u001c\u0002\u001f\u0013\b\u0003M\u001cDbz_Q@}p_QOgsC\u001dYVI\u0004UAAj_ga\u0004\u0012\u0000K\u001d\u0007_t\u0019b\bCx\u0002UeGat\u001fTTCBLER`\u0006\u0001\r\f\u0012\u0006\u0005N^^\u0002acH~r\u0004_\u0003RO|\u000bcd_@~`Rnqrgh\n\u0015\nL\\Nh\u0000~G\u000et\u0000eb]VQ\u0006t^F[ZIGxCdZD\u000b\u0011\u0002OA~LP@\u000fcSDyATQApaT^{|wa]\\\u0001E\u000f\u0013\nJfxve}\u0004J\u0003c{YL\u0007^^yDYQf\bhe\u0005_wg\r\u0010\u0007\bEHpX@||\u0002Z\\uTGyA\u0001JP\u0005t~VkTE\u0000J\\\u000b\u0013\nMr\u0018zTzK}qE]vnvwROuheYvwduvQ\r\u001a\u0005M\u0006z\u001dfXfzvHFc~dXUz}O\u001aB\u0005t\u0002i\u001co_\u0004\u0012\u0003\u0007J\u0006b\u0003\u000eqlfvbEstgu~wB\u0001v@`yI\u0002ZPx\f\u0014\u0003NR\u0002yBZvuD_cd\u0004q]lH]\u0007bD}pCe\t\u0004t\n",
                4: "w^_R", 6: 11, 7: "\u0014\u0004aqrg\u0015\u0013",
                8: "1.132.1", 9: 3, 10: 2,
                11: "\u0003bbSQ6wxegh9qAdV2KyoVleA17yPmYF+yTnOrl+JMknmppeUBe5ZsiHueP2mZZ4KOs6b2Ail1S9z3qIeU9hGFZ2M6PP39/zjIc/RFVPAkgDagySswMVmYaPhkzU5IqNPow2843fyQUz9xI10NdMhl1WiI4Y6wCXBotiUS9wSgujQ4j0fWXUyklCxBWo8r27hyoGSVrPdTPXFMnJJpPRRFFmWqc3fWvMg+BNfxSRJOZRSrkzG0nNvSIJ4uZB2pqAlHIPEYx7bI6zsgwUVDiLZJKTUTyuCGbOd1DegDUFfazFesTG1LJknT5WhgzCsrBIy+f2l+LeJe5DW7wEwNaHambM7ECXcJcLIhB9kJJsW0tFvXkk3HSdcQ8N1K6wjSKWhpkW0kV8Zrjj0jkhS/7AZ6T9GJRIA827YDtTorBvbx1UkXjYrqYI1nSa2GaMexGnqlurc5DE3v1R+mUBI9GqmjEPgTSYVBxyeCdQMHaMXGtspAhvkiO84ToU87sP45pylDEfFOVoc/rcmdzWeqlYPsv6txKRtIHcb0cO+MoVShoU8ZUVRDF3znbqzVrscPIfplBaa79lwvQqzRubLl9XY="
            },
            11: {1: "IDC4", 2: 281, 3: "ME"},
            13: "fr", 16: "7OR\u0019", 20: "\b\u0015", 27: "\bH\u0010\u0003"
        }
    }
    return _make_chat_packet(0x05, "15", skinz, K, V)

def MakeGhostName():
    return "[b][c][1E90FF]Tiktok: [00FFFF]@jocker_90a"

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r") as f:
                accs = json.load(f)
            clean = []
            for a in accs:
                u = str(a.get("uid", "")).lstrip("> ").strip()
                p = str(a.get("password", "")).strip()
                if u and p:
                    clean.append({"uid": u, "password": p})
            return clean
        except:
            pass
    return []

def save_accounts(accs):
    try:
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(accs, f, indent=2)
    except:
        pass

async def _read_online(reader, uid_key):
    while True:
        try:
            data = await reader.read(65535)
            if not data:
                return
            if uid_key in BOTS:
                BOTS[uid_key]["data2"] = data
        except:
            return

async def _keepalive(writer, region):
    fail = 0
    while True:
        try:
            writer.write(build_keepalive(region))
            await writer.drain()
            fail = 0
            await asyncio.sleep(HEARTBEAT_INTERVAL)
        except Exception:
            fail += 1
            if fail >= 3:
                return
            await asyncio.sleep(1)

async def do_join_for(bot, teamcode, timeout=1.5):
    ow = bot["online_writer"]
    if not ow:
        return {"ok": False, "msg": "offline"}
    bot["data2"] = None
    JP = JoinSq_original(teamcode, bot["key"], bot["iv"])
    try:
        ow.write(JP)
        await ow.drain()
    except Exception as e:
        return {"ok": False, "msg": f"send err: {e}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        await asyncio.sleep(0.2)
        if not bot["data2"]:
            continue
        hex_raw = bot["data2"].hex()
        if not hex_raw.startswith("0500"):
            continue
        try:
            js = None
            for off in (10, 0, 8, 12):
                try:
                    cand = json.loads(await DeCode_PackEt(hex_raw[off:]))
                    if "5" in cand and "data" in cand["5"]:
                        js = cand
                        break
                except:
                    continue
            if not js:
                continue
            d5 = js["5"]["data"]
            owner = d5.get("1", {}).get("data") if isinstance(d5.get("1"), dict) else d5.get("1")
            squad = d5.get("31", {}).get("data") if isinstance(d5.get("31"), dict) else d5.get("31")
            if owner and squad:
                bump_stat("squad_joined")
                return {"ok": True, "owner": int(owner), "squad": str(squad)}
        except:
            continue
    return {"ok": False, "msg": "no packet"}

async def do_create_team5_for(bot, invite_uid=None):
    ow = bot["online_writer"]
    if not ow:
        return {"ok": False, "uid": str(bot["account_id"]), "msg": "offline"}
    if TAO_PACKET is None:
        return {"ok": False, "uid": str(bot["account_id"]), "msg": "GPackGEN chưa load"}
    region_code_map = {"VN": 0x19, "ID": 0x19, "IND": 0x14, "SG": 0x19, "TH": 0x19, "BR": 0x19, "ME": 0x19}
    my_region = bot["region"].upper()
    region_int = region_code_map.get(my_region, 0x19)
    try:
        logindata = {"1": bot["account_id"], "19": [{"1": region_int, "2": my_region}, {"1": 0x19, "2": "VN"}]}
        jsdata = {"iv": list(bot["iv"]), "key": list(bot["key"]),
                  "LockRegion": bot["region"], "UserNickName": bot["account_name"],
                  "ClientVersion": "1.132.6"}
        pack = TAO_PACKET(logindata, jsdata)
    except Exception as e:
        return {"ok": False, "uid": str(bot["account_id"]), "msg": f"TAO_PACKET init fail: {e}"}
    bot["data2"] = None
    # Delay nhỏ tránh rate-limit khi retry liên tục
    await asyncio.sleep(0.5)
    try:
        ow.write(pack.open_squad(5))
        await ow.drain()
    except Exception as e:
        return {"ok": False, "uid": str(bot["account_id"]), "msg": f"open err: {e}"}
    teamcode = None
    deadline = time.time() + 25
    _last_hex = None
    while time.time() < deadline:
        await asyncio.sleep(0.3)
        if not bot["data2"]:
            continue
        hex_raw = bot["data2"].hex()
        if not hex_raw.startswith("0500"):
            continue
        if hex_raw == _last_hex:
            continue  # packet chưa cập nhật, chờ tiếp
        _last_hex = hex_raw
        try:
            js = None
            for off in (10, 0, 8, 12, 14, 16, 18, 20, 6, 4, 2):
                try:
                    cand = json.loads(await DeCode_PackEt(hex_raw[off:]))
                    if "5" in cand and "data" in cand["5"]:
                        js = cand
                        break
                except:
                    continue
            if not js:
                # Log hex đầu để debug nếu vẫn fail
                print(f"[CREATE-DBG] {bot['account_name']} 0500 packet len={len(hex_raw)//2} hex[:40]={hex_raw[:40]}")
                continue
            d5 = js["5"]["data"]
            for fk in ("11", "17", "31", "14", "4", "5", "6", "33", "34", "7", "8", "9", "10"):
                if fk in d5:
                    v = d5[fk]
                    if isinstance(v, dict):
                        v = v.get("data")
                    if v and str(v).isdigit() and len(str(v)) >= 5:
                        teamcode = str(v)
                        break
            if teamcode:
                break
        except:
            continue
    if not teamcode:
        return {"ok": False, "uid": str(bot["account_id"]), "msg": "Không lấy được teamcode"}
    bump_stat("team_created")
    invited = None
    if invite_uid:
        try:
            ow.write(pack.invite_squad(int(invite_uid), 1))
            await ow.drain()
            await asyncio.sleep(0.15)
            ow.write(pack.invite_squad(int(invite_uid), 2))
            await ow.drain()
            invited = int(invite_uid)
        except:
            pass
    return {"ok": True, "uid": str(bot["account_id"]), "name": bot["account_name"],
            "teamcode": teamcode, "invited_uid": invited}

async def do_exit_team(bot):
    ow = bot["online_writer"]
    if not ow:
        return
    try:
        EXIT = await ExiT("000000", bot["key"], bot["iv"])
        ow.write(EXIT)
        await ow.drain()
    except:
        pass

async def start_one_bot(uid, password):
    vc = await get_version_config()
    if not vc:
        return None
    rel, cv, su = vc
    tg = await get_access_token(uid, password)
    if not tg:
        print(f"[-] {uid} token fail")
        return None
    oid, at, pf = tg
    dev = get_device(uid)
    lpd = await build_majorlogin_payload(oid, at, pf, cv, dev)
    ml = await send_majorlogin(lpd, rel, su)
    if ml is None:
        print(f"[-] {uid} MajorLogin fail")
        return None
    key = bytes(ml.aes_ak)
    iv = bytes(ml.iv_i)
    token = ml.token
    account_id = ml.account_id
    region = ml.region or "VN"
    server_time = ml.server_time
    gl = await send_getlogin(lpd, ml.url, token, rel)
    if gl is None or not gl.functional_addrs:
        print(f"[-] {uid} GetLoginData fail")
        return None
    account_name = gl.nickname or "Bot"
    online_ip, online_port = gl.functional_addrs.split(":")
    reader, writer = await asyncio.open_connection(online_ip, int(online_port))
    tcp_pkt = build_tcp_startup(account_id, token, server_time, key, iv, region)
    writer.write(bytes.fromhex(tcp_pkt))
    await writer.drain()
    BOTS[str(account_id)] = {
        "online_writer": writer, "data2": None,
        "key": key, "iv": iv, "account_id": account_id,
        "account_name": account_name, "region": region, "ready": True,
        "token": token, "rel": rel,
        "host": gl.functional_addrs.split(":")[0],
        "uid_orig": uid, "password_orig": password,
    }
    asyncio.create_task(_keepalive(writer, region))
    asyncio.create_task(_read_online(reader, str(account_id)))
    print(f"[OK] {account_name} | {account_id} | {region}")
    return BOTS[str(account_id)]

async def handle_stats(request):
    return web.json_response({"ok": True, "stats": STATS})

async def handle_status(request):
    return web.json_response({
        "count": len(BOTS),
        "current_teamcode": CURRENT_TEAMCODE,
        "bots": [{"uid": b["account_id"], "name": b["account_name"],
                  "region": b["region"], "ready": b["ready"]} for b in BOTS.values()],
    })

async def handle_ghost(request):
    if not BOTS:
        return web.json_response({"ok": False, "msg": "no bot"})
    tc = request.query.get("tc", "").strip()
    if not tc:
        return web.json_response({"ok": False, "msg": "Format: /ghost?tc=123456789"})
    bot = list(BOTS.values())[-1]
    ow = bot["online_writer"]
    key = bot["key"]
    iv = bot["iv"]
    ghost_name = MakeGhostName()
    bot["data2"] = None
    owner = None
    squad = None
    JP = JoinSq_original(tc, key, iv)
    try:
        ow.write(JP)
        await ow.drain()
    except Exception as e:
        return web.json_response({"ok": False, "msg": "join err: " + str(e)})
    deadline = time.time() + 15
    while time.time() < deadline:
        await asyncio.sleep(0.3)
        if not bot["data2"]:
            continue
        hex_raw = bot["data2"].hex()
        if not hex_raw.startswith("0500") or len(bot["data2"]) < 80:
            continue
        try:
            js = json.loads(await DeCode_PackEt(hex_raw[10:]))
            action_raw = js.get("4")
            if action_raw is None:
                continue
            try:
                action = int(action_raw.get("data") if isinstance(action_raw, dict) else action_raw)
            except (ValueError, TypeError):
                continue
            if action != 6:
                continue
            field5_raw = js.get("5")
            if not field5_raw:
                continue
            d5 = field5_raw.get("data") if isinstance(field5_raw, dict) else None
            if not d5:
                continue
            owner_raw = d5.get("1")
            if owner_raw is None:
                continue
            try:
                owner = int(owner_raw.get("data") if isinstance(owner_raw, dict) else owner_raw)
            except (ValueError, TypeError):
                continue
            f31 = d5.get("31")
            if isinstance(f31, dict):
                squad = f31.get("data")
            if owner and squad:
                break
        except:
            continue
    if not owner or not squad:
        try:
            EXIT = await ExiT("000000", key, iv)
            ow.write(EXIT)
            await ow.drain()
        except:
            pass
        return web.json_response({"ok": False, "msg": "Khong bat duoc owner/squad"})
    try:
        EXIT = await ExiT("000000", key, iv)
        ow.write(EXIT)
        await ow.drain()
        await asyncio.sleep(0.5)
    except Exception:
        pass
    try:
        GHOST = await Send_GhosTs(owner, ghost_name, squad, key, iv)
        if not GHOST:
            return web.json_response({"ok": False, "msg": "Ghost packet None"})
        ow.write(GHOST)
        await ow.drain()
        bump_stat("ghost_sent")
        print(f"[GHOST] ✅ owner={owner}")
    except Exception as e:
        return web.json_response({"ok": False, "msg": "ghost err: " + str(e)})
    return web.json_response({
        "ok": True, "uid": str(bot["account_id"]), "name": bot["account_name"],
        "owner_uid": owner, "squad_len": len(str(squad)), "ghost_name": ghost_name,
    })

async def start_http_server():
    app = web.Application()
    app.router.add_get("/status", handle_status)
    app.router.add_get("/ghost", handle_ghost)
    app.router.add_get("/stats", handle_stats)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()
    print(f"[HTTP] http://{HTTP_HOST}:{HTTP_PORT}")

async def _channel_loop(k, main_bot, ghost_bots, channel_cycles):
    """Loop riêng cho kênh K — main_bot tạo team, ghost_bots hunt."""
    print(f"[K{k}] Bắt đầu | main={main_bot['account_name']} | ghosts={[b['account_name'] for b in ghost_bots]}")

    # Học suffix thực tế từ vài lần tạo team đầu
    learned_suffix = None

    while True:
        channel_cycles[k] += 1
        cycle = channel_cycles[k]
        try:
            print(f"[K{k}] === Cycle {cycle} ===")

            # Exit team trước
            try:
                await do_exit_team(main_bot)
            except:
                pass

            # Tạo team, retry tối đa 3 lần
            r = None
            for _try in range(3):
                r = await do_create_team5_for(main_bot)
                if r.get("ok"):
                    break
                print(f"[K{k}] Tạo fail lần {_try+1}: {r.get('msg')} — retry...")
                try:
                    await do_exit_team(main_bot)
                except:
                    pass
                await asyncio.sleep(2)

            if not r or not r.get("ok"):
                print(f"[K{k}] Tạo fail sau 3 lần: {r.get('msg') if r else 'None'}")
                await asyncio.sleep(5)
                continue

            teamcode = r["teamcode"]
            # Học suffix thực tế của bot này (ổn định theo account)
            if len(teamcode) >= 2:
                learned_suffix = teamcode[-2:]
            print(f"[K{k}] Teamcode: {teamcode} | suffix={learned_suffix}")

            # Exit ngay để ghost có thể hunt
            await do_exit_team(main_bot)
            print(f"[K{k}] Out team xong")

            if len(teamcode) < 5 or not ghost_bots:
                continue

            suffix   = learned_suffix if learned_suffix else teamcode[-2:]
            body_len = len(teamcode) - 2  # toàn bộ phần random = tổng - 2 số cuối
            print(f"[K{k}] Ghost hunt {'x'*body_len}{suffix} (suffix cố định: {suffix}, random: {body_len} số)")
            ghost_stop  = time.time() + 30
            join_rounds = 0
            tried_codes: set = set()

            async def one_hunt(b, _cycle=cycle, _teamcode=teamcode, _k=k,
                               _suffix=suffix, _body_len=body_len):
                # Bỏ qua nếu teamcode gốc đã thành công rồi
                if _teamcode in JOINED_TEAMCODES:
                    return
                # Sinh code chưa thử — random toàn bộ phần đầu, chỉ giữ suffix
                tc = None
                for _ in range(20):
                    body = "".join(str(random.randint(0, 9)) for _ in range(_body_len))
                    cand = body + _suffix
                    if cand not in tried_codes and cand not in JOINED_TEAMCODES:
                        tried_codes.add(cand)
                        tc = cand
                        break
                if tc is None:
                    return
                try:
                    res = await do_join_for(b, tc, timeout=1.0)
                    if not (isinstance(res, dict) and res.get("ok")):
                        return

                    owner = res["owner"]
                    squad = res["squad"]

                    # Thoát team
                    try:
                        EXIT = await ExiT("000000", b["key"], b["iv"])
                        b["online_writer"].write(EXIT)
                        await b["online_writer"].drain()
                    except:
                        pass
                    await asyncio.sleep(1)

                    # Gửi ghost lần 1
                    gn    = MakeGhostName()
                    GHOST = await Send_GhosTs(owner, gn, squad, b["key"], b["iv"])
                    if GHOST:
                        b["online_writer"].write(GHOST)
                        await b["online_writer"].drain()
                        bump_stat("ghost_sent")
                        print(f"[K{_k}][👻] ghost=ok owner={owner} tc={tc}")
                        await asyncio.sleep(0.3)

                        # Gửi ghost lần 2 (đảm bảo)
                        try:
                            GHOST2 = await Send_GhosTs(owner, gn, squad, b["key"], b["iv"])
                            if GHOST2:
                                b["online_writer"].write(GHOST2)
                                await b["online_writer"].drain()
                                bump_stat("ghost_sent")
                                print(f"[K{_k}][👻] ghost=ok x2 owner={owner}")
                        except:
                            pass

                    bump_stat("hunt_success")

                    # Gọi API nhạc
                    try:
                        music_resp = await http_client.get(
                            f"http://de28.spaceify.eu:26110/join?tc={tc}", timeout=10.0
                        )
                        music_data = music_resp.json()
                        msg     = music_data.get("message", "")
                        ok_flag = music_data.get("success", False)
                        room_id = music_data.get("room") or music_data.get("room_id")
                        if not room_id and "room=" in str(msg):
                            room_id = str(msg).split("room=")[-1].split("'")[0].split("}")[0].strip()
                        if ok_flag and room_id:
                            print(f"[K{_k}][🎵] music=ok room={room_id}")
                        else:
                            print(f"[K{_k}][🎵] music=fail resp={music_data}")
                    except Exception:
                        pass

                    # Đánh dấu đã thành công
                    JOINED_TEAMCODES.add(tc)
                    JOINED_TEAMCODES.add(_teamcode)

                    add_history({
                        "time": str(datetime.now()), "channel": f"K{_k}",
                        "cycle": _cycle, "teamcode": _teamcode,
                        "matched_code": tc, "owner": owner,
                        "squad_preview": str(squad)[:80],
                        "bot": b["account_name"],
                    })

                except Exception as e:
                    print(f"[K{_k}][HUNT] err: {e}")
                    await asyncio.sleep(0.5)

            while time.time() < ghost_stop:
                join_rounds += 1
                await asyncio.gather(*[one_hunt(b) for b in ghost_bots], return_exceptions=True)

            print(f"[K{k}] Hết 30s ({join_rounds} vòng)")

        except Exception as e:
            print(f"[K{k}] Cycle {cycle} err: {e}")
            await asyncio.sleep(1)


async def auto_hunt_loop():
    global CURRENT_TEAMCODE
    print("[AUTO] === Bắt đầu loop 4 kênh ===")
    bots_list = list(BOTS.values())
    if len(bots_list) < 2:
        print("[AUTO] Cần >= 2 bot")
        return

    # Nếu số bot đủ chia 4 kênh (>= 8), dùng channel routing theo uid % 4
    # Nếu ít hơn, gom vào số kênh tối đa có thể (mỗi kênh cần >= 2 bot)
    num_channels = min(4, len(bots_list) // 2)
    print(f"[AUTO] {len(bots_list)} bot → dùng {num_channels} kênh")

    if num_channels >= 4:
        # Phân bổ đúng kênh theo uid % 4
        main_bots  = {0: None, 1: None, 2: None, 3: None}
        ghost_pool = []
        for b in bots_list:
            k = _get_channel(b["account_id"])
            if main_bots[k] is None:
                main_bots[k] = b
            else:
                ghost_pool.append(b)
        channels = {0: [], 1: [], 2: [], 3: []}
        for k in range(4):
            if main_bots[k]:
                channels[k].append(main_bots[k])
        for i, b in enumerate(ghost_pool):
            channels[i % 4].append(b)
    else:
        # Ít bot: chia đều vào num_channels kênh, không quan tâm uid % 4
        channels = {k: [] for k in range(num_channels)}
        for i, b in enumerate(bots_list):
            channels[i % num_channels].append(b)

    tasks = []
    channel_cycles = {k: 0 for k in range(num_channels)}

    for k in range(num_channels):
        bots_k = channels[k]
        main_name   = bots_k[0]["account_name"] if bots_k else "none"
        ghost_count = len(bots_k) - 1
        print(f"[AUTO] K{k}: main={main_name} | {ghost_count} ghost")
        if len(bots_k) < 2:
            print(f"[AUTO] K{k}: chỉ 1 bot — bỏ qua")
            continue
        tasks.append(_channel_loop(k, bots_k[0], bots_k[1:], channel_cycles))

    if not tasks:
        print("[AUTO] Không kênh nào đủ bot")
        return

    print(f"[AUTO] asyncio.gather {len(tasks)} kênh")
    await asyncio.gather(*tasks)

async def main():
    load_stats()
    accounts = load_accounts()
    if not accounts:
        print("\n[!] Nhập uid:password (Enter trống để dừng):\n")
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                break
            line = line.lstrip("> ").strip()
            if ":" in line:
                u, p = line.split(":", 1)
                u = u.strip().lstrip("> ").strip()
                p = p.strip()
                if u and p:
                    accounts.append({"uid": u, "password": p})
        save_accounts(accounts)
        if not accounts:
            print("[-] Không có account")
            return

    print(f"[+] Login {len(accounts)} account...")
    for acc in accounts:
        try:
            await start_one_bot(acc["uid"], acc["password"])
        except Exception as e:
            print(f"[-] Login {acc['uid']} fail: {e}")
        await asyncio.sleep(1.5)

    if not BOTS:
        print("[-] Không có bot nào online")
        return
    print(f"[✅] {len(BOTS)} bot online")

    try:
        await start_http_server()
    except Exception as e:
        print(f"[!] HTTP server skip: {e}")

    try:
        await auto_hunt_loop()
    except KeyboardInterrupt:
        print("\n[!] Dừng")
    finally:
        save_stats()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        save_stats()
        print("\n[!] Thoát")
