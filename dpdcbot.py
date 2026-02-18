import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USER_ID = os.getenv('AUTHORIZED_USER_ID')  # Optional: restrict to your user ID

# DPDC meter account numbers (Customer Numbers from your bills)
METER_ACCOUNTS = [
    os.getenv('METER_1', ''),
    os.getenv('METER_2', ''),
    os.getenv('METER_3', ''),
    os.getenv('METER_4', ''),
    os.getenv('METER_5', ''),
    os.getenv('METER_6', ''),
    os.getenv('METER_7', ''),
]

# Filter out empty meter numbers
METER_ACCOUNTS = [m for m in METER_ACCOUNTS if m]


class DPDCBalanceChecker:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
    
    async def initialize_browser(self):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()
        # Launch in headed mode for manual CAPTCHA solving
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=['--start-maximized']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    
    async def solve_captcha_manually(self, page):
        """Wait for manual CAPTCHA solving"""
        logger.info("⏳ Waiting for manual CAPTCHA solving... (60 seconds)")
        logger.info("Please check the browser window and solve the CAPTCHA")
        
        # Wait up to 60 seconds for CAPTCHA to be solved
        for i in range(60):
            try:
                # Check if submit button is enabled (CAPTCHA solved)
                submit_btn = await page.query_selector('button:has-text("Submit")')
                if submit_btn:
                    is_disabled = await submit_btn.get_attribute('disabled')
                    if not is_disabled:
                        logger.info("✅ CAPTCHA solved!")
                        return True
            except:
                pass
            await asyncio.sleep(1)
        
        logger.warning("⚠️ CAPTCHA timeout")
        return False
    
    async def solve_captcha_2captcha(self, page, site_key):
        """
        Solve reCAPTCHA using 2captcha service (optional)
        """
        try:
            from twocaptcha import TwoCaptcha
            
            api_key = os.getenv('TWOCAPTCHA_API_KEY')
            if not api_key:
                logger.error("2captcha API key not found")
                return False
            
            solver = TwoCaptcha(api_key)
            logger.info("🤖 Solving CAPTCHA with 2captcha...")
            
            result = solver.recaptcha(
                sitekey=site_key,
                url=page.url
            )
            
            # Inject the solution
            await page.evaluate(f'''
                document.getElementById("g-recaptcha-response").innerHTML="{result['code']}";
                if (typeof grecaptcha !== 'undefined') {{
                    grecaptcha.getResponse = function() {{ return "{result['code']}"; }};
                }}
            ''')
            
            logger.info("✅ CAPTCHA solved with 2captcha")
            return True
            
        except Exception as e:
            logger.error(f"2captcha error: {e}")
            return False
    
    async def get_meter_balance(self, account_number):
        """Fetch balance for a specific meter using Quick Pay page"""
        page = None
        try:
            page = await self.context.new_page()
            
            # Navigate to DPDC login page first
            logger.info(f"Checking balance for account: {account_number}")
            await page.goto('https://amiapp.dpdc.org.bd/login', wait_until='networkidle')
            await asyncio.sleep(2)
            
            # Click on QUICK PAY button
            try:
                # Look for the Quick Pay button/link
                quick_pay_button = await page.query_selector('button:has-text("QUICK PAY"), a:has-text("QUICK PAY"), [href*="quickpay"]')
                if quick_pay_button:
                    await quick_pay_button.click()
                    await page.wait_for_load_state('networkidle')
                    logger.info("Navigated to Quick Pay page")
                else:
                    # If button not found, try direct navigation
                    await page.goto('https://amiapp.dpdc.org.bd/quickpay', wait_until='networkidle')
            except Exception as e:
                logger.warning(f"Quick Pay button not found, trying direct URL: {e}")
                await page.goto('https://amiapp.dpdc.org.bd/quickpay', wait_until='networkidle')
            
            await asyncio.sleep(2)
            
            # Wait for page to load
            await page.wait_for_selector('input[placeholder*="Customer Number"], input[name*="customer"], input[id*="customer"]', timeout=10000)
            
            # Fill customer number - try multiple possible selectors
            customer_input_filled = False
            possible_selectors = [
                'input[placeholder*="Customer Number"]',
                'input[name*="customer"]',
                'input[id*="customer"]',
                'input[type="text"]',
            ]
            
            for selector in possible_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await element.fill(account_number)
                        customer_input_filled = True
                        logger.info(f"Filled customer number using selector: {selector}")
                        break
                except:
                    continue
            
            if not customer_input_filled:
                logger.error("Could not find customer number input field")
                raise Exception("Customer number input field not found")
            
            # Check for reCAPTCHA
            try:
                # Wait a moment for reCAPTCHA to load
                await asyncio.sleep(2)
                
                # Check if reCAPTCHA exists
                recaptcha = await page.query_selector('.g-recaptcha, iframe[src*="recaptcha"]')
                
                if recaptcha:
                    # Try automatic solving first if 2captcha is configured
                    api_key = os.getenv('TWOCAPTCHA_API_KEY')
                    if api_key:
                        try:
                            site_key = await page.get_attribute('.g-recaptcha', 'data-sitekey')
                            if site_key:
                                captcha_solved = await self.solve_captcha_2captcha(page, site_key)
                                if not captcha_solved:
                                    # Fall back to manual
                                    await self.solve_captcha_manually(page)
                        except:
                            await self.solve_captcha_manually(page)
                    else:
                        # Manual CAPTCHA solving
                        await self.solve_captcha_manually(page)
            except Exception as e:
                logger.info(f"No CAPTCHA or already solved: {e}")
            
            # Click submit button - try multiple possible selectors
            submit_clicked = False
            possible_submit_selectors = [
                'button:has-text("Submit")',
                'button:has-text("SIGN IN")',
                'button[type="submit"]',
                'input[type="submit"]',
                '.submit-button',
                '#submit',
            ]
            
            for selector in possible_submit_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_disabled = await element.get_attribute('disabled')
                        if not is_disabled:
                            await element.click()
                            submit_clicked = True
                            logger.info(f"✅ Clicked submit button using selector: {selector}")
                            break
                except:
                    continue
            
            if not submit_clicked:
                logger.warning("⚠️ Submit button not clicked automatically, may need manual click")
            
            # Wait for results to load
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            
            # Extract balance information from the page
            balance_data = {
                'account': account_number,
                'balance': None,
                'status': 'error'
            }
            
            try:
                
                # Try to find any text containing "Balance", "Bill", "Amount", "Taka" etc.
                page_content = await page.content()
                
                # Method 1: Look for common balance patterns
                balance_patterns = [
                    r'Balance[:\s]+(?:Tk\.?|৳|BDT)?\s*([\d,]+\.?\d*)',
                    r'Bill Amount[:\s]+(?:Tk\.?|৳|BDT)?\s*([\d,]+\.?\d*)',
                    r'Current Bill[:\s]+(?:Tk\.?|৳|BDT)?\s*([\d,]+\.?\d*)',
                    r'Total Amount[:\s]+(?:Tk\.?|৳|BDT)?\s*([\d,]+\.?\d*)',
                    r'Due Amount[:\s]+(?:Tk\.?|৳|BDT)?\s*([\d,]+\.?\d*)',
                    r'(?:Tk\.?|৳|BDT)\s*([\d,]+\.?\d*)',
                ]
                
                page_text = await page.inner_text('body')
                
                for pattern in balance_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        balance_str = match.group(1).replace(',', '')
                        balance_data['balance'] = float(balance_str)
                        balance_data['status'] = 'success'
                        logger.info(f"✅ Found balance: ৳{balance_data['balance']}")
                        break
                
                # If no balance found, try to extract from specific elements
                if balance_data['balance'] is None:
                    # Try common class names and IDs
                    selectors = [
                        '.balance', '#balance', '.bill-amount', '#billAmount',
                        '.amount', '.total', '.due', '[class*="balance"]',
                        '[class*="bill"]', '[class*="amount"]'
                    ]
                    
                    for selector in selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element:
                                text = await element.inner_text()
                                numbers = re.findall(r'[\d,]+\.?\d*', text)
                                if numbers:
                                    balance_str = numbers[0].replace(',', '')
                                    balance_data['balance'] = float(balance_str)
                                    balance_data['status'] = 'success'
                                    logger.info(f"✅ Found balance: ৳{balance_data['balance']}")
                                    break
                        except:
                            continue
                
                if balance_data['balance'] is None:
                    logger.warning(f"⚠️ Could not extract balance for {account_number}")
                    # Take a screenshot for debugging
                    screenshot_path = f'/home/claude/debug_{account_number}.png'
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
            except Exception as e:
                logger.error(f"Error extracting balance: {e}")
            
            await page.close()
            return balance_data
            
        except Exception as e:
            logger.error(f"Error fetching balance for {account_number}: {e}")
            if page:
                await page.close()
            return {'account': account_number, 'balance': None, 'status': 'error'}
    
    async def get_all_balances(self):
        """Fetch balances for all meters"""
        results = []
        
        try:
            await self.initialize_browser()
            
            # Fetch balance for each meter
            for i, account in enumerate(METER_ACCOUNTS, 1):
                logger.info(f"Processing meter {i}/{len(METER_ACCOUNTS)}: {account}")
                balance_data = await self.get_meter_balance(account)
                results.append(balance_data)
                
                # Small delay between requests to be respectful
                if i < len(METER_ACCOUNTS):
                    await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error in get_all_balances: {e}")
        finally:
            await self.close()
        
        return results
    
    async def close(self):
        """Close browser"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Welcome to DPDC Balance Checker Bot!\n\n'
        'Commands:\n'
        '/show - Get all meter balances\n'
        '/start - Show this message'
    )


async def show_balances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display all meter balances"""
    
    # Optional: Check if user is authorized
    if AUTHORIZED_USER_ID and str(update.effective_user.id) != AUTHORIZED_USER_ID:
        await update.message.reply_text("Unauthorized access!")
        return
    
    # Check if meters are configured
    if not METER_ACCOUNTS:
        await update.message.reply_text(
            "No meter accounts configured!\n"
            "Please add your meter numbers to the .env file."
        )
        return
    
    await update.message.reply_text(
        f"Fetching balances for {len(METER_ACCOUNTS)} meters...\n"
        "This may take 1-2 minutes.\n\n"
        "A browser window will open. Please solve the CAPTCHA when prompted."
    )
    
    try:
        checker = DPDCBalanceChecker()
        results = await checker.get_all_balances()
        
        if results:
            message = "*DPDC Meter Balances*\n"
            message += f"{asyncio.get_event_loop().time()}\n\n"
            
            total = 0
            success_count = 0
            
            for i, data in enumerate(results, 1):
                account = data['account']
                balance = data['balance']
                status = data['status']
                
                # Mask account number for privacy (show last 4 digits)
                masked_account = f"***{account[-4:]}" if len(account) > 4 else account
                
                if status == 'success' and balance is not None:
                    message += f"🔌 Meter {i} ({masked_account}): TK{balance:,.2f}\n"
                    total += balance
                    success_count += 1
                else:
                    message += f"🔌 Meter {i} ({masked_account}): Error\n"
            
            message += f"\n{'─' * 30}\n"
            message += f"*Total Balance: Tk{total:,.2f}*\n"
            message += f"Successfully fetched: {success_count}/{len(results)}"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "Failed to fetch balances.\n"
                "Please check the logs and try again."
            )
            
    except Exception as e:
        logger.error(f"Error in show_balances: {e}")
        await update.message.reply_text(
            f"❌ Error occurred:\n{str(e)}\n\n"
            "Please check if:\n"
            "• Meter numbers are correct\n"
            "• Internet connection is stable\n"
            "• DPDC website is accessible"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    text = update.message.text.lower()
    
    if text == 'show':
        await show_balances(update, context)
    else:
        await update.message.reply_text(
            "Type 'show' or use /show to get meter balances."
        )


def main():
    """Start the bot"""
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("show", show_balances))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run the bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()