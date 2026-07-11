#!/bin/bash
cd /home/nativesol/streamflix || exit
/home/nativesol/streamflix/.venv/bin/python foryou_scraper.py >> /home/nativesol/streamflix/logs/foryou_scraper.log 2>&1
