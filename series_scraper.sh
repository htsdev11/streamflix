#!/bin/bash
cd /home/nativesol/streamflix || exit
/home/nativesol/streamflix/.venv/bin/python series_scraper.py >> /home/nativesol/streamflix/logs/series_scraper.log 2>&1
