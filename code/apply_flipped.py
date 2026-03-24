"""
One-time script: stamps swap_front_back=True onto consolidated_data.csv
for every objectid listed in code/manual/flipped.csv.
"""
import pandas as pd

consolidated_path = 'data/processed/consolidated_data.csv'
flipped_path      = 'code/manual/flipped.csv'

df      = pd.read_csv(consolidated_path)
flipped = pd.read_csv(flipped_path)

flipped_ids = set(flipped['objectid'].dropna().str.strip())

if 'swap_front_back' not in df.columns:
    df['swap_front_back'] = False

matched = df['objectid'].isin(flipped_ids)
df.loc[matched, 'swap_front_back'] = True

df.to_csv(consolidated_path, index=False)

print(f"Stamped swap_front_back=True on {matched.sum()} of {len(flipped_ids)} requested objectids.")
unmatched = flipped_ids - set(df['objectid'])
if unmatched:
    print(f"WARNING: {len(unmatched)} objectids in flipped.csv not found in CSV:")
    for oid in sorted(unmatched):
        print(f"  {oid}")
