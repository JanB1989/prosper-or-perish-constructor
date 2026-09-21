from pathlib import Path
import polars as pl
r=Path.cwd(); a=pl.read_csv(r/'tmp/china_start_before.csv'); z=pl.read_csv(r/'artifacts/data/worldbuilder/start_placement.csv')
d=a.select('location_tag',pl.col('capacity_people').alias('before')).join(z.select('location_tag',pl.col('capacity_people').alias('after')),on='location_tag').filter(pl.col('before')!=pl.col('after'))
print('changed capacities',d.height)
print(d.filter(pl.col('location_tag').is_in(['bijnot','cairo'])).to_dicts())
print(d.filter((pl.col('after')-pl.col('before')).abs()<10000).to_dicts())
