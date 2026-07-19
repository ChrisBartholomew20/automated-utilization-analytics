import pandas as pd
import numpy as np
import os

# ==========================================
# CONFIGURATION
# ==========================================
# Exactly 15 Assets. This acts as our relational Master Table.
MASTER_ASSETS = [
    "Cage 1", "Cage 2", "Cage 3", "Cage 4", "Cage 5", 
    "Cage 6", "Cage 7 Tee Cage", "Cage 8 Long Cage", "3 Pitch Lab", "Annex Area Weight Room",
    "Annex Cage 1", "Annex Infield", "Infield",
    "1 Pitch Lab", "2 Pitch Lab"
]

HOURS_PER_DAY = 9.5
DAYS_IN_WEEK = 7
WEEKLY_CAPACITY = HOURS_PER_DAY * DAYS_IN_WEEK

def load_and_clean_data(csv_path: str) -> pd.DataFrame:
    print(f"Loading raw data from {csv_path}...")
    if not os.path.exists(csv_path):
        raise FileNotFoundError("Raw data file not found. Run app.py first!")

    df = pd.read_csv(csv_path)
    df['Duration (Minutes)'] = pd.to_numeric(df['Duration (Minutes)'], errors='coerce').fillna(0)
    df['Hours Booked'] = (df['Duration (Minutes)'] / 60).round(2)
    
    string_cols = ['Resource/Column', 'Start Time', 'End Time', 'Raw Text', 'Source File']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df.replace("nan", np.nan, inplace=True)
    df.fillna({'Validation Notes': 'Clean', 'AI Confidence': 'High'}, inplace=True)
    return df

def generate_excel_dashboard(df: pd.DataFrame, output_path: str):
    print("Building relational matrices and capacity models...")

    # -----------------------------------------
    # MODEL 1: Weekly Capacity vs Utilization
    # -----------------------------------------
    # Calculate actuals
    weekly_actuals = df.groupby('Resource/Column')['Hours Booked'].sum().reset_index()
    
    # Create the Master Table and Left Join the actuals
    weekly_summary = pd.DataFrame({'Resource/Column': MASTER_ASSETS})
    weekly_summary = pd.merge(weekly_summary, weekly_actuals, on='Resource/Column', how='left').fillna(0)
    
    # Add Capacity Constraints
    weekly_summary['Total Capacity (Hours)'] = WEEKLY_CAPACITY
    weekly_summary['Utilization %'] = (weekly_summary['Hours Booked'] / weekly_summary['Total Capacity (Hours)'])
    
    # Sort for the graph
    weekly_summary = weekly_summary.sort_values(by='Hours Booked', ascending=False)

    # -----------------------------------------
    # MODEL 2: Daily Capacity vs Utilization
    # -----------------------------------------
    # Find all unique days processed (e.g., Monday.png, Tuesday.png)
    # If the CSV is empty, provide a fallback day
    unique_days = df['Source File'].dropna().unique() if not df.empty else ["Monday.png"]
    
    # Create a Cartesian Product (Cross Join) of Every Day x Every Asset
    multi_index = pd.MultiIndex.from_product([unique_days, MASTER_ASSETS], names=['Source File', 'Resource/Column'])
    daily_master = pd.DataFrame(index=multi_index).reset_index()
    
    # Calculate actuals per day
    daily_actuals = df.groupby(['Source File', 'Resource/Column'])['Hours Booked'].sum().reset_index()
    
    # Left join to guarantee zero-hour assets are mapped to every day
    daily_summary = pd.merge(daily_master, daily_actuals, on=['Source File', 'Resource/Column'], how='left').fillna(0)
    
    daily_summary['Daily Capacity (Hours)'] = HOURS_PER_DAY
    daily_summary['Utilization %'] = (daily_summary['Hours Booked'] / daily_summary['Daily Capacity (Hours)'])

    # -----------------------------------------
    # EXPORT PROCESS WITH EMBEDDED GRAPHICS
    # -----------------------------------------
    print(f"Writing interactive dashboard to {output_path}...")
    
    # We use xlsxwriter to physically draw the Excel chart via Python
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        
        # 1. Write the tabs
        weekly_summary.to_excel(writer, sheet_name='Weekly Summary', index=False)
        daily_summary.to_excel(writer, sheet_name='Daily Breakdown', index=False)
        df.to_excel(writer, sheet_name='Raw Extracted Data', index=False)
        
        # 2. Format the Utilization % columns as actual percentages in Excel
        workbook = writer.book
        percent_fmt = workbook.add_format({'num_format': '0.0%'})
        
        worksheet_week = writer.sheets['Weekly Summary']
        worksheet_week.set_column('D:D', None, percent_fmt)
        
        worksheet_day = writer.sheets['Daily Breakdown']
        worksheet_day.set_column('E:E', None, percent_fmt)

        # 3. BUILD THE EXCEL CHART
        chart = workbook.add_chart({'type': 'column'})
        max_row = len(weekly_summary) + 1
        
        # Add the 'Hours Booked' data series to the chart
        chart.add_series({
            'name':       ['Weekly Summary', 0, 1],
            'categories': ['Weekly Summary', 1, 0, max_row - 1, 0],
            'values':     ['Weekly Summary', 1, 1, max_row - 1, 1],
            'fill':       {'color': '#4C9900'}, # Green
            'overlap':    -10
        })
        
        # Add the 'Total Capacity' data series to the chart
        chart.add_series({
            'name':       ['Weekly Summary', 0, 2],
            'categories': ['Weekly Summary', 1, 0, max_row - 1, 0],
            'values':     ['Weekly Summary', 1, 2, max_row - 1, 2],
            'fill':       {'color': '#D3D3D3'}  # Light Grey
        })
        
        # Configure chart layout and text
        chart.set_title({'name': 'Weekly Asset Utilization vs Maximum Capacity'})
        chart.set_x_axis({'name': 'Facility Assets', 'label_position': 'low'})
        chart.set_y_axis({'name': 'Total Hours', 'major_gridlines': {'visible': True}})
        chart.set_size({'width': 900, 'height': 450})
        
        # Insert the chart onto the Weekly Summary sheet at cell F2
        worksheet_week.insert_chart('F2', chart)

    print("✅ Dashboard complete! Open your Excel file to see the interactive chart.")

if __name__ == "__main__":
    raw_csv = "weekly_utilization_report.csv"
    final_excel = "Facility_Analytics_Dashboard.xlsx"
    
    try:
        clean_data = load_and_clean_data(raw_csv)
        generate_excel_dashboard(clean_data, final_excel)
    except Exception as e:
        print(f"Error building report: {e}")