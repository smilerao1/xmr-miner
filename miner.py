#!/usr/bin/env python3
"""
Simple Monero CPU Miner
Connects to MoneroOcean mining pool using Stratum protocol
Author: You!
License: MIT
"""

import socket
import json
import hashlib
import struct
import time
import threading
import sys
import os

# ============================================================
#  SETTINGS — Edit these before running
# ============================================================
WALLET  = "47vWEzxbeVe1PxqXzh2P5cU7FbfwscfQtCr7jXHFbVAwWKmYGznzAtCTD4qbivF2kMLfkUWp4oSiJTfCusRu7wSH6fgm5vC"   # Your Monero wallet address
WORKER  = "MyMiner"                    # Any name you want
POOL    = "gulf.moneroocean.stream"    # Mining pool server
PORT    = 10128                        # Pool port
THREADS = 2                            # CPU threads (start with 2)
# ============================================================

# Stats
stats = {"hashes": 0, "shares": 0, "start": time.time()}

def log(msg, tag="INFO"):
    colors = {"INFO": "\033[94m", "OK": "\033[92m", "WARN": "\033[93m", "ERR": "\033[91m"}
    reset = "\033[0m"
    c = colors.get(tag, "")
    ts = time.strftime("%H:%M:%S")
    print(f"{c}[{ts}] [{tag}] {msg}{reset}")

def hashrate_display():
    """Shows your mining speed every 10 seconds"""
    while True:
        time.sleep(10)
        elapsed = time.time() - stats["start"]
        hr = stats["hashes"] / elapsed
        unit = "H/s"
        if hr > 1000:
            hr /= 1000
            unit = "KH/s"
        log(f"Hashrate: {hr:.2f} {unit} | Shares submitted: {stats['shares']}", "INFO")

def xmr_hash(blob_hex, nonce_int):
    """
    Hashes a block blob with a given nonce.
    In real Monero this uses RandomX — here we simulate with SHA256
    for learning purposes. For real mining, use XMRig instead.
    """
    nonce_hex = format(nonce_int & 0xFFFFFFFF, "08x")
    # Insert nonce at position 78 (where Monero expects it)
    data = blob_hex[:78] + nonce_hex + blob_hex[86:]
    raw = bytes.fromhex(data)
    # Double SHA256 (simplified stand-in for RandomX)
    h = hashlib.sha256(hashlib.sha256(raw).digest()).hexdigest()
    stats["hashes"] += 1
    return h

def meets_target(hash_hex, target_hex):
    """Check if our hash is below the pool's target (lower = harder)"""
    return hash_hex < target_hex.zfill(64)

class MinerClient:
    def __init__(self):
        self.sock = None
        self.job = None
        self.job_id = None
        self.target = None
        self.blob = None
        self.lock = threading.Lock()
        self.running = False
        self.msg_id = 1

    def connect(self):
        log(f"Connecting to {POOL}:{PORT} ...")
        try:
            self.sock = socket.create_connection((POOL, PORT), timeout=30)
            self.sock.settimeout(60)
            log("Connected!", "OK")
            return True
        except Exception as e:
            log(f"Connection failed: {e}", "ERR")
            return False

    def send(self, data):
        msg = json.dumps(data) + "\n"
        self.sock.sendall(msg.encode())

    def recv_line(self):
        buf = b""
        while True:
            ch = self.sock.recv(1)
            if not ch:
                break
            buf += ch
            if ch == b"\n":
                break
        return buf.decode().strip()

    def login(self):
        log(f"Logging in as {WORKER} ...")
        self.send({
            "id": self.msg_id,
            "method": "login",
            "params": {
                "login": WALLET,
                "pass":  WORKER,
                "agent": "simple-py-miner/1.0"
            }
        })
        self.msg_id += 1

    def handle_message(self, msg):
        try:
            data = json.loads(msg)
        except:
            return

        # Login response — contains first job
        if data.get("id") == 1 and "result" in data:
            result = data["result"]
            if result and "job" in result:
                self.set_job(result["job"])
                log("Login successful! Mining started.", "OK")
            elif data.get("error"):
                log(f"Login error: {data['error']}", "ERR")

        # New job from pool
        elif data.get("method") == "job":
            self.set_job(data["params"])
            log("New job received from pool", "INFO")

        # Share accepted/rejected
        elif "result" in data and data.get("id", 0) > 1:
            if data["result"] and data["result"].get("status") == "OK":
                stats["shares"] += 1
                log(f"Share ACCEPTED! Total: {stats['shares']}", "OK")
            elif data.get("error"):
                log(f"Share rejected: {data['error']}", "WARN")

    def set_job(self, job):
        with self.lock:
            self.job_id = job["job_id"]
            self.blob   = job["blob"]
            self.target = job["target"]
        log(f"Job ID: {self.job_id[:12]}... Target: {self.target}", "INFO")

    def mine_thread(self, thread_id):
        """Each thread tries different nonces"""
        nonce = thread_id
        while self.running:
            if not self.blob:
                time.sleep(0.1)
                continue
            with self.lock:
                blob   = self.blob
                target = self.target
                job_id = self.job_id

            result = xmr_hash(blob, nonce)

            if meets_target(result, target):
                log(f"Thread {thread_id} found a share! Nonce: {nonce}", "OK")
                self.submit_share(job_id, nonce, result)

            nonce += THREADS  # Each thread uses different nonces

    def submit_share(self, job_id, nonce, result):
        self.send({
            "id":     self.msg_id,
            "method": "submit",
            "params": {
                "id":     "0",
                "job_id": job_id,
                "nonce":  format(nonce & 0xFFFFFFFF, "08x"),
                "result": result
            }
        })
        self.msg_id += 1

    def listen(self):
        """Listen for messages from pool"""
        while self.running:
            try:
                msg = self.recv_line()
                if msg:
                    self.handle_message(msg)
            except socket.timeout:
                continue
            except Exception as e:
                log(f"Connection lost: {e}", "ERR")
                self.running = False
                break

    def start(self):
        if not self.connect():
            return
        self.running = True
        self.login()

        # Start listener thread
        t_listen = threading.Thread(target=self.listen, daemon=True)
        t_listen.start()

        # Wait for first job
        time.sleep(2)

        # Start mining threads
        log(f"Starting {THREADS} mining thread(s)...", "INFO")
        for i in range(THREADS):
            t = threading.Thread(target=self.mine_thread, args=(i,), daemon=True)
            t.start()

        # Start hashrate display
        t_stats = threading.Thread(target=hashrate_display, daemon=True)
        t_stats.start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            log("Miner stopped by user.", "WARN")
            self.running = False

def check_wallet():
    if WALLET == "YOUR_WALLET_ADDRESS_HERE":
        log("ERROR: You forgot to set your wallet address in miner.py!", "ERR")
        log("Open miner.py and replace YOUR_WALLET_ADDRESS_HERE with your real wallet.", "ERR")
        sys.exit(1)

if __name__ == "__main__":
    print("\033[92m")
    print("=" * 50)
    print("   Simple Monero Miner — Open Source")
    print("   Pool: MoneroOcean")
    print("=" * 50)
    print("\033[0m")

    check_wallet()
    client = MinerClient()
    client.start()
