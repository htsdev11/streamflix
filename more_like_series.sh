#!/bin/bash
cd /home/nativesol/streamflix || exit
/home/nativesol/streamflix/.venv/bin/python more_like_series.py >> /home/nativesol/streamflix/logs/more_like_series.log 2>&1
