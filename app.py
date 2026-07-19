import os
import json
import glob
from datetime import datetime
import pandas as pd
import time
import json_repair
from google import genai
from google.genai import types
from rapidfuzz import process, fuzz
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# MASTER CONFIGURATION
# ==========================================
MASTER_RESOURCE_LIST = [
    "Cage 1", "Cage 2", "Cage 3", "Cage 4", "Cage 5", 
    "Cage 6", "Cage 7 Tee Cage", "Cage 8 Long Cage", "Cage 9", "Cage 10",
    "Pitching Lane 1", "Pitching Lane 2", "Pitching Lane 3",
    "1 Pitch Lab", "Hittrack Lab"
]

# ==========================================
# 1. TIME CALCULATION UTILITY
# ==========================================
def calculate_duration(start_str: str, end_str: str) -> int:
    """Calculates the duration in minutes between two time strings."""
    start_str = start_str.strip().upper()
    end_str = end_str.strip().upper()
    
    time_formats = ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]
    
    start_dt, end_dt = None, None
    for fmt in time_formats:
        try:
            start_dt = datetime.strptime(start_str, fmt)
            break
        except ValueError:
            continue
            
    for fmt in time_formats:
        try:
            end_dt = datetime.strptime(end_str, fmt)
            break
        except ValueError:
            continue
            
    if not start_dt or not end_dt:
        return 60
        
    duration = end_dt - start_dt
    minutes = int(duration.total_seconds() / 60)
    
    if minutes < 0:
        minutes += 24 * 60
        
    return minutes

# ==========================================
# 2. CORE EXTRACTION ENGINE (MAP-REDUCE)
# ==========================================
def extract_schedule_data(image_path: str):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type="image/png"
    )

    # -----------------------------------------
    # PASS 1: THE MAPPER (Pure Visual Extraction)
    # -----------------------------------------
    pass_1_prompt = """
    You are an eagle-eyed visual inspector. Scan this schedule grid methodically from left to right, top to bottom.
    Your ONLY job is to find every single colored booking block and list it. Do not worry about formatting.

    For EVERY colored block, write a bullet point containing:
    1. The Column Header it is under.
    2. The exact text written inside the block.
    3. The start and end time (read from the text inside the block, or deduced from the left-side time grid if not written).

    CRITICAL: Do not skip any blocks, especially small 30-minute ones. Be exhaustive.
    """
    
    print("      -> Running Pass 1: Visual Scanning...")
    pass_1_response = None
    
    for attempt in range(3):
        try:
            pass_1_response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[image_part, pass_1_prompt]
            )
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(15)
            else:
                raise e
                
    raw_text_data = pass_1_response.text

    # -----------------------------------------
    # PASS 2: THE REDUCER (Data Logic & Formatting)
    # -----------------------------------------
    pass_2_prompt = f"""
    You are a rigid data processing engineer. I am giving you a raw list of schedule bookings extracted from an image.
    Your single task is to convert this text into a perfect JSON array.
    
    CRITICAL RULES:
    1. Calculate the exact Start Time and End Time based on the notes. Fix any obvious AM/PM logical errors.
    2. ADD CONFIDENCE SCORE: Include a "confidence_score" ("High", "Medium", "Low") for each booking. Use "Low" if the text seems confusing.
    3. Format exactly as this JSON structure:
    {{
      "detected_bookings": [
        {{
          "column_header": "Cage 6",
          "start_time": "4:00 PM",
          "end_time": "5:00 PM",
          "visible_text": "Hitting Lesson",
          "confidence_score": "High"
        }}
      ]
    }}
    
    RAW BOOKING DATA TO PROCESS:
    {raw_text_data}
    """
    
    print("      -> Running Pass 2: Data Structuring...")
    pass_2_response = None
    for attempt in range(3):
        try:
            pass_2_response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[pass_2_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(15)
            else:
                raise e

    # -----------------------------------------
    # JSON PROCESSING & VALIDATION LAYER
    # -----------------------------------------
    try:
        clean_text = pass_2_response.text.strip().removeprefix('```json').removesuffix('```').strip()
        data = json_repair.loads(clean_text)
    except Exception as e:
        print(f"\n[!] Critical JSON Formatting Error: {e}")
        return pd.DataFrame()

    raw_bookings = data.get("detected_bookings", [])
    processed_bookings = []
    
    for booking in raw_bookings:
        raw_column_header = booking.get("column_header", "")
        start_t = booking.get("start_time", "")
        end_t = booking.get("end_time", "")
        confidence = booking.get("confidence_score", "High")
        
        # Fuzzy String Matching against Master Database
        validated_column = raw_column_header 
        if raw_column_header:
            match = process.extractOne(raw_column_header, MASTER_RESOURCE_LIST, scorer=fuzz.ratio)
            if match and match[1] >= 75: 
                validated_column = match[0]
        
        duration_minutes = calculate_duration(start_t, end_t)
        notes = ""
        
        # Mathematical Quality Control
        if duration_minutes > 360:
            notes = f"⚠️ WARNING: Implausible duration ({duration_minutes} min). AI likely misread AM/PM."
            duration_minutes = 60 

        processed_bookings.append({
            "Resource/Column": validated_column,
            "Start Time": start_t,
            "End Time": end_t,
            "Duration (Minutes)": duration_minutes,
            "Raw Text": booking.get("visible_text", ""),
            "Source File": os.path.basename(image_path),
            "AI Confidence": confidence,
            "Validation Notes": notes
        })
        
    df = pd.DataFrame(processed_bookings)
    if not df.empty:
        df.drop_duplicates(subset=["Resource/Column", "Start Time", "End Time"], inplace=True)
        
    return df

# ==========================================
# 3. BATCH PROCESSING EXECUTION
# ==========================================
if __name__ == "__main__":
    image_folder = "Weekly_Schedule"
    
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
        print(f"Created '{image_folder}'. Add schedule images and run again!")
        exit()
        
    image_files = glob.glob(os.path.join(image_folder, "*.png"))
    
    if not image_files:
        print(f"No images found in '{image_folder}'. Add them and try again.")
        exit()
        
    print(f"Found {len(image_files)} schedule images. Starting batch extraction...\n")
    all_weekly_data = []
    
    for img_path in image_files:
        print(f"Analyzing {os.path.basename(img_path)}...")
        try:
            df = extract_schedule_data(img_path)
            all_weekly_data.append(df)
            print(f" -> Found {len(df)} bookings.")
            time.sleep(4)
        except Exception as e:
            print(f" -> Error processing {os.path.basename(img_path)}: {e}")
            
    if all_weekly_data:
        master_df = pd.concat(all_weekly_data, ignore_index=True)
        output_file = "weekly_utilization_report.csv"
        master_df.to_csv(output_file, index=False)
        
        print(f"\nSUCCESS! Extracted {len(master_df)} bookings across {len(image_files)} days.")
        print(f"Your final report is ready: {output_file}")