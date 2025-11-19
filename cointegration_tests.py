import numpy as np
import csv
from dataimport import read_file 
import pandas as pd
from pathlib import Path
import sys
import matplotlib.pyplot as plt
import statsmodels.api as sm
import statsmodels.tsa.stattools as ts
from statsmodels.tsa.stattools import adfuller 


# Resolve CSV path relative to this script (robust) and print diagnostics
BASE = Path(__file__).resolve().parent
csv_path = BASE / "Round Data" / "Round_1" / "Round_1.csv"

stock_names, time, df = read_file(str(csv_path))

Hatfield_df = df[df["product"] == "HATFIELD_STOCKS"].copy()
Castle_df = df[df["product"] == "CASTLE_STOCKS"].copy()
Chads_df = df[df["product"] == "CHADS_STOCKS"].copy()
Johns_df = df[df["product"] == "JOHNS_STOCKS"].copy()
Collingwood_df = df[df["product"] == "COLLINGWOOD_STOCKS"].copy()
Cuths_df = df[df["product"] == "CUTHS_STOCKS"].copy()

# Calculate volume weighted average price using all 3 bid/ask levels
def calculate_vwap(bids, asks, bid_vols, ask_vols):
    total_volume = sum(bid_vols) + sum(ask_vols)
    total_value = (sum(b * v for b, v in zip(bids, bid_vols)) + 
                   sum(a * v for a, v in zip(asks, ask_vols)))
    return total_value / total_volume

def df_vwap_apply(df):
    df.loc[:,'vwap'] = df.apply(lambda x: calculate_vwap(
    [x['bid_price_1'], x['bid_price_2'], x['bid_price_3']],
    [x['ask_price_1'], x['ask_price_2'], x['ask_price_3']], 
    [x['bid_volume_1'], x['bid_volume_2'], x['bid_volume_3']],
    [x['ask_volume_1'], x['ask_volume_2'], x['ask_volume_3']]
), axis=1)
    
    return df

Hatfield_df = df_vwap_apply(Hatfield_df)
Castle_df = df_vwap_apply(Castle_df)
Chads_df = df_vwap_apply(Chads_df)
Johns_df = df_vwap_apply(Johns_df)
Collingwood_df = df_vwap_apply(Collingwood_df)
Cuths_df = df_vwap_apply(Cuths_df)

def Cointegration_Test(df1, df2, plot = True, re = False):
    '''
    Plot = True self explanatory
    re = True returns vectors of residuals, use for Z- test
    '''


    # Merge on index to ensure alignment
    df1_renamed = df1.rename(columns={'vwap': 'vwap1'})
    df2_renamed = df2.rename(columns={'vwap': 'vwap2'})

    # Then merge
    merged = pd.merge(df1_renamed, df2_renamed, on='timestamp', how='inner')
    Y = np.log(merged['vwap2'])
    X = np.log(merged['vwap1'])
    
    X = sm.add_constant(X)
    model = sm.OLS(Y, X)
    results = model.fit()
    results.params

    #Get spread
    alpha = results.params.values[0]
    beta = results.params.values[1]
    errors = Y - (alpha + beta * X.iloc[:, 1])

    #Conduct Dikey-Fuller Test
    dftest = adfuller(errors, maxlag = 1)
    dfoutput = pd.Series(dftest[0:4], index = ["Test Statistic", "p-value", "#Lags Used", "Number of Observations Used"])
    critical_values = pd.Series(dftest[4].values(), index = dftest[4].keys())
    print(f"Dickey Fuller Result:\n{dfoutput} \n\n Dickey Fuller Critical Values:\n{critical_values}")


    #Plot OLS Test
    if plot == True:    
        errors.plot(label = f'{df2["product"].iloc[0]} vs {df1["product"].iloc[0]} Spread')
        plt.axhline(y=0, color='red', linestyle='--', alpha=0.7, label='Zero Line')
        plt.xlabel('Time')
        plt.ylabel('Spread')
        plt.legend()
        plt.show()

    if re == True:
        return errors
    return None


def Z_test(errors):
    zscore = (errors - errors.mean()) / errors.std()
    zscore.plot(label = 'Z-score')
    plt.xlabel('Time')
    plt.ylabel('Values')
    plt.axhline(y = 1.2, color = 'b', label = '1.2 threshold')
    plt.axhline(y = -1.2, color = 'b', label = '-1.2 threshold')
    plt.legend()
    plt.show()


def has_nan_vwap(df):
    return df['vwap'].isna().any()

# Usage
#if has_nan_vwap(Castle_df):
#    print("VWAP column contains NaN values!")
#else:
#    print("VWAP column is clean - no NaN values")


for (df1,df2) in [(Hatfield_df, Castle_df), (Hatfield_df, Chads_df), (Hatfield_df, Johns_df),
                   (Hatfield_df, Collingwood_df), (Hatfield_df, Cuths_df),
                     (Castle_df, Chads_df), (Castle_df, Johns_df),
                        (Castle_df, Collingwood_df), (Castle_df, Cuths_df),
                            (Chads_df, Johns_df), (Chads_df, Collingwood_df), (Chads_df, Cuths_df),
                                (Johns_df, Collingwood_df), (Johns_df, Cuths_df),
                                    (Collingwood_df, Cuths_df)]:
        print(f"Testing Cointegration between {df1['product'].iloc[0]} and {df2['product'].iloc[0]}")
        Cointegration_Test(df1, df2, plot = True)
        