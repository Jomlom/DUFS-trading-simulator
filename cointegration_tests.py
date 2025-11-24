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

# ETF1 = bond1 + bond2 + bond3
# ETF2 = 0.5(bond1 + bond2 + bond4)

# Resolve CSV path relative to this script (robust) and print diagnostics
BASE = Path(__file__).resolve().parent
csv_path = BASE / "Round Data" / "Round_2" / "Round_2.csv"

stock_names, time, df = read_file(str(csv_path))

bond1_df = df[df["product"] == "bond1"].copy()
bond2_df = df[df["product"] == "bond2"].copy()
bond3_df = df[df["product"] == "bond3"].copy()
bond4_df = df[df["product"] == "bond4"].copy()
ETF1_df = df[df["product"] == "ETF1"].copy()
ETF2_df = df[df["product"] == "ETF2"].copy()

# Calculate volume weighted average price using all 3 bid/ask levels
def calculate_vwap(bids, asks, bid_vols, ask_vols):
    total_volume = sum(bid_vols) + sum(ask_vols)
    if total_volume == 0:
         return None
    
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

bond1_df = df_vwap_apply(bond1_df)
bond2_df = df_vwap_apply(bond2_df)
bond3_df = df_vwap_apply(bond3_df)
bond4_df = df_vwap_apply(bond4_df)
ETF1_df = df_vwap_apply(ETF1_df)
ETF2_df = df_vwap_apply(ETF2_df)

# --- synthETF1 = bond1 + bond2 + bond3 (by VWAP) ---
synthETF1_df = (
    bond1_df[['timestamp', 'vwap']].rename(columns={'vwap': 'b1'})
    .merge(bond2_df[['timestamp', 'vwap']].rename(columns={'vwap': 'b2'}), on='timestamp', how='inner')
    .merge(bond3_df[['timestamp', 'vwap']].rename(columns={'vwap': 'b3'}), on='timestamp', how='inner')
)

synthETF1_df['vwap'] = synthETF1_df['b1'] + synthETF1_df['b2'] + synthETF1_df['b3']
synthETF1_df['product'] = 'synthETF1'
synthETF1_df = synthETF1_df[['timestamp', 'vwap', 'product']]

# --- synthETF2 = 0.5 * (bond1 + bond2 + bond4) ---
synthETF2_df = (
    bond1_df[['timestamp', 'vwap']].rename(columns={'vwap': 'b1'})
    .merge(bond2_df[['timestamp', 'vwap']].rename(columns={'vwap': 'b2'}), on='timestamp', how='inner')
    .merge(bond4_df[['timestamp', 'vwap']].rename(columns={'vwap': 'b3'}), on='timestamp', how='inner')
)

synthETF2_df['vwap'] = 0.5 * (synthETF2_df['b1'] + synthETF2_df['b2'] + synthETF2_df['b3'])
synthETF2_df['product'] = 'synthETF2'
synthETF2_df = synthETF2_df[['timestamp', 'vwap', 'product']]



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
    
    merged = merged.replace([np.inf, -np.inf], np.nan)
    merged = merged.dropna(subset=["vwap1", "vwap2"])
    merged = merged[(merged["vwap1"]>0) & (merged['vwap2']>0)]

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


for (df1,df2) in [(bond1_df, bond2_df), (bond1_df, bond3_df), (bond1_df, bond4_df),
                   (bond1_df, ETF1_df), (bond1_df, ETF2_df), (bond1_df, synthETF1_df), 
                   (bond1_df, synthETF2_df), (bond2_df, bond3_df), (bond2_df, bond4_df),
                        (bond2_df, ETF1_df), (bond2_df, ETF2_df), (bond2_df, synthETF1_df), (bond2_df, synthETF2_df),
                            (bond3_df, bond4_df), (bond3_df, ETF1_df), (bond3_df, ETF2_df), (bond3_df, synthETF1_df), (bond3_df, synthETF2_df),
                                (bond4_df, ETF1_df), (bond4_df, ETF2_df), (bond4_df, synthETF1_df), (bond4_df, synthETF2_df),
                                    (ETF1_df, ETF2_df), (ETF1_df, synthETF1_df), (ETF1_df, synthETF2_df), (ETF2_df, synthETF1_df), (ETF2_df, synthETF2_df), (synthETF1_df, synthETF2_df)]:
        print(f"Testing Cointegration between {df1['product'].iloc[0]} and {df2['product'].iloc[0]}")
        Cointegration_Test(df1, df2, plot = True)
        