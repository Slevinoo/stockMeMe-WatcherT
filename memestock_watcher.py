#!/usr/bin/env python3
import os
import time
import praw
import yfinance as yf
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone


# ================== CONFIGURATION ==================
CONFIG = {
    "reddit": {
        "client_id": "a8eYZMUdG5oTzKM1x60aWA",
        "client_secret": "PCfzKtda3niWCD9wZDchIqEIktRs_g",
        "user_agent": "memestock-watcher"
    },
    "smtp": {
        "host": "smtp.maileroo.com",
        "port": 587,
        "username": "gentlehenk@273f43bf8dbfe3d1.maileroo.org",
        "password": "c4c3119dd7b2ed8abd1b89a5",
        "from_addr": "helllooo@maileroo.com"
    },
    "notify_to": ["m.houtum@gmail.com"],
    "subreddits": ["wallstreetbets", "stocks", "pennystocks"],
    "keywords": ["to the moon", "short squeeze", "buy", "gamma", "pump", "🚀"],
    "min_mentions": 3,
    "scan_interval": 900  # seconds (15 minutes)
}
# ====================================================


def send_email(smtp_conf, subject, body, to_addresses):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_conf["from_addr"]
    msg["To"] = ", ".join(to_addresses)

    with smtplib.SMTP(smtp_conf["host"], smtp_conf["port"]) as server:
        server.starttls()
        server.login(smtp_conf["username"], smtp_conf["password"])
        server.sendmail(smtp_conf["from_addr"], to_addresses, msg.as_string())


def send_error_email(smtp_conf, to_addresses, error_message):
    try:
        subject = "[MemeWatcher] ERROR detected"
        body = (
            "An error occurred in the MemeStock Watcher:\n\n"
            f"{error_message}\n\n"
            f"UTC time: {datetime.now(timezone.utc).isoformat()}\n\n"
            "Check logs or journalctl for more details."
        )
        send_email(smtp_conf, subject, body, to_addresses)
    except Exception as e:
        logging.error("Failed to send error email: %s", e)


class MemeStockWatcher:
    def __init__(self, cfg):
        self.cfg = cfg
        self.reddit = praw.Reddit(
            client_id=cfg["reddit"]["client_id"],
            client_secret=cfg["reddit"]["client_secret"],
            user_agent=cfg["reddit"]["user_agent"]
        )
        logging.info("Reddit API connected.")

        try:
            send_email(
                cfg["smtp"],
                "[MemeWatcher] Service started",
                f"MemeStock Watcher started at {datetime.now(timezone.utc).isoformat()} UTC",
                cfg["notify_to"]
            )
        except Exception as e:
            logging.warning("Failed to send startup email: %s", e)

    def scan_reddit(self):
        found = {}
        for sub in self.cfg["subreddits"]:
            subreddit = self.reddit.subreddit(sub)
            for post in subreddit.new(limit=100):
                title = post.title.lower()
                for kw in self.cfg["keywords"]:
                    if kw.lower() in title:
                        words = post.title.upper().split()
                        for w in words:
                            if len(w) <= 5 and w.isalpha() and w.isupper():
                                found[w] = found.get(w, 0) + 1
        return {t: c for t, c in found.items() if c >= self.cfg["min_mentions"]}

    def check_stock(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get("currentPrice", 0)
            volume = info.get("volume", 0)
            avg_volume = info.get("averageVolume", 0)
            market_cap = info.get("marketCap", 0)

            score = 0
            if volume and avg_volume and volume > avg_volume * 2:
                score += 1
            if market_cap and market_cap < 1e9:
                score += 1

            return score, price, volume, avg_volume
        except Exception as e:
            logging.warning("Error checking stock %s: %s", ticker, e)
            return 0, 0, 0, 0

    def scan_once(self):
        logging.info("Starting scan at %s", datetime.now(timezone.utc).isoformat())
        trending = self.scan_reddit()

        if not trending:
            logging.info("No trending tickers found.")
            return

        interesting = []
        for ticker, count in trending.items():
            score, price, vol, avg_vol = self.check_stock(ticker)
            if score >= 2:
                interesting.append((ticker, count, score, price, vol))

        if interesting:
            body = "Potential meme stocks detected:\n\n"
            for t, c, s, p, v in interesting:
                body += f"{t}: Mentions={c}, Score={s}, Price={p}, Volume={v}\n"
            send_email(self.cfg["smtp"], "[MemeWatcher] Interesting Stocks", body, self.cfg["notify_to"])
            logging.info("Interesting stocks: %s", [i[0] for i in interesting])
        else:
            logging.info("No stocks meet criteria this round.")

    def run_loop(self):
        cadence = self.cfg["scan_interval"]
        send_error_email(self.cfg["smtp"], self.cfg["notify_to"], 'Error!')
        while True:
            try:
                self.scan_once()
            except Exception as e:
                logging.exception("Error during scan: %s", e)
                error_text = f"{type(e).__name__}: {str(e)}"
                try:
                    send_error_email(self.cfg["smtp"], self.cfg["notify_to"], error_text)
                except Exception as mail_err:
                    logging.error("Failed to send error notification: %s", mail_err)
            time.sleep(cadence)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("/var/log/memewatcher.log"),
            logging.StreamHandler()
        ]
    )

    watcher = MemeStockWatcher(CONFIG)
    watcher.run_loop()
