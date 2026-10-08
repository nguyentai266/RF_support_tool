import datetime
import glob
import os
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd


class ParserLog(object):
	def __init__(self):
		super().__init__()
		

	def load_limit(self,filepath):
		col_use=["measurement","low_limit","high_limit"]
		df=pd.read_csv(filepath,header=1,usecols=col_use)
		final=df.copy()
		return final # type: ignore

	def __load_data(self,filepath):
		col_use=["phase","measurement","value"]
		info_log=pd.read_csv(filepath,nrows=0).to_string() #lay dong dau tien cua log
		info_dict={}
		if "dut_id:" in info_log:
			pattern = r'(\w+):\s*([\w\.\-]+)'
			matches=re.findall(pattern,info_log)
			info_dict=dict(matches)
			
		if info_dict:
			dut_id=info_dict.get("dut_id")
			outcome=info_dict.get("result")
			station_id=info_dict.get("station_id")
			#time=filepath.split('.')[0].split('_')[-1]
			start_time = datetime.datetime.fromtimestamp(int(filepath.split('.')[0].split('_')[-1]) / 1000).strftime('%Y-%m-%d %H:%M:%S')
			slot=filepath.split('.')[0].split('_')[-2]

			info_df=pd.DataFrame({
				"measurement":["slot","dut_id","station_id","outcome","start_time","log_path"],
				"value":[slot,dut_id,station_id,outcome,start_time,filepath]
				})
			df=pd.read_csv(filepath,header=1,usecols=col_use)
			
			df_full=df.drop(columns="phase").copy()
			#df_full=df.copy()
			df_combined=pd.concat([info_df,df_full],ignore_index=True)
			df_transpose=df_combined.set_index('measurement').T
			
			return df_transpose  #type: ignore
 
	def __process_data(self,filepath):
		try:
			return self.__load_data(filepath)

		except Exception as e:
			print(f"Error: {e}")
			return None

	def summary_data(self,path_dir):
		list_file=glob.glob(os.path.join(path_dir,"*.csv"))
		
		if list_file: df_limit=self.load_limit(filepath=list_file[0])
		with ThreadPoolExecutor(max_workers=8) as executor:
			results = list(executor.map(lambda f:self.__process_data(f), list_file))
	
		li = [df for df in results if df is not None]
		if li: 
			li_cleaned = [df.loc[:, ~df.columns.duplicated()].copy() for df in li]
			df_summary = pd.concat(li_cleaned, axis=0, ignore_index=True)
		else:  df_summary = pd.DataFrame()
		return df_limit,df_summary		#type: ignore
	

	
	def group_data(self,dataFrame,groupBy):
		if groupBy == "dut_id":
			groups = [(key, g) for key, g in dataFrame.groupby(groupBy)]
		elif groupBy == "station_id":
			groups = [(key, g) for key, g in dataFrame.groupby(groupBy)]
		else:
			groups = [(key, g) for key, g in dataFrame.groupby(["station_id","dut_id"])]
		
		return groups
	
	def grr_summary(self, limit, summary):
		df_final = pd.DataFrame()
		
		if not summary.empty and not limit.empty:

			if any('measurement' in str(idx).lower() for idx in limit.index):
				limit = limit.T
				
			meas_col = [col for col in limit.columns if 'measurement' in str(col).lower()][0]
			low_col = [col for col in limit.columns if 'low' in str(col).lower() or 'min' in str(col).lower()][0]
			high_col = [col for col in limit.columns if 'high' in str(col).lower() or 'max' in str(col).lower()][0]
			
			low_row_dict = {col: "" for col in summary.columns}
			high_row_dict = {col: "" for col in summary.columns}
			
			id_column = 'dut_id' if 'dut_id' in summary.columns else summary.columns[0]
			low_row_dict[id_column] = ""
			high_row_dict[id_column] = ""
			
			def keep_only_numeric(val):
				if pd.isna(val): return ""
				val_str = str(val).strip()
				try:
					float(val_str)
					return val
				except ValueError:
					return ""
			
			for _, row in limit.iterrows():
				item_name = str(row[meas_col]).strip()
				if item_name in summary.columns:
					low_row_dict[item_name] = keep_only_numeric(row[low_col])
					high_row_dict[item_name] = keep_only_numeric(row[high_col])
					
			
			df_limits_rows = pd.DataFrame([high_row_dict,low_row_dict], columns=summary.columns)
			df_final = pd.concat([df_limits_rows, summary], axis=0, ignore_index=True)

		else:
			df_final = summary.copy()
			
		return df_final



if __name__=="__main__":\
	
	parser = ParserLog()
	limit,summary = parser.summary_data("C:/Users/V1531673/Desktop/CELL-04/GRR")
	
	data = parser.grr_summary(limit=limit,summary=summary)
	data.to_csv("grr.csv",index=False)

	
	
