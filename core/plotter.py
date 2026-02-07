
import json
import os

import matplotlib
import numpy as np
import pandas as pd
import yaml
from matplotlib import pyplot as plt
from matplotlib.figure import Figure

from core.load_config import load_yaml
from core.logger import setup_logging

logger=setup_logging()
matplotlib.use('Agg')
class DrawChart(object):
    def __init__(self):
        self.config=load_yaml()

    def maker_graph(self,limit_df,data_df,phase,draw_by="station_id"):
        self.phase=phase
        limit_df_by_phase=limit_df[limit_df["phase"]==phase].copy()
        self.min_freq=limit_df_by_phase["freq"].min()
        #self.max_freq=limit_df_by_phase["freq"].max()
        ##
        limit_df_by_phase["low_limit"] = pd.to_numeric(limit_df_by_phase["low_limit"], errors="coerce")
        limit_df_by_phase["high_limit"] = pd.to_numeric(limit_df_by_phase["high_limit"], errors="coerce")
        limit_df_by_phase.replace([np.inf, -np.inf], np.nan, inplace=True)
        ##
        self.freq_limit=limit_df_by_phase["freq"]
        self.hsl=limit_df_by_phase['high_limit']
        self.lsl=limit_df_by_phase['low_limit']
        
        
        #config plot 
        self.y_min=self.config["plot_config"][phase]["min"]
        self.y_max=self.config["plot_config"][phase]["max"]
        self.y_step=self.config["plot_config"][phase]["step"]
        if "fr_norm" or "seal_chirp" in phase:
            self.y_extend=self.y_step
        else:
            self.y_extend=self.y_step/2
        
        df_graph=data_df[data_df["phase"].isin([draw_by,phase])].copy()
        data_cols = [col for col in data_df.columns if col not in ['dut_id', 'Test_ID', 'phase']]
        grouped=df_graph.groupby('station_id')
    
        df_graph.to_csv(f"phase/{phase}.csv")
        self.freq_data=df_graph["freq"]
        self.max_freq=df_graph["freq"].max()
        
        #values = df_graph.iloc[:, 2:]
        #values.to_csv(f"phase/{phase}.csv")
        fig=self.__draw(grouped)
        return fig

        


            
    def __draw(self,values):
        fig = Figure(figsize=(7, 5), dpi=100)
        fig.patch.set_facecolor("#e6e6e6")
        ax = fig.add_subplot(111)
        ax.set_xlim(self.min_freq,self.max_freq)
        ax.set_ylim(self.y_min - self.y_extend,self.y_max + self.y_extend) # Thiết lập dải hiển thị từ -60dB đến 60dB
        ax.set_yticks(np.arange(self.y_min,self.y_max+self.y_extend, self.y_step)) 
        
        fig.suptitle(self.phase)    
        ax.plot(self.freq_limit,self.hsl, color="red", linewidth=1.5, label="high_limit")
        ax.plot(self.freq_limit,self.lsl, color="red", linewidth=1.5, label="low_limit")
        values = values.apply(pd.to_numeric, errors='coerce')
       
        x=self.freq_data.to_numpy()
        for dut_id,group in values:
            y_matrix = group[data_cols].to_numpy()
        y=values.to_numpy()

        ax.plot(x,y,linewidth=0.8)
        ax.axhline(y=0,color="#000000",linewidth=1,linestyle="--")
        ax.set_xscale("log")
        ax.set_xlabel("Frequency (Hz)")
        ax.grid(True, which="both", linestyle="--", linewidth=0.5)
        
        return fig
    
if __name__ == "__main__":
    draw=DrawChart()
    
    limit_df=pd.read_csv("limit.csv")
    data_df=pd.read_csv("sum.csv")
    draw.maker_graph(limit_df,data_df,"mic-1_fr")
    

