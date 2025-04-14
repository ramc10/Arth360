# RSS Feed Services

[![Join Telegram Channel](https://img.shields.io/badge/Telegram-Join%20Channel-blue)](https://t.me/artha360)

This project consists of three main services that work together to fetch, process, and publish RSS feed content:

1. `feeder.py` - Fetches RSS feeds and stores them in the database
2. `content.py` - Extracts content from the stored URLs
3. `telegram_publisher.py` - Publishes content to a Telegram channel 