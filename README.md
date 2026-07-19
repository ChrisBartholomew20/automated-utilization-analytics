# automated-utilization-analytics


[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-Data_Analytics-150458.svg)](https://pandas.pydata.org/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-Vision_API-4285F4.svg)](https://ai.google.dev/)

A Python-based automation tool I built to extract unstructured schedule data from screenshots of a facility's schedule and turn it into a clean, multi-tab Excel dashboard. 

## The Problem
Facility schedules are often trapped inside GUI software that doesn't let you easily export custom data. To figure out the actual utilization rates ( how often Cage 1 was booked vs. the Pitching Lab), we would have to do tedious manual entry. 

I built this pipeline to completely automate that process. I upload screenshots of the weekly schedule, and then use AI to read the colored booking blocks, and it outputs a math-checked pivot table in Excel. It tracks 15 different physical assets operating at 9.5 hours of daily capacity.

## How It Works (Handling AI Hallucinations)
If you ask an AI vision model to read a dense schedule grid and format it into JSON all at once, it gets overwhelmed and skips over some bookings or miscalculates how long they last. To fix this, I split the process into two steps (a Map-Reduce approach):

1. Pass 1 (Visual Scan): The Gemini 3.1 Flash Lite Vision API looks at the image and extracts a raw text list of every single booking block it sees.
2. Pass 2 (Data Structuring): A text-only prompt takes that raw list, does the time math, and formats everything perfectly into a strict JSON array.

## Key Features
* Automated Data Cleaning: The AI sometimes misspells things (e.g., extracting "Gage 6" instead of "Cage 6"). I used the `rapidfuzz` library to automatically match and correct these typos against a list of our assets.
* Math & Logic Filters: The script automatically flags impossible bookings (like a 12-hour lesson caused by the AI confusing AM and PM) and moves them to a "Requires Manual Review" tab in Excel. 
* Relational Mapping: Used `pandas` to cross-join the extracted data with our total weekly capacity. This ensures that if a batting cage wasn't booked at all, it still shows up correctly as having a 0% utilization rate.
* Auto-Retries: Built-in fault tolerance. If the Google API hits a rate limit or times out, the script pauses and tries again instead of crashing the whole batch.

## Tech Stack
* Language: Python
* Data & Analytics: `pandas`, `numpy`
* APIs: `google-genai` (Gemini Vision API)
* Text Fixing: `rapidfuzz`, `json_repair`
* Excel Generation: `xlsxwriter`, `openpyxl`

## How to Run It

**1. Clone and set up the environment:**
```bash
git clone [https://github.com/YourUsername/facility-analytics-pipeline.git](https://github.com/YourUsername/facility-analytics-pipeline.git)
cd facility-analytics-pipeline
python -m venv nenv
source nenv/bin/activate  # Windows: nenv\Scripts\activate
pip install -r requirements.txt
