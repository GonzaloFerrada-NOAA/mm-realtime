#!/usr/bin/env python
# coding: utf-8

# # MELODIES-MONET-analysis dev
# First lets just import the driver to see how it happens and so we can play around with it a little

#This is needed to tell matplotlib to use a non-interactive backend and avoid display errors.
import matplotlib
matplotlib.use('Agg')
from melodies_monet import driver
from melodies_monet.util.region_select import select_region
import pandas as pd
import os
import dask
import sys

platform    = sys.argv[1] # 'airnow' 'aeronet' 'openaq'
plot_type   = sys.argv[2] if len(sys.argv) > 2 else ''   # plot type from mm_run.sh (e.g. 'ts_site')

print("Hello from mm_analysis")
print(f"    platform    = {platform}")
print(f"    plot_type   = {plot_type}")


def pair_to_df(an, p, obsvar, domain_type, domain_name, rem_obs_nan):
    """Paired data for one obs/model pair and one domain, filtered as driver.plotting() does."""
    modvar = p.model_vars[p.obs_vars.index(obsvar)]
    if modvar == obsvar:                                  # pairing appends '_new' when names match
        modvar = modvar + '_new'
    reg = select_region(p.obj, domain_type, domain_name)  # subset to this site
    df = reg.to_dataframe(dim_order=['time', 'x']).loc[an.start_time:an.end_time].reset_index()
    df = df.dropna(subset=[modvar, obsvar] if rem_obs_nan else [modvar])
    cols = [c for c in ['time', 'time_local', 'siteid', 'latitude', 'longitude'] if c in df.columns]
    return df[cols + [obsvar, modvar]].rename(columns={modvar: p.model})  # model column = model label


def save_csv(an):
    """One CSV per figure, same directory and name as the PNG (.csv instead of .png).
    Columns: time, time_local, siteid, latitude, longitude, <obsvar>, <model1>, <model2>, ...
    Stations with no valid obs get no file; they are listed in stations_without_data.csv."""
    start = an.start_time.strftime('%Y-%m-%d_%H')   # same date stamps used in the figure names
    end = an.end_time.strftime('%Y-%m-%d_%H')
    no_data = []                                     # one metadata row per station without obs
    for grp, gd in an.control_dict['plots'].items():
        rem_obs_nan = gd.get('data_proc', {}).get('rem_obs_nan', True)
        obs_vars = list(dict.fromkeys(v for l in gd['data'] for v in an.paired[l].obs_vars))
        for obsvar in obs_vars:
            for dtype, dname in zip(gd['domain_type'], gd['domain_name']):
                dfs = {l: pair_to_df(an, an.paired[l], obsvar, dtype, dname, rem_obs_nan)
                       for l in gd['data'] if obsvar in an.paired[l].obs_vars}

                # No valid obs at this station: save its metadata, skip the file
                if all(df[obsvar].isna().all() for df in dfs.values()):
                    reg = select_region(an.paired[next(iter(dfs))].obj, dtype, dname)
                    row = {'site': dname, 'variable': obsvar}
                    for c in ['siteid', 'latitude', 'longitude']:
                        v = reg[c].values.ravel() if c in reg else []
                        row[c] = v[0] if len(v) else None   # first value (same for all times)
                    no_data.append(row)
                    continue

                # obs + one model column per pair, joined on time and site
                out = pd.concat([df.drop(columns=an.paired[l].model) for l, df in dfs.items()]) \
                        .drop_duplicates(subset=['time', 'siteid'])
                for l, df in dfs.items():
                    out = out.merge(df[['time', 'siteid', an.paired[l].model]], on=['time', 'siteid'], how='outer')
                # Same name as plotting(): grp.type.var.start.end.domain_type.domain_name
                fn = os.path.join(an.output_dir, f"{grp}.{gd['type']}.{obsvar}.{start}.{end}.{dtype}.{dname}.csv")
                out.sort_values(['time', 'siteid']).to_csv(fn, index=False)
                print('CSV written:', fn)

    # Single file listing every station skipped above
    if no_data:
        fn = os.path.join(an.output_dir, 'stations_without_data.csv')
        pd.DataFrame(no_data).to_csv(fn, index=False)
        print(f'{len(no_data)} stations without data listed in:', fn)


# ### Driver class
# Now lets create an instance of the python driver analysis class. It consists of 4 main parts; model instances, observation instances, a paired instance of both.  This will allow us to move things around the plotting function for spatial and overlays and more complex plots.

an = driver.analysis()

# ### Control File
#
# set the yaml control file and begin by reading the file

an.control = 'control.yaml'        # 'control.yaml.rapchemtest'
an.read_control() # control='control.yaml')

dask.config.set(**{'array.slicing.split_large_chunks': True})

# ### Loading the model data
#
# driver will automatically loop through the "models" found in the model section of the yaml file and create an instance of the driver.model class for each that includes the label, mapping information, and xarray object as well as the filenames.  Note it can open multiple files easily by including hot keys

an.open_models()

#All the info in the analysis class can also be called.
print(an.start_time)
print(an.end_time)

an.open_obs()

# All the info in the observation class can also be called.
an.obs[platform].obj

#This just pairs the data
print("pairing")
an.pair_data()

# And the stats
if (plot_type == 'stats'):
    print('Doing stats...')
    an.stats()
elif (plot_type == 'ts_site'):
    # Save the paired data behind the ts_site figures as CSV
    print('Saving csv...')
    save_csv(an)
else:
    # And this generates all the plots.
    print('Plotting...')
    an.plotting()