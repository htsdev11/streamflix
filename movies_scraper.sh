#!/bin/bash
cd /home/nativesol/streamflix || exit
/home/nativesol/streamflix/.venv/bin/python movies_scraper.py >> /home/nativesol/streamflix/logs/movies_scraper.log 2>&1
