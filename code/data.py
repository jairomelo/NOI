import pandas as pd
import os
import uuid
from pathlib import Path
from glob import glob

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
    
    consolidated_df['objectid'] = consolidated_df.apply(lambda _: str(uuid.uuid4()), axis=1)
    consolidated_df['artifacts_location'] = consolidated_df['filename'].apply(lambda x: _locate_artifacts(x, "artifacts", None))
    
    if not dry_run:
        consolidated_df.to_csv(os.path.join(output_folder, output_file), index=False)
        print(f"Consolidated data saved to {output_file}")
    else:
        print(f"Dry run: Consolidated data would be saved to {output_file} with {len(consolidated_df)} rows.")
        print(consolidated_df['artifacts_location'].head())

def _locate_artifacts(path, origin, patterns):
    name, extension = os.path.splitext(path)
    if "Fotos" in name:
        origin = os.path.join(origin, "EuroPosts")
    elif "C2-G2" in name:
        origin = os.path.join(origin, "sitiopostales")
    else:
        origin = os.path.join(origin, "Coleccion-MC")
    
    search_pattern = os.path.join(origin, f"{Path(path).stem}-*.*")
    # print(f"Searching for files matching: {search_pattern}")
    matching_files = glob(search_pattern)
    return matching_files


if __name__ == "__main__":
    consolidate_data(data_folder="data", output_folder="data/processed", output_file="consolidated_data.csv", dry_run=False)