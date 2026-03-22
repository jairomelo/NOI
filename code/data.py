import pandas as pd
import os

def consolidate_data(data_folder, output_folder=None, output_file="consolidated_data.csv", dry_run=False):
    
    output_folder = os.path.join(data_folder, 'processed') if output_folder is None else output_folder
    os.makedirs(output_folder, exist_ok=True)
    
    all_data = os.listdir(data_folder)
    
    consolidated_df = pd.DataFrame()
    
    for file in all_data:
        file_path = os.path.join(data_folder, file)
        if file.endswith(".csv"):
            df = pd.read_csv(file_path)
            consolidated_df = pd.concat([consolidated_df, df], ignore_index=True)
            
    consolidated_df = consolidated_df.dropna(how='all').dropna(subset=['filename'])
    consolidated_df = consolidated_df.replace(r'\s', ' ', regex=True)
    
    if not dry_run:
        consolidated_df.to_csv(os.path.join(output_folder, output_file), index=False)
        print(f"Consolidated data saved to {output_file}")
    else:
        print(f"Dry run: Consolidated data would be saved to {output_file} with {len(consolidated_df)} rows.")
        print(consolidated_df.head())
    

if __name__ == "__main__":
    pass