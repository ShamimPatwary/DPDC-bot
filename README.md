# DPDC Balance Checker Bot 🔌

A personal Telegram bot to check my DPDC electricity meter balances without manually visiting the website every time. Just send `/show` and it scrapes the balances for all configured meters and sends back a summary — right in Telegram.

---

## Features

- Check balances for up to 7 DPDC meter accounts in one go
- Scrapes the DPDC Quick Pay portal automatically using Playwright
- Solves CAPTCHAs manually via a browser window; 2Captcha API works too if you have credits
- Masks account numbers in Telegram messages for privacy
- Shows individual balances and a grand total across all meters
- Bot access locked to a specific Telegram user ID

---

## Requirements

- Python 3.9+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Your DPDC Customer Number(s)
- *(Optional)* A [2Captcha](https://2captcha.com) account with active credits for automated CAPTCHA solving

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/yourusername/dpdc-balance-bot.git
cd dpdc-balance-bot
```

**2. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**3. Install Playwright browsers**

```bash
playwright install chromium
```

**4. Set up environment variables**

Copy the example env file and fill in your details:

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
AUTHORIZED_USER_ID=your_telegram_user_id_here

# Add your DPDC Customer Numbers (from your electricity bill)
METER_1=
METER_2=
METER_3=
METER_4=
METER_5=
METER_6=
METER_7=

# Optional: 2Captcha API key (only works if you have active account credit)
TWOCAPTCHA_API_KEY=
```

> **Tip:** To find your Telegram user ID, message [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## Usage

**Start the bot:**

```bash
python bot.py
```

**In Telegram:**

| Command | Description |
|---------|-------------|
| `/start` | Show available commands |
| `/show` | Fetch and display all meter balances |

You can also just type `show` as a plain message.

---

## How It Works

1. The bot opens a Chromium browser window via Playwright
2. It navigates to the [DPDC Quick Pay portal](https://amiapp.dpdc.org.bd/quickpay)
3. It fills in each Customer Number and submits the form
4. If a CAPTCHA appears, it either solves it automatically (via 2Captcha) or waits up to 60 seconds for you to solve it manually in the browser window
5. It extracts the balance from the page and sends the results to your Telegram chat

---

## CAPTCHA Handling

By default, the bot opens a visible browser window and waits for you to solve the CAPTCHA manually. You have **60 seconds** to solve it before it times out.

If you have a [2Captcha](https://2captcha.com) account with active credit, set your API key in `.env` and the bot will attempt to solve CAPTCHAs automatically, falling back to manual solving if it fails.

---

## Project Structure

```
dpdc-balance-bot/
├── bot.py              # Main bot script
├── requirements.txt    # Python dependencies
└── README.md
```

---

## Dependencies

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Playwright](https://playwright.dev/python/)
- [python-dotenv](https://github.com/theskumar/python-dotenv)
- [2captcha-python](https://github.com/2captcha/2captcha-python) *(optional)*

Install all at once:

```bash
pip install python-telegram-bot playwright python-dotenv 2captcha-python
```

---

## Notes

- The bot requires a visible display to show the browser window for manual CAPTCHA solving. If running on a headless server, you'll need a virtual display (e.g., `Xvfb`) or rely on 2Captcha for automated solving.
- This bot is for personal use only. Be respectful of DPDC's servers — don't run checks too frequently.
- Account numbers are masked in Telegram messages (only the last 4 digits are shown).

---

## License

Personal use only.
